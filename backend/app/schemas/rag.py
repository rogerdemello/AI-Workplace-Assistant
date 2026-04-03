from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    id: UUID
    title: str
    chunks: int
    status: str
    
    class Config:
        from_attributes = True


class DocumentChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    id: UUID
    title: str
    is_active: bool
    created_at: datetime
    chunks_count: int = 0
    
    class Config:
        from_attributes = True


class DocumentDetailResponse(BaseModel):
    id: UUID
    title: str
    file_path: str
    is_active: bool
    created_at: datetime
    chunks_count: int = 0
    
    class Config:
        from_attributes = True
