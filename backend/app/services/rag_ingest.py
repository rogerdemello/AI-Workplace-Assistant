import hashlib
import logging
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

from ..models.document import Document, DocumentChunk
from ..ai_client import get_ai_client

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100


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
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + CHUNK_SIZE
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - CHUNK_OVERLAP
        
        return chunks
