"""
Anthropic provider.

Prompt layout, chosen for prompt caching — the cache is a prefix match, so
stable content goes first and volatile content last:

    system[0]  tutoring rules            never changes
    system[1]  the problem statement     changes per problem   <- cache breakpoint
    messages   the transcript            changes per turn
    last turn  the user's current code   changes per keystroke

The code rides in the final user turn rather than the system prompt precisely
because it changes every message; putting it earlier would invalidate the
cache on every turn.
"""

from collections.abc import Sequence

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types.beta import BetaMessage

from ..config import settings
from ..prompt import SYSTEM_PROMPT, code_block, problem_block
from ..schemas import ChatRequest, ChatResponse, PriorSolution, Usage
from .base import CUT_SHORT_MARKER, REFUSAL_REPLY, NoCredentials, ProviderError


class ClaudeProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self.model = settings.anthropic_model
        self._client: AsyncAnthropic | None = None

    def _get_client(self) -> AsyncAnthropic:
        """Built on first use so a missing key fails on the first chat with a
        clear message instead of preventing the server from starting."""
        if self._client is not None:
            return self._client

        if settings.anthropic_api_key:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            return self._client

        # Zero-arg: the SDK resolves ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN
        # from the process environment, or an `ant auth login` profile. It does
        # not complain if none exist — it raises a bare TypeError on the first
        # request instead — so check the same three sources its request-time
        # check looks at, and fail with something nameable.
        c = AsyncAnthropic()
        if c.api_key is None and c.auth_token is None and getattr(c, "_token_cache", None) is None:
            raise NoCredentials("No Anthropic credentials: set ANTHROPIC_API_KEY in backend/.env")
        self._client = c
        return c

    async def chat(self, request: ChatRequest, prior: Sequence[PriorSolution] = ()) -> ChatResponse:
        system = [
            {"type": "text", "text": SYSTEM_PROMPT},
            {
                "type": "text",
                "text": problem_block(request, prior),
                "cache_control": {"type": "ephemeral"},
            },
        ]
        messages = _build_messages(request)

        response = await self._create(system=system, messages=messages, effort=settings.llm_effort)
        return _to_chat_response(response, {"system": system, "messages": messages})

    async def complete(self, *, instructions: str, text: str, effort: str | None = None) -> ChatResponse:
        system = [{"type": "text", "text": instructions}]
        messages = [{"role": "user", "content": text}]

        response = await self._create(system=system, messages=messages, effort=effort)
        return _to_chat_response(response, {"system": system, "messages": messages})

    async def _create(self, *, system: list[dict], messages: list[dict], effort: str | None) -> BetaMessage:
        """The one place this provider calls the API, so every kind of request
        gets the same error mapping."""
        try:
            return await self._get_client().beta.messages.create(
                model=self.model,
                max_tokens=16000,
                # Claude Opus 5 has thinking on by default (adaptive). effort,
                # when set, caps how much; omitted = the default.
                **({"output_config": {"effort": effort}} if effort else {}),
                # Refusal fallback: if a safety classifier declines the
                # request, the API re-runs it on Anthropic's recommended
                # fallback model server-side instead of returning the refusal.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=system,
                messages=messages,
            )
        except anthropic.AuthenticationError as e:
            raise ProviderError(
                502,
                "The backend's Anthropic key was rejected",
                log=f"Anthropic rejected the key: {e.message}",
            ) from None
        except anthropic.RateLimitError:
            raise ProviderError(429, "Rate limited by Anthropic — try again shortly") from None
        except anthropic.APIStatusError as e:
            raise ProviderError(
                502,
                f"Anthropic API error ({e.status_code})",
                log=f"Anthropic API error {e.status_code}: {e.message}",
            ) from None
        except anthropic.APIConnectionError:
            raise ProviderError(502, "Could not reach Anthropic") from None


def _to_chat_response(response: BetaMessage, prompt: dict) -> ChatResponse:
    usage = response.usage
    return ChatResponse(
        reply=_reply_text(response),
        model=response.model,
        usage=Usage(
            # Anthropic already reports input_tokens excluding the cached
            # part, which is exactly what Usage wants.
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            # Thinking is folded into output_tokens; not reported separately.
            reasoning_tokens=0,
            cache_read_input_tokens=usage.cache_read_input_tokens or 0,
            cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
        ),
        prompt=prompt,
    )


def _build_messages(request: ChatRequest) -> list[dict]:
    """Every user turn is a list of text blocks with the message first, so a
    turn is shaped the same whether it is the newest — `[message, code]` — or
    history — `[message]`. Same reasoning as the OpenAI provider: the only
    difference between one request and the next is then the code at the very
    end, which is what lets the earlier turns be served from cache."""
    messages: list[dict] = []
    for m in request.messages[:-1]:
        if m.role == "user":
            messages.append({"role": "user", "content": [{"type": "text", "text": m.content}]})
        else:
            messages.append({"role": "assistant", "content": m.content})

    last = request.messages[-1]
    content = [{"type": "text", "text": last.content}]
    if code := code_block(request):
        content.append({"type": "text", "text": code})
    messages.append({"role": "user", "content": content})
    return messages


def _reply_text(response: BetaMessage) -> str:
    if response.stop_reason == "refusal":
        return REFUSAL_REPLY

    text = "".join(block.text for block in response.content if block.type == "text")

    if response.stop_reason == "max_tokens":
        text += CUT_SHORT_MARKER
    return text
