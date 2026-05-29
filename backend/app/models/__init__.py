from .user import User, UserRole, UserStatus
from .department import Department
from .conversation import Conversation, Message, ConversationStatus, MessageSender, SentimentLabel
from .ticket import Ticket, TicketMessage, TicketStatus, TicketPriority, SLA_HOURS
from .survey import Survey, SurveyResponse
from .room import Room, RoomBooking
from .user_profile import UserProfile
from .conversation_memory import ConversationMemory
from .action import HRAction, HRActionType, HRActionStatus
from .hr_alert import HrAlert
from .leave_request import LeaveRequest, LeaveStatus, LeaveType
from .attachment import Attachment, AttachmentEntityType
from .chat_feedback import ChatFeedback
from .activity_event import ActivityEvent
from .reminder_schedule import ReminderSchedule
from .wellbeing_signal import WellbeingSignal
from .risk_snapshot import RiskSnapshot
from .automation_action import AutomationAction
from .calendar_integration import CalendarIntegration
from .personal_fact import PersonalFact, PersonalFactType
from .mood_entry import MoodEntry, MoodEmoji
from .celebration import Celebration, CelebrationType
from .appreciation_note import AppreciationNote
from .wellness_tip import WellnessTip, WellnessTipType
from .onboarding_checklist import OnboardingChecklist
from .onboarding_buddy import OnboardingBuddy
from .webhook import Webhook, WebhookDelivery, WebhookEventType, WebhookStatus, SlackIntegration
from .ticket_action_log import TicketActionLog
from .hr_notification import HrNotification
from .automation_rule import AutomationRule
from .sentiment_log import SentimentLog
from .employee_score import EmployeeScore
from .message_signal import MessageSignal
from .anonymous_feedback import AnonymousFeedback
# Imported so every table is registered on Base.metadata when alembic loads
# `app.models`; without these, autogenerate flagged live tables (documents,
# audit_logs, whatsapp_links, meeting_events, analytics_*) for removal.
from .analytics import (
    MentalHealthScore,
    BurnoutPrediction,
    SentimentHistory,
    AnalyticsSnapshot,
    Insight,
    ResponseSuggestion,
)
from .audit_log import AuditLog
from .document import Document, DocumentChunk
from .meeting_event import MeetingEvent
from .whatsapp_link import WhatsappLink
from .offboarding_task import OffboardingTask

__all__ = [
    "User", "UserRole", "UserStatus", "Department",
    "Conversation", "Message", "ConversationStatus", "MessageSender", "SentimentLabel",
    "Ticket", "TicketMessage", "TicketStatus", "TicketPriority", "SLA_HOURS",
    "Survey", "SurveyResponse",
    "Room", "RoomBooking",
    "UserProfile", "ConversationMemory",
    "HRAction", "HRActionType", "HRActionStatus",
    "HrAlert",
    "LeaveRequest", "LeaveStatus", "LeaveType",
    "Attachment", "AttachmentEntityType",
    "ChatFeedback",
    "ActivityEvent",
    "ReminderSchedule",
    "WellbeingSignal",
    "RiskSnapshot",
    "AutomationAction",
    "CalendarIntegration",
    "PersonalFact",
    "PersonalFactType",
    "MoodEntry",
    "MoodEmoji",
    "Celebration",
    "CelebrationType",
    "AppreciationNote",
    "WellnessTip",
    "WellnessTipType",
    "OnboardingChecklist",
    "OnboardingBuddy",
    "TicketActionLog",
    "HrNotification",
    "AutomationRule",
    "SentimentLog",
    "EmployeeScore",
    "MessageSignal",
    "Webhook",
    "WebhookDelivery",
    "WebhookEventType",
    "WebhookStatus",
    "SlackIntegration",
    "AnonymousFeedback",
]
