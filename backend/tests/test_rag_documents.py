import uuid
from types import SimpleNamespace

from app.models.document import Document, DocumentChunk


def test_employee_cannot_list_documents(client, auth_headers):
    response = client.get("/api/v1/rag/documents", headers=auth_headers)
    assert response.status_code == 403


def test_hr_can_toggle_and_delete_document(client, db, hr_auth_headers, hr_user):
    document = Document(
        id=uuid.uuid4(),
        title="Leave policy",
        file_path="/tmp/policy.pdf",
        uploaded_by=hr_user.id,
        is_active=True,
    )
    db.add(document)
    db.add(
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=document.id,
            chunk_index=0,
            content="Leave policy content",
            embedding_id=str(uuid.uuid4()),
            embedding_provider_id=uuid.uuid4(),
        )
    )
    db.commit()

    toggle_response = client.patch(
        f"/api/v1/rag/documents/{document.id}/active?is_active=false",
        headers=hr_auth_headers,
    )
    assert toggle_response.status_code == 200
    assert toggle_response.json()["is_active"] is False

    delete_response = client.delete(f"/api/v1/rag/documents/{document.id}", headers=hr_auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["ok"] is True


def test_hr_upload_document_works_with_ingest_mock(client, hr_auth_headers, monkeypatch):
    fake_doc = SimpleNamespace(id=uuid.uuid4(), title="Policy", chunks=[1, 2])

    class FakeIngestService:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        def process_document(self, _file_path: str, _title: str):
            return fake_doc

    monkeypatch.setattr("app.api.v1.rag.RAGIngestService", FakeIngestService)

    response = client.post(
        "/api/v1/rag/documents",
        headers=hr_auth_headers,
        files={"file": ("policy.pdf", b"%PDF-1.4 test content", "application/pdf")},
        data={"title": "Policy upload"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Policy"
    assert payload["chunks"] == 2
