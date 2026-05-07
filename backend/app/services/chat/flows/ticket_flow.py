"""Ticket / complaint flow — trust-first: context, target, anonymity, confirm (severity inferred)."""

FLOW_NAME = "ticket"

# Severity is inferred in code, not asked as mild/serious/urgent.
required_fields = ["issue", "against", "anonymous"]
steps = ["issue", "against", "anonymous", "confirm", "done"]

prompts = {
    "issue": "That sounds frustrating 😔 Can you tell me what happened?",
    "against": "Is this about a specific person or role? A name is fine.",
    "anonymous": "Do you want to keep this anonymous? (yes / no)",
    "confirm": "Want me to send this to HR? They'll handle it confidentially.",
    "done": "Done — I've shared this with HR.",
}

allowed_severity = {"mild", "serious", "urgent"}
allowed_departments = {"hr", "it", "facilities", "finance", "management"}
