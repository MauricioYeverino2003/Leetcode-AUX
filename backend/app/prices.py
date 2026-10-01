"""
Per-model prices, USD per 1M tokens, for cost estimates.

Hand-maintained from the vendors' pricing pages, so treat every number as
approximate and check the date below against the vendor's page before quoting
one. A model with no entry gets `None`, never a guess.
"""

from dataclasses import dataclass

from .schemas import Usage

PRICES_AS_OF = "2026-09-30"

PER_MILLION = 1_000_000

@dataclass(frozen=True)
class Price:
    input: float
    output: float
    # Input served from the prompt cache.
    cached_input: float
    # Writing to the cache. Anthropic bills it at 1.25x input; OpenAI does not
    # bill cache writes at all.
    cache_write: float


PRICES: dict[str, Price] = {
    "claude-opus-5": Price(input=5.00, output=25.00, cached_input=0.50, cache_write=6.25),
    "claude-sonnet-5": Price(input=2.00, output=10.00, cached_input=0.20, cache_write=2.50),
    "claude-haiku-4-5": Price(input=1.00, output=5.00, cached_input=0.10, cache_write=1.25),
    "gpt-5": Price(input=1.25, output=10.00, cached_input=0.125, cache_write=0.0),
    "gpt-5-mini": Price(input=0.25, output=2.00, cached_input=0.025, cache_write=0.0),
}

def lookup(model: str) -> Price | None:
    """Exact match first, then the longest key the model id starts with — the
    API often reports a dated snapshot such as `gpt-5-2025-08-07`."""
    if model in PRICES:
        return PRICES[model]
    candidates = [key for key in PRICES if model.startswith(key)]
    if not candidates:
        return None
    return PRICES[max(candidates, key=len)]

def estimate_cost(model: str, usage: Usage) -> float | None:
    price = lookup(model)
    if price is None:
        return None
    cost = (
        usage.input_tokens * price.input
        + usage.cache_read_input_tokens * price.cached_input
        + usage.cache_creation_input_tokens * price.cache_write
        + usage.output_tokens * price.output
    ) / PER_MILLION
    return round(cost, 6)
