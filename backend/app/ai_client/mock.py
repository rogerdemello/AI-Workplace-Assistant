from typing import List, Dict, Any, Optional


class MockAzureOpenAIClient:
    def __init__(self, *args, **kwargs):
        pass

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        last_message = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict) and "content" in last_msg:
                last_message = str(last_msg["content"])

        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": f"Mock response to: {last_message[:50]}..."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            },
            "model": "mock-gpt-4"
        }

    def embeddings(self, text: str, engine: Optional[str] = None) -> List[float]:
        return [0.1] * 1536
