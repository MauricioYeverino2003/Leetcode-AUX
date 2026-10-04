"""
The contract every model provider implements.

A provider turns a ChatRequest into a ChatResponse using one vendor's SDK, and
reports failures as ProviderError so the route can answer with the right HTTP
status without knowing which vendor is behind it. main.py imports nothing
vendor-specific; that is the whole point.
"""

from collections.abc import Sequence
from typing import Protocol

from ..schemas import ChatRequest, ChatResponse, PriorSolution


class ProviderError(Exception):
    """A failure the route should turn into an HTTP response.

    `status` is the HTTP status to return and `detail` the message the client
    sees. `log` is what goes in the server log when it should say more than the
    client is told (upstream error text, for instance).
    """

    def __init__(self, status: int, detail: str, *, log: str | None = None):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.log = log or detail


class NoCredentials(ProviderError):
    """The backend has no way to authenticate to the vendor."""

    def __init__(self, detail: str):
        super().__init__(503, detail)


class Provider(Protocol):
    name: str
    model: str

    async def chat(self, request: ChatRequest, prior: Sequence[PriorSolution] = ()) -> ChatResponse:
        """One tutoring turn. `prior` is what recall found among the user's
        saved solutions; it goes into the prompt's stable part."""
        ...

    async def complete(self, *, instructions: str, text: str, effort: str | None = None) -> ChatResponse:
        """A one-off request outside the tutoring chat — its own instructions,
        one piece of input, no transcript. `effort` is this call's own; the
        LLM_EFFORT setting is for chat and is not applied here."""
        ...


# What the user sees when the vendor's safety layer declines the request.
# Worded the same everywhere so the product does not change tone by vendor.
REFUSAL_REPLY = "I can't help with that one. Want to try a different question about the problem?"

CUT_SHORT_MARKER = "\n\n[reply cut short]"
