"""Leave request conversation flow definition."""

FLOW_NAME = "leave_request"

required_fields = ["leave_type", "start_date", "end_date", "reason"]
steps = ["leave_type", "start_date", "end_date", "reason", "done"]

prompts = {
    "leave_type": "Got you. What type of leave do you need — paid, sick, work from home, or unpaid?",
    "start_date": "Got it. When does it start? (YYYY-MM-DD works great)",
    "end_date": "Noted. And what is the last day?",
    "end_date_invalid": "That end date looks earlier than the start date. What is the correct end date?",
    "reason": "What's the reason for your leave?",
    "done": "Done. I have submitted your leave request and your manager will review it.",
}
