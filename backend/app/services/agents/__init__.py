"""MARK specialized agents — thin domain modules consumed by chat orchestration."""

from .base import AgentContext, AgentName, AgentResult
from .hr_agent import HrAgent
from .life_agent import LifeAgent
from .productivity_agent import ProductivityAgent
from .analysis_agent import AnalysisAgent
from .emotional_agent import EmotionalAgent
from .proactive_agent import ProactiveAgent

__all__ = [
    "AgentContext",
    "AgentName",
    "AgentResult",
    "HrAgent",
    "LifeAgent",
    "ProductivityAgent",
    "AnalysisAgent",
    "EmotionalAgent",
    "ProactiveAgent",
]
