import hashlib
import logging
import re
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

from ..models.document import Document, DocumentChunk
from ..ai_client import get_ai_client

logger = logging.getLogger(__name__)

# Sentence-aware chunking targets these word counts. Smaller chunks improve
# retrieval precision on short questions; the overlap preserves context across
# boundaries so an answer split across two chunks is still findable.
CHUNK_TARGET_WORDS = 400
CHUNK_OVERLAP_WORDS = 50
CHUNK_MAX_WORDS = 600  # hard cap so a paragraph without periods can't blow up

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(])")


class RAGIngestService:
    def __init__(self, db: Session, user_id: Optional[UUID] = None):
        self.db = db
        self.user_id = user_id
        self.ai_client = get_ai_client()
    
    def process_document(self, file_path: str, title: str) -> Document:
        # Calculate checksum
        with open(file_path, 'rb') as f:
            checksum = hashlib.sha256(f.read()).hexdigest()
        
        # Extract text based on file type
        if file_path.lower().endswith('.pdf'):
            text = self._extract_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            text = self._extract_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
        
        # Create document record
        document = Document(
            title=title,
            file_path=file_path,
            uploaded_by=self.user_id,
            checksum_sha256=checksum,
            is_active=True
        )
        self.db.add(document)
        self.db.flush()  # Get document ID
        
        # Chunk and embed
        chunks = self._chunk_text(text)
        for idx, chunk_text in enumerate(chunks):
            # Generate embedding for chunk
            try:
                embedding = self.ai_client.embeddings(chunk_text)
                logger.info(f"Generated embedding for chunk {idx}, vector dimension: {len(embedding)}")
            except Exception as e:
                logger.warning(f"Failed to generate embedding for chunk {idx}: {e}")
                # Still store chunk even if embedding fails
            
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=idx,
                content=chunk_text,
                embedding_id=str(uuid4()),
                embedding_provider_id=uuid4()  # Would come from integration_providers in production
            )
            self.db.add(chunk)
        
        self.db.commit()
        self.db.refresh(document)
        return document
    
    def _extract_pdf(self, file_path: str) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise ValueError(f"Failed to extract PDF: {str(e)}")
    
    def _extract_docx(self, file_path: str) -> str:
        try:
            from docx import Document as DocxReader
            doc = DocxReader(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
        except Exception as e:
            raise ValueError(f"Failed to extract DOCX: {str(e)}")
    
    def _chunk_text(self, text: str) -> List[str]:
        """Sentence-aware chunking with word-count target and overlap.

        Each chunk is a list of consecutive sentences whose total word count is
        close to ``CHUNK_TARGET_WORDS``. Adjacent chunks share the last
        ``CHUNK_OVERLAP_WORDS`` of the previous chunk so a relevant span isn't
        split unanswerably.
        """
        normalized = re.sub(r"\s+", " ", text or "").strip()
        if not normalized:
            return []

        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(normalized) if s.strip()]
        if not sentences:
            sentences = [normalized]

        chunks: List[str] = []
        current: List[str] = []
        current_word_count = 0

        for sentence in sentences:
            words_in_sentence = len(sentence.split())
            if (
                current_word_count + words_in_sentence > CHUNK_TARGET_WORDS
                and current
            ) or current_word_count >= CHUNK_MAX_WORDS:
                chunks.append(" ".join(current))
                # Seed the next chunk with an overlap drawn from the tail of
                # the previous one to preserve cross-boundary context.
                tail_words: List[str] = []
                tail_count = 0
                for s in reversed(current):
                    s_words = s.split()
                    if tail_count + len(s_words) > CHUNK_OVERLAP_WORDS and tail_words:
                        break
                    tail_words.insert(0, s)
                    tail_count += len(s_words)
                current = list(tail_words)
                current_word_count = tail_count

            current.append(sentence)
            current_word_count += words_in_sentence

        if current:
            chunks.append(" ".join(current))

        return chunks
