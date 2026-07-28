from .client import AzureOpenAIClient
from .mock import MockAzureOpenAIClient
from ..config import settings


def get_ai_client(use_mock: bool = False):
    # AI_USE_MOCK makes the stub reachable by configuration, not just by callers
    # that pass use_mock. Browser e2e runs need it: without a real endpoint every
    # model call burns its full retry timeout before falling back, which made the
    # suite slow and timing-sensitive — and hid a real message-dropping bug
    # behind that latency for several CI runs.
    if use_mock or getattr(settings, "AI_USE_MOCK", False):
        return MockAzureOpenAIClient()
    return AzureOpenAIClient(
        api_key=settings.AZURE_OPENAI_API_KEY,
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        api_version=getattr(settings, 'AZURE_OPENAI_API_VERSION', '2024-02-15')
    )


__all__ = ["AzureOpenAIClient", "MockAzureOpenAIClient", "get_ai_client"]
