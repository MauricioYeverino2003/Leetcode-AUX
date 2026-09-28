"""
Which vendor answers the chat is one setting: LLM_PROVIDER in backend/.env.

Each provider's SDK is imported only when that provider is selected, so the
unselected one can be missing, broken, or unconfigured without any effect.
"""

from functools import lru_cache

from ..config import settings
from .base import NoCredentials, Provider, ProviderError

__all__ = ["NoCredentials", "Provider", "ProviderError", "get_provider"]


@lru_cache
def get_provider() -> Provider:
    if settings.llm_provider == "openai":
        from .gpt import OpenAIProvider

        return OpenAIProvider()

    from .claude import ClaudeProvider

    return ClaudeProvider()
