from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.auth import get_hr_context
from ..services.supabase_client import supabase_or_503

router = APIRouter(prefix="/tickets", tags=["hr-tickets"])


class TicketStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=64)


class TicketCommentBody(BaseModel):
    comment: str = Field(..., min_length=1, max_length=8000)


@router.get("")
def get_tickets(user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    return supabase.table("tickets").select("*").execute().data or []


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: str,
    body: TicketStatusUpdate,
    user: dict = Depends(get_hr_context),
):
    supabase = supabase_or_503()
    res = (
        supabase.table("tickets")
        .update({"status": body.status})
        .eq("id", ticket_id)
        .execute()
    )
    data = getattr(res, "data", None)
    if data is None and isinstance(res, dict):
        data = res.get("data")
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found or not updated",
        )
    return data


@router.post("/{ticket_id}/comment")
def add_comment(
    ticket_id: str,
    body: TicketCommentBody,
    user: dict = Depends(get_hr_context),
):
    supabase = supabase_or_503()
    return (
        supabase.table("ticket_comments")
        .insert(
            {
                "ticket_id": ticket_id,
                "comment": body.comment,
            }
        )
        .execute()
        .data
    )
