"""Expense flow — file a reimbursement claim: category → amount → date → description → confirm."""

FLOW_NAME = "expense_claim"

required_fields = ["expense_type", "amount", "expense_date", "description"]
steps = ["expense_type", "amount", "expense_date", "description", "confirm", "done"]

prompts = {
    "expense_type": "Sure — what kind of expense is it? (travel, meals, equipment, training, or something else)",
    "amount": "How much was it? Just the number is fine.",
    "expense_date": "What date was the expense? (YYYY-MM-DD works great.)",
    "description": "Briefly, what was it for?",
    "confirm": "Want me to submit this claim?",
    "amount_invalid": "I couldn't read that amount — could you give me just the number, like 2500?",
    "expense_date_invalid": "That date looks off. What date was the expense? (YYYY-MM-DD)",
    "done": "Submitted. Finance will pick it up from here.",
}
