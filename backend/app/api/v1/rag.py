from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from sqlalchemy.orm import Session
import tempfile
import os
from typing import List, Optional
from uuid import UUID
import logging

from ...database import get_db
from ...core.feature_flags import get_feature_flags
from ...schemas.rag import DocumentUploadResponse, DocumentListResponse, DocumentDetailResponse
from ...auth import get_current_user, require_roles
from ...models.user import User
from ...models.document import Document
from ...services.rag_ingest import RAGIngestService
from ...services.rag_retrieve import RAGRetrieveService
from ...services.rag import RAGOrchestrator

router = APIRouter(prefix="/rag", tags=["rag"])
logger = logging.getLogger(__name__)


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str = None,
    current_user: User = Depends(require_roles(["hr", "admin"])),
    db: Session = Depends(get_db)
):
    if not title:
        title = file.filename
    
    if not (file.filename.endswith('.pdf') or file.filename.endswith('.docx')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX files are supported"
        )
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        service = RAGIngestService(db, current_user.id)
        document = service.process_document(tmp_path, title)
        
        return DocumentUploadResponse(
            id=document.id,
            title=document.title,
            chunks=len(document.chunks),
            status="processed"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}"
        )
    finally:
        os.unlink(tmp_path)


@router.get("/documents", response_model=List[DocumentListResponse])
def list_documents(
    current_user: User = Depends(require_roles(["hr", "admin"])),
    db: Session = Depends(get_db)
):
    documents = db.query(Document).filter(Document.is_active == True).all()
    return [
        DocumentListResponse(
            id=doc.id,
            title=doc.title,
            is_active=doc.is_active,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            chunks_count=len(doc.chunks)
        )
        for doc in documents
    ]


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: UUID,
    current_user: User = Depends(require_roles(["hr", "admin"])),
    db: Session = Depends(get_db)
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        file_path=document.file_path,
        is_active=document.is_active,
        created_at=document.created_at,
        chunks_count=len(document.chunks)
    )


@router.patch("/documents/{document_id}/active", response_model=DocumentDetailResponse)
def set_document_active_state(
    document_id: UUID,
    is_active: bool = Query(..., description="Enable/disable this document for retrieval"),
    current_user: User = Depends(require_roles(["hr", "admin"])),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    document.is_active = is_active
    db.commit()
    db.refresh(document)
    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        file_path=document.file_path,
        is_active=document.is_active,
        created_at=document.created_at,
        chunks_count=len(document.chunks),
    )


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: UUID,
    current_user: User = Depends(require_roles(["hr", "admin"])),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db.delete(document)
    db.commit()
    return {"ok": True}


@router.post("/search")
def search_documents(
    query: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(3, ge=1, le=20, description="Maximum number of results"),
    threshold: float = Query(0.7, ge=0.0, le=1.0, description="Minimum similarity threshold"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search documents using semantic search with hybrid (vector + keyword) matching.
    
    Returns top-k relevant document chunks with similarity scores.
    """
    if not get_feature_flags().enable_rag:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Policy knowledge base is disabled by configuration",
        )

    service = RAGRetrieveService(db)
    try:
        results = service.search(query, top_k=top_k, threshold=threshold)
    except Exception as exc:
        logger.exception("RAG search failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Policy knowledge base is temporarily unavailable: {exc}",
        ) from exc
    
    return {
        "query": query,
        "count": len(results),
        "results": results
    }


@router.post("/search-with-answer")
def search_with_answer(
    query: str = Query(..., min_length=1, description="Search query"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search documents and generate an answer with citations.
    
    Returns answer with source citations for HR assistant.
    """
    if not get_feature_flags().enable_rag:
        return {
            "answer": "Policy knowledge base is disabled by configuration.",
            "citations": [],
            "sources": [],
            "source": "disabled",
        }

    try:
        retrieve_service = RAGRetrieveService(db)
        orchestrator = RAGOrchestrator(db=db, retrieve_service=retrieve_service)
        return orchestrator.ask(query)
    except Exception as exc:
        logger.exception("RAG answer generation failed")
        return {
            "answer": (
                "Policy knowledge base is temporarily unavailable. "
                "Please check with HR while we restore document search."
            ),
            "citations": [],
            "sources": [],
            "source": "fallback",
            "error": str(exc),
        }
