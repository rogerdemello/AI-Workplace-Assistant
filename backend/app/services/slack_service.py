import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models.webhook import SlackIntegration
from ..core.time import utcnow_naive


class SlackService:
    SLACK_API_URL = "https://slack.com/api"
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_integration(self, user_id: UUID) -> Optional[SlackIntegration]:
        return self.db.query(SlackIntegration).filter(
            SlackIntegration.user_id == user_id
        ).first()
    
    def connect(
        self,
        user_id: UUID,
        slack_user_id: str,
        slack_team_id: str,
        access_token: str
    ) -> SlackIntegration:
        integration = self.get_user_integration(user_id)
        
        if integration:
            integration.slack_user_id = slack_user_id
            integration.slack_team_id = slack_team_id
            integration.access_token = access_token
            integration.is_active = True
        else:
            integration = SlackIntegration(
                user_id=user_id,
                slack_user_id=slack_user_id,
                slack_team_id=slack_team_id,
                access_token=access_token
            )
            self.db.add(integration)
        
        self.db.commit()
        self.db.refresh(integration)
        return integration
    
    def disconnect(self, user_id: UUID) -> bool:
        integration = self.get_user_integration(user_id)
        if not integration:
            return False
        
        integration.is_active = False
        integration.access_token = None
        self.db.commit()
        return True
    
    def update_settings(
        self,
        user_id: UUID,
        notify_on_mood: Optional[bool] = None,
        notify_on_appreciation: Optional[bool] = None,
        notify_on_tickets: Optional[bool] = None,
        notify_on_calendar: Optional[bool] = None,
        notify_on_leave: Optional[bool] = None,
        dm_enabled: Optional[bool] = None,
        channel_notifications: Optional[bool] = None,
        notification_channel: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Dict]:
        integration = self.get_user_integration(user_id)
        if not integration:
            return None
        
        if notify_on_mood is not None:
            integration.notify_on_mood = notify_on_mood
        if notify_on_appreciation is not None:
            integration.notify_on_appreciation = notify_on_appreciation
        if notify_on_tickets is not None:
            integration.notify_on_tickets = notify_on_tickets
        if notify_on_calendar is not None:
            integration.notify_on_calendar = notify_on_calendar
        if notify_on_leave is not None:
            integration.notify_on_leave = notify_on_leave
        if dm_enabled is not None:
            integration.dm_enabled = dm_enabled
        if channel_notifications is not None:
            integration.channel_notifications = channel_notifications
        if notification_channel is not None:
            integration.notification_channel = notification_channel
        if is_active is not None:
            integration.is_active = is_active
        
        self.db.commit()
        self.db.refresh(integration)
        
        return {
            "id": str(integration.id),
            "user_id": str(integration.user_id),
            "slack_user_id": integration.slack_user_id,
            "slack_team_id": integration.slack_team_id,
            "is_active": integration.is_active,
            "notify_on_mood": integration.notify_on_mood,
            "notify_on_appreciation": integration.notify_on_appreciation,
            "notify_on_tickets": integration.notify_on_tickets,
            "notify_on_calendar": integration.notify_on_calendar,
            "notify_on_leave": integration.notify_on_leave,
            "dm_enabled": integration.dm_enabled,
            "channel_notifications": integration.channel_notifications,
            "notification_channel": integration.notification_channel,
            "created_at": integration.created_at.isoformat(),
            "updated_at": integration.updated_at.isoformat()
        }
    
    async def send_dm(
        self,
        user_id: UUID,
        text: str,
        blocks: Optional[List[Dict]] = None
    ) -> bool:
        integration = self.get_user_integration(user_id)
        if not integration or not integration.is_active or not integration.dm_enabled:
            return False
        
        if not integration.access_token or not integration.slack_user_id:
            return False
        
        url = f"{self.SLACK_API_URL}/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {integration.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "channel": integration.slack_user_id,
            "text": text
        }
        
        if blocks:
            payload["blocks"] = blocks
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=30.0)
                return response.status_code == 200
        except Exception:
            return False
    
    async def send_channel_message(
        self,
        user_id: UUID,
        channel_id: str,
        text: str,
        blocks: Optional[List[Dict]] = None
    ) -> bool:
        integration = self.get_user_integration(user_id)
        if not integration or not integration.is_active:
            return False
        
        if not integration.access_token:
            return False
        
        url = f"{self.SLACK_API_URL}/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {integration.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "channel": channel_id,
            "text": text
        }
        
        if blocks:
            payload["blocks"] = blocks
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=30.0)
                return response.status_code == 200
        except Exception:
            return False
    
    async def notify_mood_logged(
        self,
        user_id: UUID,
        mood_emoji: str,
        mood_score: int,
        note: Optional[str] = None
    ) -> bool:
        integration = self.get_user_integration(user_id)
        if not integration or not integration.is_active or not integration.notify_on_mood:
            return False
        
        emoji_map = {
            "happy": ":smile:",
            "neutral": ":neutral_face:",
            "sad": ":disappointed:",
            "upset": ":worried:"
        }
        
        emoji = emoji_map.get(mood_emoji, ":grey_question:")
        
        text = f"{emoji} You logged your mood: {mood_emoji} (Score: {mood_score}/5)"
        if note:
            text += f"\nNote: {note}"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Mood logged at {datetime.now().strftime('%I:%M %p')}"
                    }
                ]
            }
        ]
        
        if integration.dm_enabled:
            return await self.send_dm(user_id, text, blocks)
        
        if integration.channel_notifications and integration.notification_channel:
            return await self.send_channel_message(
                user_id, integration.notification_channel, text, blocks
            )
        
        return False
    
    async def notify_appreciation(
        self,
        user_id: UUID,
        from_name: str,
        message: str,
        is_sent: bool = True
    ) -> bool:
        integration = self.get_user_integration(user_id)
        if not integration or not integration.is_active:
            return False
        
        if is_sent and not integration.notify_on_appreciation:
            return False
        
        action = "sent" if is_sent else "received"
        text = f":star: Appreciation {action}!\n*From:* {from_name}\n{message}"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }
        ]
        
        if integration.dm_enabled:
            return await self.send_dm(user_id, text, blocks)
        
        if integration.channel_notifications and integration.notification_channel:
            return await self.send_channel_message(
                user_id, integration.notification_channel, text, blocks
            )
        
        return False
    
    async def notify_ticket_update(
        self,
        user_id: UUID,
        ticket_id: str,
        title: str,
        status: str,
        is_created: bool = False
    ) -> bool:
        integration = self.get_user_integration(user_id)
        if not integration or not integration.is_active or not integration.notify_on_tickets:
            return False
        
        action = "created" if is_created else "updated"
        text = f":ticket: Ticket {action}\n*#{ticket_id}:* {title}\nStatus: {status}"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }
        ]
        
        if integration.dm_enabled:
            return await self.send_dm(user_id, text, blocks)
        
        return False
    
    async def notify_leave(
        self,
        user_id: UUID,
        leave_type: str,
        start_date: str,
        end_date: str,
        status: str
    ) -> bool:
        integration = self.get_user_integration(user_id)
        if not integration or not integration.is_active or not integration.notify_on_leave:
            return False
        
        text = f":calendar: Leave Request {status}\n*Type:* {leave_type}\n*Dates:* {start_date} to {end_date}"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }
        ]
        
        if integration.dm_enabled:
            return await self.send_dm(user_id, text, blocks)
        
        return False
    
    def get_status(self, user_id: UUID) -> Dict:
        integration = self.get_user_integration(user_id)
        
        if not integration:
            return {
                "connected": False,
                "is_active": False,
                "notify_on_mood": True,
                "notify_on_appreciation": True,
                "notify_on_tickets": True,
                "notify_on_calendar": False,
                "notify_on_leave": True,
                "dm_enabled": True,
                "channel_notifications": False
            }
        
        return {
            "connected": True,
            "is_active": integration.is_active,
            "slack_user_id": integration.slack_user_id,
            "slack_team_id": integration.slack_team_id,
            "notify_on_mood": integration.notify_on_mood,
            "notify_on_appreciation": integration.notify_on_appreciation,
            "notify_on_tickets": integration.notify_on_tickets,
            "notify_on_calendar": integration.notify_on_calendar,
            "notify_on_leave": integration.notify_on_leave,
            "dm_enabled": integration.dm_enabled,
            "channel_notifications": integration.channel_notifications,
            "notification_channel": integration.notification_channel
        }
    
    def should_notify(self, user_id: UUID, event_type: str) -> bool:
        integration = self.get_user_integration(user_id)
        if not integration or not integration.is_active:
            return False
        
        mapping = {
            "mood_logged": integration.notify_on_mood,
            "appreciation_sent": integration.notify_on_appreciation,
            "appreciation_received": integration.notify_on_appreciation,
            "ticket_created": integration.notify_on_tickets,
            "ticket_updated": integration.notify_on_tickets,
            "ticket_resolved": integration.notify_on_tickets,
            "leave_requested": integration.notify_on_leave,
            "leave_approved": integration.notify_on_leave,
            "leave_rejected": integration.notify_on_leave,
            "birthday": integration.notify_on_calendar,
            "work_anniversary": integration.notify_on_calendar
        }
        
        return mapping.get(event_type, False)


def get_slack_service(db: Session) -> SlackService:
    return SlackService(db)


def connect_slack(
    db: Session,
    user_id: UUID,
    slack_user_id: str,
    slack_team_id: str,
    access_token: str
) -> Dict:
    service = SlackService(db)
    integration = service.connect(user_id, slack_user_id, slack_team_id, access_token)
    return {
        "id": str(integration.id),
        "user_id": str(integration.user_id),
        "slack_user_id": integration.slack_user_id,
        "slack_team_id": integration.slack_team_id,
        "is_active": integration.is_active
    }


def disconnect_slack(db: Session, user_id: UUID) -> bool:
    service = SlackService(db)
    return service.disconnect(user_id)


def update_slack_settings(
    db: Session,
    user_id: UUID,
    notify_on_mood: Optional[bool] = None,
    notify_on_appreciation: Optional[bool] = None,
    notify_on_tickets: Optional[bool] = None,
    notify_on_calendar: Optional[bool] = None,
    notify_on_leave: Optional[bool] = None,
    dm_enabled: Optional[bool] = None,
    channel_notifications: Optional[bool] = None,
    notification_channel: Optional[str] = None,
    is_active: Optional[bool] = None
) -> Optional[Dict]:
    service = SlackService(db)
    return service.update_settings(
        user_id,
        notify_on_mood=notify_on_mood,
        notify_on_appreciation=notify_on_appreciation,
        notify_on_tickets=notify_on_tickets,
        notify_on_calendar=notify_on_calendar,
        notify_on_leave=notify_on_leave,
        dm_enabled=dm_enabled,
        channel_notifications=channel_notifications,
        notification_channel=notification_channel,
        is_active=is_active
    )


def get_slack_status(db: Session, user_id: UUID) -> Dict:
    service = SlackService(db)
    return service.get_status(user_id)


def should_notify_slack(db: Session, user_id: UUID, event_type: str) -> bool:
    service = SlackService(db)
    return service.should_notify(user_id, event_type)