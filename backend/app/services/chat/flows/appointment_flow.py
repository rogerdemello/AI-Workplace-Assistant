"""Appointment flow — book a 1:1 with HR: topic → date → time → mode → confirm."""

FLOW_NAME = "appointment_request"

required_fields = ["topic", "preferred_date", "preferred_time", "mode"]
steps = ["topic", "preferred_date", "preferred_time", "mode", "confirm", "done"]

prompts = {
    "topic": "Of course — what would you like to talk about? A one-line summary is plenty.",
    "preferred_date": "Which day works for you? (YYYY-MM-DD is easiest.)",
    "preferred_time": "What time suits you best? (e.g. 11:00 or 3pm)",
    "mode": "Would you prefer this in person, over a call, or a video meeting?",
    "confirm": "Want me to send this to HR?",
    "preferred_date_invalid": "That date looks like it's in the past. Which upcoming day works?",
    "preferred_time_invalid": "I couldn't read that time — could you give it as 11:00 or 3pm?",
    "done": "Booked. HR will confirm the slot with you shortly.",
}
