from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.auth import get_hr_context
from ..services.supabase_client import supabase_or_503

router = APIRouter(prefix="/employees", tags=["hr-employees"])


@router.get("")
def get_employees(user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    return supabase.table("employee_insights").select("*").execute().data or []


@router.get("/{employee_id}")
def get_employee_detail(employee_id: str, user: dict = Depends(get_hr_context)):
    supabase = supabase_or_503()
    insights = (
        supabase.table("employee_insights")
        .select("*")
        .eq("employee_id", employee_id)
        .execute()
        .data
        or []
    )
    tickets = (
        supabase.table("tickets")
        .select("*")
        .eq("user_id", employee_id)
        .execute()
        .data
        or []
    )
    return {
        "insights": insights,
        "tickets": tickets,
    }
