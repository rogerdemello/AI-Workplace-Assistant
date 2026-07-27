"""Shift-change flow — remote-work days and shift swaps.

Distinct from the leave flow: a WFH day here is a working day the employee wants
relocated, not time off. The leave flow keeps its ``work from home`` leave type
for people who phrase it as leave.
"""

FLOW_NAME = "shift_change_request"

required_fields = ["change_type", "start_date", "end_date", "reason"]
steps = ["change_type", "start_date", "end_date", "reason", "confirm", "done"]

prompts = {
    "change_type": "Got it — is this to work from home, or to swap/change a shift?",
    "start_date": "Which day should this start? (YYYY-MM-DD works great.)",
    "end_date": "And the last day? If it's just the one day, repeat the same date.",
    "reason": "What's the reason? A short line is enough.",
    "confirm": "Want me to send this to your manager and HR?",
    "end_date_invalid": "That end date looks earlier than the start date. What's the correct end date?",
    "start_date_invalid": "Start dates can't be more than 1 day in the past. Please use today or a future date.",
    "max_duration_exceeded": "Shift-change requests can't span more than 90 days. Could you shorten the range?",
    "done": "Sent. Your manager will review it and HR has a copy.",
}
