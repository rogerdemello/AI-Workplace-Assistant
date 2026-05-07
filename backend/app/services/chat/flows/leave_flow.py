"""Leave request flow — strict slot order: dates → type → reason → confirm."""

FLOW_NAME = "leave_request"

required_fields = ["start_date", "end_date", "leave_type", "reason"]
steps = ["start_date", "end_date", "leave_type", "reason", "confirm", "done"]

prompts = {
    "start_date": "Sure — what start date should I use? (YYYY-MM-DD works great.)",
    "end_date": "What end date works?",
    "leave_type": "Which type of leave is this — paid, sick, work from home, or unpaid?",
    "reason": "Got it — what's the reason for this leave?",
    "confirm": "Want me to submit this leave for you?",
    "end_date_invalid": "That end date looks earlier than the start date. What's the correct end date?",
    "max_duration_exceeded": "Leave requests can't exceed 60 days. Could you adjust the dates?",
    "start_date_invalid": "Start dates can't be more than 1 day in the past. Please use today or a future date.",
    "done": "Done. I have submitted your leave request and your manager will review it.",
}
