"""Shared types for MARK multi-agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID


class AgentName(str, Enum):
    HR = "hr"
    LIFE = "life"
    PRODUCTIVITY = "productivity"
    ANALYSIS = "analysis"
    EMOTIONAL = "emotional"
    PROACTIVE = "proactive"


@dataclass
class AgentContext:
    """Mutable view of one user turn for specialist agents."""

    message: str
    intent: str
    sentiment: str
    user_id: UUID
    orchestrator: Any  # ConversationOrchestrator — provides .service (SmartChatService)


@dataclass
class AgentResult:
    agent: AgentName
    handled: bool
    payload: Dict[str, Any] = field(default_factory=dict)
    reply_prefix: Optional[str] = None
    reply_suffix: Optional[str] = None
