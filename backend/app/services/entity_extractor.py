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
    matched_type: Optional[str] = None
    if re.search(r"\b(sick|ill|medical)\b", low):
        matched_type = "sick"
    elif re.search(r"\b(wfh|work from home|working from home|remote)\b", low):
        matched_type = "work from home"
    elif re.search(r"\b(unpaid|personal|bereavement|parental)\b", low):
        matched_type = "personal"
    elif re.search(r"\b(paid|pto|annual|vacation|holiday|time off)\b", low):
        matched_type = "vacation"

    # The slot the flow is actually waiting on, based on already-collected data.
    pending_slot = first_missing_leave_slot(cd)

    # Only adopt a type keyword as leave_type while the flow is still collecting
    # the type. At the reason step a word like "vacation" in "going on a vacation"
    # belongs to the reason, not a type selection — otherwise the reason is never
    # captured and the flow loops re-asking for it.
    if matched_type and pending_slot != "reason":
        out["leave_type"] = matched_type

    looks_like_date_only = len(dates) == 1 and bool(re.fullmatch(r"\s*" + re.escape(dates[0]) + r"\s*", text))
    if (
        pending_slot == "reason"
        and out["start_date"] is None
        and out["end_date"] is None
        and len(text) > 12
        and not looks_like_date_only
        and not re.match(r"^(yes|no|yeah|yep|ok|okay|sure)\b", low)
    ):
        out["reason"] = text.strip()

    return out


#: Ordered slots per conversational request flow — the order the flow asks in.
REQUEST_FIELDS: Dict[str, list] = {
    "appointment_request": ["topic", "preferred_date", "preferred_time", "mode"],
    "expense_claim": ["expense_type", "amount", "expense_date", "description"],
    "shift_change_request": ["change_type", "start_date", "end_date", "reason"],
    "document_request": ["document_type", "purpose"],
}

#: Date slots per flow, in the order they should absorb dates found in a message.
_REQUEST_DATE_SLOTS: Dict[str, list] = {
    "appointment_request": ["preferred_date"],
    "expense_claim": ["expense_date"],
    "shift_change_request": ["start_date", "end_date"],
    "document_request": [],
}

#: Free-text slots — when the flow is waiting on one of these, the whole message is the answer.
_REQUEST_FREE_TEXT_SLOTS = {"topic", "description", "reason", "purpose"}

_TIME_TEXT = re.compile(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|(?:[01]?\d|2[0-3]):[0-5]\d)\b", re.IGNORECASE)
_AMOUNT_TEXT = re.compile(r"(?:[₹$€£]\s*)?(\d[\d,]*(?:\.\d{1,2})?)")

_ENUM_KEYWORDS: Dict[str, list] = {
    "mode": [
        (r"\b(in[-\s]?person|face[-\s]?to[-\s]?face|onsite|in\s+office)\b", "in person"),
        (r"\b(video|zoom|teams|google\s+meet|gmeet|vc)\b", "video"),
        (r"\b(call|phone|dial)\b", "call"),
    ],
    "expense_type": [
        (r"\b(travel|cab|taxi|flight|train|mileage|fuel|hotel|lodging)\b", "travel"),
        (r"\b(meal|food|lunch|dinner|breakfast|client\s+dinner)\b", "meals"),
        (r"\b(laptop|monitor|keyboard|mouse|equipment|hardware|desk|chair)\b", "equipment"),
        (r"\b(course|training|certification|conference|workshop|book)\b", "training"),
        (r"\b(internet|broadband|phone\s+bill|mobile\s+bill)\b", "connectivity"),
    ],
    "change_type": [
        (r"\b(wfh|work\s+from\s+home|working\s+from\s+home|remote|remotely)\b", "work from home"),
        (r"\b(swap|switch|shift\s+change|change\s+my\s+shift|roster)\b", "shift change"),
    ],
    "document_type": [
        (r"\b(pay\s?slip|salary\s+slip)\b", "payslip"),
        (r"\b(form\s*16|tax\s+(document|certificate|form)|tds)\b", "tax document"),
        (r"\b(employment\s+letter|employment\s+verification|address\s+proof)\b", "employment letter"),
        (r"\b(experience\s+letter|relieving\s+letter|service\s+certificate)\b", "experience letter"),
        (r"\b(salary\s+certificate|income\s+certificate|loan\s+letter)\b", "salary certificate"),
        (r"\b(offer\s+letter)\b", "offer letter"),
    ],
}


def _first_missing_request_slot(flow_name: str, current_data: Optional[Dict[str, Any]]) -> Optional[str]:
    data = current_data or {}
    for field in REQUEST_FIELDS.get(flow_name, []):
        value = data.get(field)
        if value is None:
            return field
        if isinstance(value, str) and (not value.strip() or value.strip().lower() == "unspecified"):
            return field
    return None


def _match_enum_slot(slot: str, text: str) -> Optional[str]:
    for pattern, label in _ENUM_KEYWORDS.get(slot, []):
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return None


def _heuristic_request_entities(
    flow_name: str,
    message: str,
    current_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[Any]]:
    """Rule-based slot extraction for the request flows — no LLM round-trip needed."""
    fields = REQUEST_FIELDS.get(flow_name, [])
    out: Dict[str, Optional[Any]] = {field: None for field in fields}
    text = (message or "").strip()
    if not text:
        return out

    cd = current_data or {}
    pending = _first_missing_request_slot(flow_name, cd)

    # Enum-ish slots: only adopt a keyword while that slot is still unfilled, so a
    # word like "travel" in a description doesn't overwrite the chosen type.
    for slot in fields:
        if slot not in _ENUM_KEYWORDS:
            continue
        if not _slot_missing(cd.get(slot)):
            continue
        matched = _match_enum_slot(slot, text)
        if matched:
            out[slot] = matched

    # Dates fill the flow's date slots left to right, skipping ones already set.
    date_slots = [s for s in _REQUEST_DATE_SLOTS.get(flow_name, []) if _slot_missing(cd.get(s))]
    found_dates = _ISO_DATE.findall(text)
    for slot, value in zip(date_slots, found_dates):
        out[slot] = value

    if "preferred_time" in fields and _slot_missing(cd.get("preferred_time")):
        time_match = _TIME_TEXT.search(text)
        if time_match:
            out["preferred_time"] = time_match.group(1)

    if "amount" in fields and _slot_missing(cd.get("amount")):
        # Skip anything that already parsed as a date so "2024-01-05" isn't an amount.
        amount_text = _ISO_DATE.sub(" ", text)
        amount_match = _AMOUNT_TEXT.search(amount_text)
        if amount_match:
            out["amount"] = amount_match.group(1)

    # Free-text slot the flow is currently waiting on takes the whole message.
    if (
        pending in _REQUEST_FREE_TEXT_SLOTS
        and out.get(pending) is None
        and not re.match(r"^(yes|no|yeah|yep|nope|ok|okay|sure)\b", text.lower())
    ):
        stripped = _ISO_DATE.sub("", text).strip(" ,.-")
        if len(stripped) >= 3:
            out[pending] = text.strip()

    return out


def _slot_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip()
        return not s or s.lower() == "unspecified"
    return False


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
    
    def extract_request_entities(
        self,
        flow_name: str,
        message: str,
        current_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Optional[Any]]:
        """
        Extract slots for an appointment / expense / shift-change / document request.

        Heuristics run first and win when they find anything, so the common phrasings
        stay LLM-free; the model only fills the gaps for unusual wording.
        """
        fields = REQUEST_FIELDS.get(flow_name, [])
        if not fields:
            return {}

        heuristic = _heuristic_request_entities(flow_name, message, current_data)
        if _fast_chat_enabled() and any(v is not None for v in heuristic.values()):
            return heuristic

        prompt = f"""Extract {flow_name.replace('_', ' ')} details from this message.

Message: "{message}"

Return ONLY a JSON object with these fields (null if not mentioned):
- {", ".join(fields)}

Dates must be ISO format (YYYY-MM-DD). Times must be 24-hour HH:MM. Amounts must be plain numbers.

Return ONLY the JSON, no other text."""

        try:
            response = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You extract structured data from user messages. Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            content = response["choices"][0]["message"]["content"]
            result = json.loads(content.strip())
        except Exception as e:
            logger.warning(f"Request entity extraction failed for {flow_name}: {e}")
            return heuristic

        # Heuristics are the more reliable signal for the slots they resolve.
        return {
            field: heuristic.get(field) if heuristic.get(field) is not None else result.get(field)
            for field in fields
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


__all__ = ["EntityExtractor", "get_entity_extractor", "REQUEST_FIELDS"]
