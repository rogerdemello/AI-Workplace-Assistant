"""Ticket conversation flow definition."""

FLOW_NAME = "ticket"

required_fields = ["issue", "category", "severity", "against", "department", "anonymous"]
steps = ["issue", "severity", "against", "department", "anonymous", "done"]

prompts = {
    "issue": "That sounds frustrating 😔  Can you tell me what happened?",
    "severity": "How severe is this issue — mild, serious, or urgent?",
    "against": "Who is this against? You can share a person, team, or role.",
    "department": "Which department should handle this — HR, IT, Facilities, Finance, or Management?",
    "anonymous": "Got you. Do you want to stay anonymous? (yes / no)",
    "done": "Done. I raised your ticket. 🎫",
}

allowed_severity = {"mild", "serious", "urgent"}
allowed_departments = {"hr", "it", "facilities", "finance", "management"}
