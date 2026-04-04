"""
Entity extraction service for slot filling in conversation flows.
Extracts structured data (department, issue, severity, etc.) from user messages.
"""

from typing import Dict, Optional
import json
import logging

from ..ai_client import get_ai_client, AzureOpenAIClient, MockAzureOpenAIClient

logger = logging.getLogger(__name__)


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
    
    def extract_leave_entities(self, message: str) -> Dict[str, Optional[str]]:
        """
        Extract leave request entities from user message.
        
        Returns:
            Dict with keys: leave_type, start_date, end_date, reason
        """
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
