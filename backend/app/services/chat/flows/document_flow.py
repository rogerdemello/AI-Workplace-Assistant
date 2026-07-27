"""Document flow — request payslips, letters and tax documents: type → purpose → confirm."""

FLOW_NAME = "document_request"

required_fields = ["document_type", "purpose"]
steps = ["document_type", "purpose", "confirm", "done"]

prompts = {
    "document_type": (
        "Happy to help — which document do you need? "
        "(payslip, employment letter, experience letter, salary certificate, or a tax document like Form 16)"
    ),
    "purpose": "What do you need it for? That helps HR issue the right version.",
    "confirm": "Want me to request this from HR?",
    "done": "Requested. HR will send it across once it's ready.",
}
