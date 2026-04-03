import numpy as np
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.document import Document, DocumentChunk
from ..ai_client import get_ai_client
from ..cache import get_cached, set_cached
from .hr_personality import FRIENDLY_SYSTEM_PROMPT

SIMILARITY_THRESHOLD = 0.7
TOP_K = 3
CHUNK_CACHE_TTL = 3600
RAG_CACHE_TTL = 600


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
        cache_key = f"rag:search:{query}:{top_k}:{threshold}"
        cached_result = get_cached(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        query_embedding = self.ai_client.embeddings(query)
        
        chunks = self._get_active_chunks()
        
        results = []
        for chunk in chunks:
            chunk_embedding = self._get_chunk_embedding(chunk)
            
            if chunk_embedding is not None:
                vector_sim = self._cosine_similarity(query_embedding, chunk_embedding)
            else:
                vector_sim = 0.0
            
            keyword_sim = self._keyword_similarity(query, chunk.content)
            
            similarity = (0.7 * vector_sim) + (0.3 * keyword_sim)
            
            if similarity >= threshold:
                results.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "document_title": chunk.document.title,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "score": round(similarity, 4),
                    "vector_score": round(vector_sim, 4),
                    "keyword_score": round(keyword_sim, 4),
                    "source": f"{chunk.document.title} (chunk {chunk.chunk_index + 1})"
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        final_results = results[:top_k]
        
        set_cached(cache_key, final_results, RAG_CACHE_TTL)
        
        return final_results
    
    def search_with_citations(self, query: str) -> Dict:
        results = self.search(query)
        
        if not results:
            return {
                "answer": "No relevant documents found for your query.",
                "citations": [],
                "sources": []
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
        try:
            return self.ai_client.embeddings(chunk.content[:1000])
        except Exception:
            return None
    
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
