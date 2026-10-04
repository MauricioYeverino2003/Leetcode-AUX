"""
Request and response shapes for /chat.

The size limits are not cosmetic. Every byte a client sends here ends up in a
prompt billed to the backend's key, so the schema is the first cost control.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ProblemContext(BaseModel):
    """What the extension captured from the LeetCode page."""

    slug: str = Field(max_length=200)
    title: str | None = Field(default=None, max_length=300)
    difficulty: str | None = Field(default=None, max_length=20)
    statement: str | None = Field(default=None, max_length=30_000)
    # LeetCode's topic tags, e.g. ["Array", "Hash Table"] — what recall
    # matches the user's saved solutions on.
    topic_tags: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=30)


class CodeContext(BaseModel):
    """What the user has written so far, read from the Monaco editor."""

    language: str | None = Field(default=None, max_length=50)
    code: str = Field(max_length=50_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)
    problem: ProblemContext | None = None
    code: CodeContext | None = None

    @model_validator(mode="after")
    def last_message_is_from_user(self) -> "ChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("The last message must be from the user")
        return self


class Usage(BaseModel):
    """Token counts, normalised so one cost formula works for every vendor.

    `input_tokens` is UNCACHED input — the part billed at the full rate. OpenAI
    reports cached tokens inside its input count and Anthropic reports them
    separately; providers reconcile that here so the fields mean the same thing
    whichever vendor answered.
    """

    input_tokens: int
    output_tokens: int
    # The part of output_tokens spent thinking before the visible reply. Billed
    # as output and usually most of the latency. OpenAI reports it; Anthropic
    # folds it into output_tokens, so it is 0 there.
    reasoning_tokens: int = 0
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class Timing(BaseModel):
    # The provider call alone — the number to compare across models and effort.
    model_ms: int = 0
    # The whole route: validation, auth, provider. The gap to model_ms is what
    # the backend itself costs, and should be negligible.
    backend_ms: int = 0


class PriorSolution(BaseModel):
    """One of the user's saved solutions, as recalled for the tutor. It never
    carries the code: the tutor gets the summary only."""

    slug: str
    title: str | None = None
    difficulty: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    summary: str
    # True when it is the very problem they are working on now.
    same_problem: bool = False


class PriorRef(BaseModel):
    """What the panel is told about a recalled solution."""

    slug: str
    title: str | None = None


class ChatResponse(BaseModel):
    reply: str
    model: str
    usage: Usage
    timing: Timing = Field(default_factory=Timing)
    # Estimated from app/prices.py. None when the model has no price entry —
    # never a guess.
    cost_usd: float | None = None
    # Exactly what was sent to the model, for the benchmark log. Excluded from
    # the JSON the client receives.
    prompt: dict | None = Field(default=None, exclude=True)
    # Which of the user's saved solutions the tutor was shown for this reply.
    prior_solutions: list[PriorRef] = Field(default_factory=list)


class SolutionRequest(BaseModel):
    """An accepted submission, as the extension read it back from LeetCode."""

    # LeetCode's id for the submission. Past the 32-bit range already.
    submission_id: int = Field(gt=0)
    problem: ProblemContext
    # The number shown on the site, e.g. "200".
    problem_number: str | None = Field(default=None, max_length=20)
    topic_tags: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=30)
    language: str | None = Field(default=None, max_length=50)
    code: str = Field(min_length=1, max_length=50_000)


class SolutionResponse(BaseModel):
    summary: str
    # True when this submission was already stored: nothing was written and no
    # model call was made.
    already_saved: bool
    model: str | None = None
    cost_usd: float | None = None
