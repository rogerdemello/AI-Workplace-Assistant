from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...auth import require_roles
from ...database import get_db
from ...models.user import User
from ...services.automation_rules import AutomationRulesService

router = APIRouter(prefix="/automations", tags=["automations"])


class AutomationRuleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    event_type: str = Field(default="ticket_created", max_length=60)
    conditions: dict[str, Any] = Field(default_factory=dict)
    actions: dict[str, Any] = Field(default_factory=dict)


class AutomationRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    enabled: bool | None = None
    conditions: dict[str, Any] | None = None
    actions: dict[str, Any] | None = None


class AutomationRuleResponse(BaseModel):
    id: str
    name: str
    event_type: str
    enabled: bool
    conditions: dict[str, Any]
    actions: dict[str, Any]
    created_by: str | None
    created_at: str
    updated_at: str


def _to_response(rule) -> AutomationRuleResponse:
    return AutomationRuleResponse(
        id=str(rule.id),
        name=rule.name,
        event_type=rule.event_type,
        enabled=bool(rule.enabled),
        conditions=rule.conditions or {},
        actions=rule.actions or {},
        created_by=str(rule.created_by) if rule.created_by else None,
        created_at=rule.created_at.isoformat() if rule.created_at else "",
        updated_at=rule.updated_at.isoformat() if rule.updated_at else "",
    )


@router.get("/rules", response_model=list[AutomationRuleResponse])
def list_rules(
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    service = AutomationRulesService(db)
    return [_to_response(rule) for rule in service.list_rules()]


@router.post("/rules", response_model=AutomationRuleResponse)
def create_rule(
    payload: AutomationRuleCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(["hr", "admin"])),
):
    service = AutomationRulesService(db)
    rule = service.create_rule(
        name=payload.name,
        event_type=payload.event_type,
        conditions=payload.conditions,
        actions=payload.actions,
        created_by=actor.id,
    )
    return _to_response(rule)


@router.patch("/rules/{rule_id}", response_model=AutomationRuleResponse)
def update_rule(
    rule_id: UUID,
    payload: AutomationRuleUpdate,
    db: Session = Depends(get_db),
    _hr: User = Depends(require_roles(["hr", "admin"])),
):
    service = AutomationRulesService(db)
    rule = service.update_rule(
        rule_id,
        name=payload.name,
        enabled=payload.enabled,
        conditions=payload.conditions,
        actions=payload.actions,
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _to_response(rule)
