"""
OpenAI provider, via the Responses API.

Same tutor, different plumbing:

    instructions   tutoring rules + the problem statement   stable per problem
    input          the transcript                          changes per turn
    last item      the user's current code + message       changes per keystroke

OpenAI's prompt caching is automatic — any request whose prefix matches a
recent one (past ~1,024 tokens) is served from cache with no breakpoints to
place. Keeping the stable text first is all that is needed, and it is the same
ordering the Anthropic provider uses. Cache hits show up as
`usage.input_tokens_details.cached_tokens`.

Two things this vendor has no equivalent for: the explicit cache breakpoint
and the server-side refusal fallback. A refusal here arrives as a `refusal`
content part in the output rather than a stop reason.
"""

import os

import openai
from openai import AsyncOpenAI
from openai.types.responses import Response

from ..config import settings
from ..prompt import SYSTEM_PROMPT, code_block, problem_block
from ..schemas import ChatRequest, ChatResponse, Usage
from .base import CUT_SHORT_MARKER, REFUSAL_REPLY, NoCredentials, ProviderError


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        self.model = settings.openai_model
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        """Built on first use, for the same reason as the Anthropic provider."""
        if self._client is None:
            # pydantic-settings reads .env into `settings`, not into the
            # process environment, so the SDK would never see the key on its
            # own — pass it explicitly. The environment stays as a fallback.
            key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
            if not key:
                raise NoCredentials("No OpenAI credentials: set OPENAI_API_KEY in backend/.env")
            self._client = AsyncOpenAI(api_key=key)
        return self._client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        try:
            response = await self._get_client().responses.create(
                model=self.model,
                instructions=f"{SYSTEM_PROMPT}\n\n{problem_block(request)}",
                input=_build_input(request),
                max_output_tokens=16000,
            )
        except openai.AuthenticationError:
            raise ProviderError(502, "The backend's OpenAI key was rejected") from None
        except openai.RateLimitError:
            # Also what the free daily allowance returns once it is used up.
            raise ProviderError(429, "Rate limited by OpenAI — try again shortly") from None
        except openai.APIStatusError as e:
            raise ProviderError(
                502,
                f"OpenAI API error ({e.status_code})",
                log=f"OpenAI API error {e.status_code}: {e.message}",
            ) from None
        except openai.APIConnectionError:
            raise ProviderError(502, "Could not reach OpenAI") from None

        usage = response.usage
        cached = usage.input_tokens_details.cached_tokens if usage else 0
        return ChatResponse(
            reply=_reply_text(response),
            model=response.model,
            usage=Usage(
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                cache_read_input_tokens=cached,
                # OpenAI does not bill cache writes separately.
                cache_creation_input_tokens=0,
            ),
        )


def _build_input(request: ChatRequest) -> list[dict]:
    history = [{"role": m.role, "content": m.content} for m in request.messages[:-1]]
    last = request.messages[-1]

    # Two text parts in one turn, mirroring the Anthropic provider.
    content: list[dict] = []
    if code := code_block(request):
        content.append({"type": "input_text", "text": code})
    content.append({"type": "input_text", "text": last.content})

    return [*history, {"role": "user", "content": content}]


def _reply_text(response: Response) -> str:
    text = response.output_text

    if not text:
        # A declined request has no text; the refusal is a content part.
        for item in response.output:
            if item.type == "message" and any(part.type == "refusal" for part in item.content):
                return REFUSAL_REPLY

    details = response.incomplete_details
    if response.status == "incomplete" and details and details.reason == "max_output_tokens":
        text += CUT_SHORT_MARKER
    return text
