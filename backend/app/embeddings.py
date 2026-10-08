"""
Embeddings, for recall by meaning.

OpenAI only: Anthropic has no embeddings API, so this runs on OPENAI_API_KEY
whatever LLM_PROVIDER says. Without a key, recall falls back to tags.

The model's dimension count is baked into the solutions table (see the
migration and EMBEDDING_DIMENSIONS), so a model that returns a different size
is refused here rather than failing deep inside Postgres.
"""

import logging
import os

import openai
from openai import AsyncOpenAI

from .config import EMBEDDING_DIMENSIONS, settings
from .prices import estimate_embedding_cost
from .schemas import ProblemContext

log = logging.getLogger("leetcode-aux")

_client: AsyncOpenAI | None = None


class EmbeddingError(Exception):
    """Same shape as ProviderError: `detail` for the client, `log` for the
    server log."""

    def __init__(self, status: int, detail: str, *, log: str | None = None):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.log = log or detail


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise EmbeddingError(503, "No OpenAI credentials for embeddings: set OPENAI_API_KEY in backend/.env")
        _client = AsyncOpenAI(api_key=key)
    return _client


async def embed(texts: list[str]) -> list[list[float]]:
    """One vector per text, in order."""
    if not texts:
        return []

    try:
        response = await _get_client().embeddings.create(model=settings.embedding_model, input=texts)
    except openai.AuthenticationError as e:
        raise EmbeddingError(
            502, "The backend's OpenAI key was rejected", log=f"OpenAI rejected the key: {e.message}"
        ) from None
    except openai.RateLimitError:
        raise EmbeddingError(429, "Rate limited by OpenAI — try again shortly") from None
    except openai.APIStatusError as e:
        raise EmbeddingError(
            502, f"OpenAI API error ({e.status_code})", log=f"OpenAI API error {e.status_code}: {e.message}"
        ) from None
    except openai.APIConnectionError:
        raise EmbeddingError(502, "Could not reach OpenAI") from None

    vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
    if any(len(v) != EMBEDDING_DIMENSIONS for v in vectors):
        raise EmbeddingError(
            500,
            "Embedding size does not match the database",
            log=(
                f"{response.model} returned {len(vectors[0])} dimensions; "
                f"the solutions table holds {EMBEDDING_DIMENSIONS}"
            ),
        )

    tokens = response.usage.total_tokens if response.usage else 0
    cost = estimate_embedding_cost(response.model, tokens)
    log.info(
        "embed model=%s texts=%d tokens=%d cost=%s",
        response.model, len(texts), tokens, f"${cost:.5f}" if cost is not None else "n/a",
    )
    return vectors


def solution_text(row: dict) -> str:
    """What a saved solution is embedded as: title, tags, the summary, and the
    statement when the row has one. Keep in step with problem_text."""
    title = row.get("problem_title") or row.get("problem_slug") or ""
    number = row.get("problem_number")
    parts = [f"{number}. {title}" if number else title]
    if row.get("topic_tags"):
        parts.append("Tags: " + ", ".join(row["topic_tags"]))
    parts.append(row.get("summary") or "")
    if row.get("statement"):
        parts.append(row["statement"])
    return "\n\n".join(p for p in parts if p)


def problem_text(problem: ProblemContext) -> str:
    """What the problem in front of the user is embedded as, to search with."""
    parts = [problem.title or problem.slug]
    if problem.topic_tags:
        parts.append("Tags: " + ", ".join(problem.topic_tags))
    if problem.statement:
        parts.append(problem.statement[:4000])
    return "\n\n".join(parts)
