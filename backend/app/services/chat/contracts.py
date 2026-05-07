"""Typed contracts for conversation flow and multi-agent orchestration."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field

from ..agents.base import AgentName


class FlowStateContract(BaseModel):
    """Canonical state shape persisted for multi-turn flows."""

    intent: str
    step: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    completed: bool = False
    last_question: Optional[str] = None

    @classmethod
    def from_state(cls, state: Optional[Dict[str, Any]], *, intent: str) -> "FlowStateContract":
        payload = state or {}
        data = payload.get("data")
        return cls(
            intent=intent,
            step=payload.get("step"),
            data=data if isinstance(data, dict) else {},
            completed=bool(payload.get("completed", False)),
            last_question=payload.get("last_question"),
        )


class AgentTurnContext(BaseModel):
    """Immutable summary of one orchestrator turn for supplementary agents."""

    message: str
    intent: str
    sentiment: str
    user_id: UUID
    active_flow: Optional[str] = None
    conversation_mode: Optional[str] = None


class AgentRoutingDecision(BaseModel):
    intent: str
    agents: List[str] = Field(default_factory=list)
    entities: Dict[str, Any] = Field(default_factory=dict)
    priority: str = "low"
    multi_agent: bool = False


class MultiAgentPlanContract(BaseModel):
    supplementary: Tuple[AgentName, ...] = ()
    decision: AgentRoutingDecision


class AgentExecutionEnvelope(BaseModel):
    requested_agents: List[str] = Field(default_factory=list)
    successful_agents: List[str] = Field(default_factory=list)
    failed_agents: List[str] = Field(default_factory=list)
    has_failures: bool = False

