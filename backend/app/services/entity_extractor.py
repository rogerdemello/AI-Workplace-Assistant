"""
Entity extraction service for slot filling in conversation flows.
Extracts structured data (department, issue, severity, etc.) from user messages.
"""

from typing import Any, Dict, Optional
import json
import logging
import re

from ..config import settings
from ..ai_client import get_ai_client, AzureOpenAIClient, MockAzureOpenAIClient
from .chat.state_machine import first_missing_leave_slot, infer_leave_patch_from_text

logger = logging.getLogger(__name__)


def _fast_chat_enabled() -> bool:
    return bool(settings.FAST_CHAT_MODE)


_ISO_DATE = re.compile(
    r"\b(20[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))\b"
)


def _parse_iso_date_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() == "unspecified":
            return None
        if _ISO_DATE.fullmatch(s):
            return s
        if _ISO_DATE.search(s):
            return _ISO_DATE.search(s).group(1)
    return None


def _has_date_slot(current_data: Optional[Dict[str, Any]], key: str) -> bool:
    return _parse_iso_date_str((current_data or {}).get(key)) is not None


def _heuristic_leave_entities(
    message: str,
    current_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    """Rule-based extraction — avoids an Azure round-trip per leave-flow turn when FAST_CHAT_MODE is on."""
    out: Dict[str, Optional[str]] = {
        "leave_type": None,
        "start_date": None,
        "end_date": None,
        "reason": None,
    }
    text = (message or "").strip()
    if not text:
        return out

    cd = current_data or {}

    # Deterministic date routing (first missing start → then end)
    for key, val in infer_leave_patch_from_text(text, cd).items():
        if val:
            out[key] = val

    dates = _ISO_DATE.findall(text)
    if len(dates) >= 2 and out.get("start_date") is None:
        out["start_date"], out["end_date"] = dates[0], dates[1]
    elif len(dates) == 1 and out.get("start_date") is None and out.get("end_date") is None:
        d0 = dates[0]
        has_start = _has_date_slot(cd, "start_date")
        has_end = _has_date_slot(cd, "end_date")
        if not has_start:
            out["start_date"] = d0
        elif not has_end:
            out["end_date"] = d0
        else:
            out["end_date"] = d0

    low = text.lower()
    if re.search(r"\b(sick|ill|medical)\b", low):
        out["leave_type"] = "sick"
    elif re.search(r"\b(wfh|work from home|working from home|remote)\b", low):
        out["leave_type"] = "work from home"
    elif re.search(r"\b(unpaid|personal|bereavement|parental)\b", low):
        out["leave_type"] = "personal"
    elif re.search(r"\b(paid|pto|annual|vacation|holiday|time off)\b", low):
        out["leave_type"] = "vacation"

    looks_like_date_only = len(dates) == 1 and bool(re.fullmatch(r"\s*" + re.escape(dates[0]) + r"\s*", text))
    next_slot = first_missing_leave_slot({**cd, **{k: v for k, v in out.items() if v}})
    if (
        next_slot == "reason"
        and out["start_date"] is None
        and out["end_date"] is None
        and out["leave_type"] is None
        and len(text) > 12
        and not looks_like_date_only
        and not re.match(r"^(yes|no|yeah|yep|ok|okay|sure)\b", low)
    ):
        out["reason"] = text.strip()

    return out


class EntityExtractor:
    """
    Extracts structured entities from user messages using LLM.
    Supports slot filling for different flow types.
    """
    
    TICKET_FIELDS = ["department", "issue", "severity", "anonymous", "against", "timeline", "details"]
    LEAVE_FIELDS = ["leave_type", "start_date", "end_date", "reason"]
    
    def __init__(self, use_mock: bool = False):
        self.ai_client = get_ai_client(use_mock=use_mock)
    
    def extract_ticket_entities(self, message: str) -> Dict[str, Optional[str]]:
        """
        Extract ticket-related entities from user message.
        
        Returns:
            Dict with keys: department, issue, severity, anonymous
        """
        prompt = f"""Extract ticket information from this message.

Message: "{message}"

Return ONLY a JSON object with these fields (null if not mentioned):
- department: "HR", "IT", "Facilities", "Finance", "Management", or null
- issue: brief description of the problem (or null if unclear)
- severity: "low", "medium", "high", "critical", or null  
- anonymous: true/false (whether they want to stay anonymous)
- against: who the complaint is about (person's name/role) or null
- timeline: when the issue started (brief description) or null
- details: additional context or background information or null

Example: {{"department": "HR", "issue": "manager not respecting work hours", "severity": "medium", "anonymous": false, "against": "team lead", "timeline": "last week", "details": "always making me stay late"}}

Return ONLY the JSON, no other text."""

        try:
            response = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You extract structured data from user messages. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            content = response["choices"][0]["message"]["content"]
            
            result = json.loads(content.strip())
            
            return {
                "department": result.get("department"),
                "issue": result.get("issue"),
                "severity": result.get("severity"),
                "anonymous": result.get("anonymous"),
                "against": result.get("against"),
                "timeline": result.get("timeline"),
                "details": result.get("details")
            }
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return {
                "department": None,
                "issue": None,
                "severity": None,
                "anonymous": None,
                "against": None,
                "timeline": None,
                "details": None
            }
    
    def extract_leave_entities(
        self,
        message: str,
        current_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Extract leave request entities from user message.
        
        Returns:
            Dict with keys: leave_type, start_date, end_date, reason
        """
        if _fast_chat_enabled():
            quick = _heuristic_leave_entities(message, current_data)
            if any(v is not None for v in quick.values()):
                return quick

        prompt = f"""Extract leave request information from this message.

Message: "{message}"

Return ONLY a JSON object with these fields (null if not mentioned):
- leave_type: "vacation", "sick", "personal", "bereavement", "parental", or null
- start_date: ISO date format or null
- end_date: ISO date format or null  
- reason: brief reason for leave (or null)

Example: {{"leave_type": "vacation", "start_date": "2024-12-23", "end_date": "2024-12-27", "reason": "family trip"}}

Return ONLY the JSON, no other text."""

        try:
            response = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You extract structured data from user messages. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            content = response["choices"][0]["message"]["content"]
            
            result = json.loads(content.strip())
            
            return {
                "leave_type": result.get("leave_type"),
                "start_date": result.get("start_date"),
                "end_date": result.get("end_date"),
                "reason": result.get("reason")
            }
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return {
                "leave_type": None,
                "start_date": None,
                "end_date": None,
                "reason": None
            }
    
    def extract_generic(self, message: str, fields: list) -> Dict[str, Optional[str]]:
        """
        Extract generic entities based on provided field list.
        
        Args:
            message: User message
            fields: List of field names to extract
            
        Returns:
            Dict mapping field names to extracted values
        """
        fields_str = ", ".join(fields)
        
        prompt = f"""Extract information from this message.

Message: "{message}"

Return ONLY a JSON object with these fields (null if not mentioned):
- {fields_str}

Return ONLY the JSON, no other text."""

        try:
            response = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You extract structured data from user messages. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            content = response["choices"][0]["message"]["content"]
            result = json.loads(content.strip())
            
            return {field: result.get(field) for field in fields}
        except Exception as e:
            logger.warning(f"Generic entity extraction failed: {e}")
            return {field: None for field in fields}


def get_entity_extractor(use_mock: bool = False) -> EntityExtractor:
    """Factory function to create EntityExtractor instance."""
    return EntityExtractor(use_mock=use_mock)


__all__ = ["EntityExtractor", "get_entity_extractor"]
