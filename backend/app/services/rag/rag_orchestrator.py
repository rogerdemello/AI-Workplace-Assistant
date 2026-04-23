"""Single-orchestrator entrypoint for policy retrieval and grounded answer generation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
import logging

from ...ai_client import get_ai_client
from ..hr_personality import FRIENDLY_SYSTEM_PROMPT
from ..rag_retrieve import RAGRetrieveService

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """Orchestrate query -> retrieve -> answer -> fallback in one place."""

    def __init__(
        self,
        db: Session,
        *,
        use_mock: bool = False,
        retrieve_service: Optional[RAGRetrieveService] = None,
    ) -> None:
        self.db = db
        self.ai_client = get_ai_client(use_mock=use_mock)
        self.retrieve_service = retrieve_service or RAGRetrieveService(db=db, use_mock=use_mock)

    def ask(self, query: str, top_k: int = 3, threshold: float = 0.7) -> Dict[str, Any]:
        query_text = (query or "").strip()
        if not query_text:
            return self._fallback("Please share a policy question so I can look it up.")

        # 1) Retrieve
        try:
            sources = self.retrieve_service.search(query_text, top_k=top_k, threshold=threshold)
        except Exception as exc:
            logger.exception("RAG retrieval failed")
            return self._fallback(
                "Policy knowledge base is temporarily unavailable. Please check with HR while we restore search.",
                error=str(exc),
            )

        if not sources:
            fallback = self.retrieve_service._get_fallback_summary(query_text)
            return {
                "answer": (
                    f"I don't have the exact policy details on that yet, but here's what I can share: "
                    f"{fallback['summary']} If you need more specific guidance, I can connect you with HR."
                ),
                "citations": [],
                "sources": [],
                "source": "retrieval_empty",
                "fallback_summary": fallback,
            }

        # 2) Answer grounded by retrieved chunks
        try:
            context = "\n\n".join(
                f"[Source {idx + 1}] {item.get('content', '')}"
                for idx, item in enumerate(sources)
            )
            prompt = (
                "Answer the HR policy question using only the provided context. "
                "If context is insufficient, say what is missing.\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {query_text}\n\nAnswer:"
            )
            response = self.ai_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"{FRIENDLY_SYSTEM_PROMPT}\n"
                            "Cite sources in [Source N] format and avoid fabrication."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            answer = response["choices"][0]["message"]["content"]
            return {
                "answer": answer,
                "citations": [item.get("source") for item in sources],
                "sources": sources,
                "source": "orchestrated",
            }
        except Exception as exc:
            logger.exception("RAG answer generation failed")
            return self._fallback(
                "Policy knowledge base is temporarily unavailable. Please check with HR while we restore search.",
                sources=sources,
                error=str(exc),
            )

    def _fallback(
        self,
        message: str,
        *,
        sources: Optional[List[Dict[str, Any]]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "answer": message,
            "citations": [],
            "sources": sources or [],
            "source": "fallback",
        }
        if error:
            payload["error"] = error
        return payload
