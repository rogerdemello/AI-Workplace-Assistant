from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    id: UUID
    title: str
    chunks: int
    status: str
    
    model_config = ConfigDict(from_attributes=True)


class DocumentChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    
    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    id: UUID
    title: str
    is_active: bool
    created_at: datetime
    chunks_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(BaseModel):
    id: UUID
    title: str
    file_path: str
    is_active: bool
    created_at: datetime
    chunks_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)
