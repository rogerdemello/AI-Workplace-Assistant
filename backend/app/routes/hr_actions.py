from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..core.auth import get_hr_context
from ..services.supabase_client import supabase_or_503

router = APIRouter(prefix="/actions", tags=["hr-actions"])


class CreateActionBody(BaseModel):
    employee_id: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1, max_length=128)


@router.post("")
def create_action(body: CreateActionBody, user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    return (
        supabase.table("actions")
        .insert(
            {
                "employee_id": body.employee_id,
                "action_type": body.action,
                "status": "pending",
            }
        )
        .execute()
        .data
    )


@router.get("")
def get_actions(user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    return supabase.table("actions").select("*").execute().data or []
