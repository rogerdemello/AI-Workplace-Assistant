from .client import AzureOpenAIClient
from .mock import MockAzureOpenAIClient
from ..config import settings


def get_ai_client(use_mock: bool = False):
    if use_mock:
        return MockAzureOpenAIClient()
    return AzureOpenAIClient(
        api_key=settings.AZURE_OPENAI_API_KEY,
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        api_version=getattr(settings, 'AZURE_OPENAI_API_VERSION', '2024-02-15')
    )


__all__ = ["AzureOpenAIClient", "MockAzureOpenAIClient", "get_ai_client"]
