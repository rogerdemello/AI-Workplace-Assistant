import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile
from sqlalchemy.orm import Session
from typing import Optional

from ...database import get_db
from ...schemas.attachment import AttachmentResponse, AttachmentEntityType
from ...auth import get_current_user
from ...models.user import User
from ...models.attachment import Attachment

router = APIRouter(prefix="/attachments", tags=["attachments"])

# Upload directory - relative to backend root
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"


def get_upload_dir() -> Path:
    """Get/create uploads directory."""
    upload_path = UPLOAD_DIR
    if not upload_path.exists():
        upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


def save_file(file: UploadFile, dest_dir: Path) -> tuple[str, str, int]:
    """
    Save uploaded file to destination directory.
    Returns: (saved_filename, file_type, file_size)
    """
    # Generate unique filename to avoid conflicts
    filename = file.filename if file.filename else ""
    file_ext = Path(filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = dest_dir / unique_filename
    
    # Read file content
    content = file.file.read()
    file_size = len(content)
    
    # Write to disk
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Get content type
    file_type = file.content_type or "application/octet-stream"
    
    return unique_filename, file_type, file_size


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile,
    entity_type: AttachmentEntityType,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a file attachment for a ticket or leave request.
    
    - **file**: The file to upload
    - **entity_type**: Type of entity (ticket or leave_request)
    - **entity_id**: ID of the associated entity
    """
    # Validate entity exists based on entity_type
    if entity_type == AttachmentEntityType.ticket:
        from ...models.ticket import Ticket
        entity = db.query(Ticket).filter(Ticket.id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="Ticket not found")
    elif entity_type == AttachmentEntityType.leave_request:
        from ...models.leave_request import LeaveRequest
        entity = db.query(LeaveRequest).filter(LeaveRequest.id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="Leave request not found")
    
    # Save file to disk
    upload_dir = get_upload_dir()
    saved_filename, file_type, file_size = save_file(file, upload_dir)
    
    # Create relative path for storage
    file_path = f"/uploads/{saved_filename}"
    
    # Create attachment record
    attachment = Attachment(
        id=uuid.uuid4(),
        user_id=current_user.id,
        file_name=file.filename or "unnamed",
        file_type=file_type,
        file_size=file_size,
        file_path=file_path,
        entity_type=entity_type,
        entity_id=entity_id
    )
    
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    
    return attachment
