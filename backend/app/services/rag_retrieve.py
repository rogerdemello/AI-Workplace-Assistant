import hashlib
import re
import numpy as np
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from ..models.document import Document, DocumentChunk
from ..ai_client import get_ai_client
from ..cache import get_cached, set_cached
from .hr_personality import FRIENDLY_SYSTEM_PROMPT

SIMILARITY_THRESHOLD = 0.7
TOP_K = 3
CHUNK_CACHE_TTL = 3600
RETRIEVAL_CACHE_TTL = 300
KEYWORD_FALLBACK_THRESHOLD = 0.15
# Cache chunk embeddings for a week. Chunk content is immutable per ingest
# (chunks are recreated on re-upload), so the key is safe to keep cold.
EMBEDDING_CACHE_TTL = 7 * 24 * 3600

logger = logging.getLogger(__name__)

_BM25_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_BM25_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "and", "or", "but",
    "if", "to", "this", "that", "these", "those", "it", "its",
}


def _normalise_scores(scores: List[float]) -> List[float]:
    """Map raw BM25 scores onto 0..1, tolerating negative values.

    BM25 IDF is negative for a term present in every document, so on a small
    corpus a genuine match can score below zero. Min-max keeps the ranking and
    still marks a lone matching chunk as relevant; an all-zero corpus (no query
    term present anywhere) stays at zero so nothing is falsely retrieved.
    """
    if not scores:
        return []
    top = max(scores)
    bottom = min(scores)
    if top > bottom:
        span = top - bottom
        return [(s - bottom) / span for s in scores]
    # Every chunk scored identically: either all matched equally, or none did.
    return [0.0 if top == 0 else 1.0 for _ in scores]


def _bm25_tokenize(text: str) -> List[str]:
    return [
        tok
        for tok in (m.group(0).lower() for m in _BM25_TOKEN_RE.finditer(text or ""))
        if tok not in _BM25_STOP_WORDS
    ]

FALLBACK_SUMMARIES = {
    "leave": {
        "category": "leave",
        "summary": (
            "Our leave policy provides paid time off for vacation, sick leave, and personal days. "
            "Employees accrue leave based on tenure and role. Requests should be submitted through "
            "the HR portal at least 48 hours in advance when possible. For extended medical leave, "
            "please contact HR directly to discuss eligibility and documentation requirements."
        ),
    },
    "harassment": {
        "category": "complaint",
        "summary": (
            "We maintain a strict zero-tolerance policy toward harassment, discrimination, and bullying. "
            "All reports are treated confidentially and investigated promptly by HR or a designated "
            "ombuds person. Employees may report concerns anonymously through the ethics hotline or "
            "directly to their manager or HR partner. Retaliation for reporting in good faith is prohibited."
        ),
    },
    "remote": {
        "category": "general",
        "summary": (
            "Our remote work policy supports flexible arrangements where role requirements allow. "
            "Eligible employees may work remotely up to the agreed schedule with their manager. "
            "Core collaboration hours and security protocols (VPN, device management) apply. "
            "Please consult your manager or the HR portal for role-specific eligibility and expectations."
        ),
    },
    "benefits": {
        "category": "general",
        "summary": (
            "We offer a comprehensive benefits package including health, dental, and vision insurance, "
            "retirement plans with employer matching, wellness stipends, and professional development "
            "allowances. Enrollment periods and plan details are available on the HR portal. For questions "
            "about coverage or claims, contact our benefits administrator or HR partner."
        ),
    },
    "pto": {
        "category": "leave",
        "summary": (
            "Paid Time Off (PTO) combines vacation, sick, and personal leave into a single bank. "
            "Accrual rates vary by tenure and location. PTO requests should be submitted via the HR portal, "
            "and managers are encouraged to approve requests that meet business needs. Unused PTO may be "
            "subject to carryover or payout policies based on local regulations."
        ),
    },
}


class RAGRetrieveService:
    def __init__(self, db: Session, use_mock: bool = False):
        self.db = db
        self.ai_client = get_ai_client(use_mock=use_mock)
        self._chunk_cache = {}
    
    def _get_active_chunks(self) -> List[DocumentChunk]:
        cache_key = "rag:active_chunks"
        cached = get_cached(cache_key)
        
        if cached:
            chunk_ids = cached
            if chunk_ids:
                return self.db.query(DocumentChunk).filter(
                    DocumentChunk.id.in_(chunk_ids)
                ).all()
            return []
        
        chunks = self.db.query(DocumentChunk).join(Document).filter(
            Document.is_active == True
        ).all()
        
        chunk_ids = [str(c.id) for c in chunks]
        set_cached(cache_key, chunk_ids, CHUNK_CACHE_TTL)
        
        return chunks
    
    def search(
        self,
        query: str,
        top_k: int = TOP_K,
        threshold: float = SIMILARITY_THRESHOLD
    ) -> List[Dict]:
        query_hash = hashlib.md5(f"{query}:{top_k}:{threshold}".encode("utf-8")).hexdigest()
        cache_key = f"rag:search:{query_hash}"
        cached_result = get_cached(cache_key)

        if cached_result is not None:
            return cached_result

        query_embedding: Optional[List[float]] = None
        embedding_available = True
        try:
            query_embedding = self.ai_client.embeddings(query)
        except Exception as exc:
            embedding_available = False
            logger.warning(
                "RAG embedding unavailable; falling back to keyword retrieval only: %s",
                exc,
            )

        chunks = self._get_active_chunks()
        if not chunks:
            set_cached(cache_key, [], RETRIEVAL_CACHE_TTL)
            return []

        # Build BM25 corpus from the current active chunks. The library is
        # tiny and recomputation is cheap (chunks count is small), so building
        # per query keeps the implementation simple and correct on edits.
        keyword_scores = self._bm25_scores(query, chunks)

        # Normalise BM25 to 0..1 so the weighted sum with cosine similarity
        # stays in a comparable range across queries.
        #
        # Min-max rather than divide-by-max: BM25 IDF goes negative when a term
        # appears in every document, which is the norm on a small corpus. The
        # old `s / max_kw if max_kw > 0` collapsed every score to zero in that
        # case, so keyword fallback — the thing that rescues us when embeddings
        # are down — silently returned nothing for small document sets.
        normalised_kw = _normalise_scores(keyword_scores)

        results = []
        for idx, chunk in enumerate(chunks):
            vector_sim = 0.0
            if embedding_available and query_embedding is not None:
                chunk_embedding = self._get_chunk_embedding(chunk)
                if chunk_embedding is not None:
                    vector_sim = self._cosine_similarity(query_embedding, chunk_embedding)

            keyword_sim = normalised_kw[idx]

            similarity = (0.7 * vector_sim) + (0.3 * keyword_sim)
            if not embedding_available:
                similarity = keyword_sim

            effective_threshold = threshold if embedding_available else min(threshold, KEYWORD_FALLBACK_THRESHOLD)
            if similarity >= effective_threshold:
                results.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "document_title": chunk.document.title,
                    "document_updated_at": chunk.document.updated_at,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "score": round(similarity, 4),
                    "vector_score": round(vector_sim, 4),
                    "keyword_score": round(keyword_sim, 4),
                    "source": f"{chunk.document.title} (chunk {chunk.chunk_index + 1})"
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        final_results = results[:top_k]

        set_cached(cache_key, final_results, RETRIEVAL_CACHE_TTL)

        return final_results

    def _bm25_scores(self, query: str, chunks: List[DocumentChunk]) -> List[float]:
        """BM25 score per chunk for ``query``. Falls back to naive overlap if
        the optional ``rank_bm25`` package isn't installed."""
        try:
            from rank_bm25 import BM25Okapi  # type: ignore
        except ImportError:
            logger.info("rank_bm25 not installed; using naive overlap for keyword score")
            return [self._keyword_similarity(query, chunk.content) for chunk in chunks]

        corpus = [_bm25_tokenize(chunk.content) for chunk in chunks]
        if not any(corpus):
            return [0.0 for _ in chunks]
        bm25 = BM25Okapi(corpus)
        query_tokens = _bm25_tokenize(query)
        if not query_tokens:
            return [0.0 for _ in chunks]
        return list(bm25.get_scores(query_tokens))

    def _classify_query(self, query: str) -> str:
        q = query.lower()
        if any(word in q for word in ("leave", "vacation", "sick day", "time off", "pto")):
            if "pto" in q or "paid time off" in q:
                return "pto"
            return "leave"
        if any(word in q for word in ("harassment", "discrimination", "bullying", "complaint", "report")):
            return "harassment"
        if any(word in q for word in ("remote", "work from home", "wfh", "hybrid")):
            return "remote"
        if any(word in q for word in ("benefits", "insurance", "health", "dental", "retirement", "401k")):
            return "benefits"
        return "general"

    def _get_fallback_summary(self, query: str) -> Dict[str, str]:
        topic = self._classify_query(query)
        return FALLBACK_SUMMARIES.get(topic, FALLBACK_SUMMARIES["general"])
    
    def search_with_citations(self, query: str) -> Dict:
        results = self.search(query)

        if not results:
            fallback = self._get_fallback_summary(query)
            return {
                "answer": fallback["summary"],
                "citations": [],
                "sources": [],
                "fallback_summary": fallback,
            }

        context = "\n\n".join([
            f"[Source {i+1}]: {r['content']}"
            for i, r in enumerate(results)
        ])

        prompt = f"""Based on the following context, answer the user's question.
If you cannot find the answer in the context, say so honestly.

Context:
{context}

Question: {query}

Answer:"""

        response = self.ai_client.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": f"""{FRIENDLY_SYSTEM_PROMPT}

When answering HR policy questions:
- Be helpful and friendly
- Always cite your sources using the format [Source N]
- If the context doesn't have the answer, say so honestly and offer to help find the right person to ask"""
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=500
        )

        answer = response["choices"][0]["message"]["content"]

        citations = [r["source"] for r in results]

        return {
            "answer": answer,
            "citations": citations,
            "sources": results
        }
    
    def _get_chunk_embedding(self, chunk: DocumentChunk) -> Optional[List[float]]:
        """Embedding for a chunk. Cached in Redis under the chunk's UUID so
        we don't re-embed every chunk on every query — the original
        implementation made an Azure OpenAI call per chunk per query, which is
        prohibitively slow and expensive at any non-trivial corpus size.
        """
        cache_key = f"rag:chunk_embedding:{chunk.id}"
        cached = get_cached(cache_key)
        if isinstance(cached, list) and cached:
            return cached
        try:
            vector = self.ai_client.embeddings(chunk.content[:1000])
        except Exception:
            return None
        if vector:
            set_cached(cache_key, vector, EMBEDDING_CACHE_TTL)
        return vector
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2:
            return 0.0
        
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def _keyword_similarity(self, query: str, content: str) -> float:
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words or not content_words:
            return 0.0
        
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all',
            'each', 'few', 'more', 'most', 'other', 'some', 'such',
            'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
            'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because',
            'until', 'while', 'what', 'which', 'who', 'whom', 'this',
            'that', 'these', 'those', 'am', 'i', 'me', 'my', 'myself',
            'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
            'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
            'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
            'they', 'them', 'their', 'theirs', 'themselves'
        }
        
        query_keywords = query_words - stop_words
        content_keywords = content_words - stop_words
        
        if not query_keywords:
            return 0.0
        
        overlap = len(query_keywords & content_keywords)
        return overlap / len(query_keywords)


def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2:
        return 0.0
    
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    
    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))
