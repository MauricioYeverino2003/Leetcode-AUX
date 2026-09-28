"""
Request and response shapes for /chat.

The size limits are not cosmetic. Every byte a client sends here ends up in a
prompt billed to the backend's key, so the schema is the first cost control.
"""

from typing import Literal

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
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class ChatResponse(BaseModel):
    reply: str
    model: str
    usage: Usage
