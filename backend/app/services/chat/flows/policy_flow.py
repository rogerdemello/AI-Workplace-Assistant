"""Policy query flow definition."""

FLOW_NAME = "policy_query"

required_fields = ["query"]
steps = ["query", "done"]

prompts = {
    "query": "Tell me your policy question and I will look it up.",
    "done": "Here is what I found.",
}
