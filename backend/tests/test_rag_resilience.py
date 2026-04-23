from fastapi import status

from app.models.document import Document, DocumentChunk
from app.services.rag_retrieve import RAGRetrieveService


def test_rag_search_keyword_fallback_when_embeddings_fail(db, test_user, monkeypatch):
    document = Document(
        title="Leave Policy",
        file_path="/tmp/leave-policy.pdf",
        uploaded_by=test_user.id,
        is_active=True,
    )
    db.add(document)
    db.flush()
    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Employees can request leave through the HR portal. Paid leave requires manager approval.",
        embedding_id="emb-1",
    )
    db.add(chunk)
    db.commit()

    service = RAGRetrieveService(db)

    def fail_embeddings(_text: str):
        raise RuntimeError("embedding deployment missing")

    monkeypatch.setattr(service.ai_client, "embeddings", fail_embeddings)

    results = service.search("leave policy", top_k=3, threshold=0.7)

    assert len(results) == 1
    assert "Leave Policy" in results[0]["source"]
    assert results[0]["keyword_score"] > 0
    assert results[0]["vector_score"] == 0


def test_rag_search_with_answer_returns_fallback_payload_on_failure(client, auth_headers, monkeypatch):
    from app.api.v1 import rag as rag_api

    class FailingService:
        def __init__(self, *_args, **_kwargs):
            pass

        def search_with_citations(self, _query: str):
            raise RuntimeError("embedding deployment missing")

    monkeypatch.setattr(rag_api, "RAGRetrieveService", FailingService)

    response = client.post(
        "/api/v1/rag/search-with-answer",
        headers=auth_headers,
        params={"query": "Leave policy"},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert "temporarily unavailable" in payload["answer"].lower()
    assert payload["source"] == "fallback"
