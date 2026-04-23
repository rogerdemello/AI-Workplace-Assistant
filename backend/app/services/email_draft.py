from typing import Dict, Optional, Any
from uuid import UUID
from sqlalchemy.orm import Session
from ..ai_client import get_ai_client
from ..config import settings

EMAIL_TYPES = ["leave_request", "follow_up", "complaint", "resignation", "general"]
TONES = ["formal", "neutral", "friendly"]


class EmailDraftService:
    def __init__(self, db: Optional[Session] = None, user_id: Optional[UUID] = None, use_mock: Optional[bool] = None):
        self.db = db
        self.user_id = user_id

        if use_mock is None:
            has_real_config = (
                bool(settings.AZURE_OPENAI_API_KEY)
                and settings.AZURE_OPENAI_API_KEY != "mock-key"
                and bool(settings.AZURE_OPENAI_ENDPOINT)
                and "mock" not in settings.AZURE_OPENAI_ENDPOINT.lower()
            )
            use_mock = not has_real_config

        self.ai_client = get_ai_client(use_mock=use_mock)
    
    def generate_draft(
        self,
        email_type: str,
        tone: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if tone not in TONES:
            raise ValueError(f"Invalid tone. Must be one of: {TONES}")
        
        if email_type not in EMAIL_TYPES:
            raise ValueError(f"Invalid email type. Must be one of: {EMAIL_TYPES}")
        
        context = context or {}
        
        prompt = self._build_prompt(email_type, tone, context)
        
        response = self.ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are an expert email writer. Generate professional workplace emails."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        content = response["choices"][0]["message"]["content"]
        
        # Parse subject and body
        lines = content.split("\n", 1)
        subject = lines[0].replace("Subject:", "").strip() if lines else "Email Draft"
        body = lines[1] if len(lines) > 1 else content
        
        result = {
            "subject": subject,
            "body": body.strip(),
            "tone": tone,
            "type": email_type,
            "context": context
        }
        
        # Store in database if db provided
        if self.db and self.user_id:
            result["draft_id"] = self._save_draft(result)
        
        return result
    
    def _build_prompt(self, email_type: str, tone: str, context: Dict[str, Any]) -> str:
        templates = {
            "leave_request": "Write a leave request email",
            "follow_up": "Write a follow-up email",
            "complaint": "Write a workplace complaint email",
            "resignation": "Write a resignation notice email",
            "general": "Write a workplace email"
        }
        
        tone_guidance = {
            "formal": "Use formal language, professional greetings, and polite phrases",
            "neutral": "Use neutral, clear language without being too formal or casual",
            "friendly": "Use friendly, conversational tone while remaining professional"
        }
        
        prompt = templates[email_type]
        prompt += f". Use a {tone} tone."
        
        if context.get("manager"):
            prompt += f" The recipient is {context['manager']}."
        
        if context.get("department"):
            prompt += f" Department: {context['department']}."
        
        if context.get("dates"):
            prompt += f" Relevant dates: {context['dates']}."
        
        if context.get("additional_info"):
            prompt += f" Additional context: {context['additional_info']}."
        
        prompt += f"\n\nFormat as: Subject: <subject>\n\n<body>"
        
        return prompt
    
    def _save_draft(self, draft: Dict[str, Any]) -> UUID:
        # Simplified - would normally save to email_logs table
        return UUID('00000000-0000-0000-0000-000000000001')
