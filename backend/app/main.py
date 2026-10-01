import logging
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import benchmarks, db
from .auth import User, current_user, user_token
from .config import settings
from .prices import estimate_cost
from .prompt import SUMMARY_PROMPT, solution_block
from .providers import ProviderError, get_provider
from .providers.base import REFUSAL_REPLY
from .schemas import ChatRequest, ChatResponse, SolutionRequest, SolutionResponse, Timing

log = logging.getLogger("leetcode-aux")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="LeetCode AUX backend", version="0.4.0")

# Summaries are a small, bounded task, so they always run at the cheapest
# effort. LLM_EFFORT is tuned for hint quality and does not apply to them.
SUMMARY_EFFORT = "low"

# The side panel runs on chrome-extension://<id>/ — 32 letters a–p. In practice
# Chrome skips CORS for hosts the extension holds host_permissions for, but
# any other client (a web dashboard, later) needs this, and it costs nothing.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^chrome-extension://[a-p]{32}$",
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def stamp_arrival(request: Request, call_next):
    # Runs before validation and auth, so backend_ms covers the whole route,
    # not just the handler body.
    request.state.arrived = perf_counter()
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    provider = get_provider()
    return {
        "status": "ok",
        "provider": provider.name,
        "model": provider.model,
        "effort": settings.llm_effort or "default",
    }


@app.get("/me")
def me(user: User = Depends(current_user)) -> User:
    """Echoes the verified user. Exists so auth can be tested without spending a
    model call."""
    return user


@app.post("/chat")
async def chat(
    request: ChatRequest,
    http: Request,
    user: User = Depends(current_user),
) -> ChatResponse:
    provider = get_provider()

    model_started = perf_counter()
    try:
        response = await provider.chat(request)
    except ProviderError as e:
        log.error("%s: %s", provider.name, e.log)
        raise HTTPException(e.status, e.detail) from None
    finished = perf_counter()

    response.timing = Timing(
        model_ms=round((finished - model_started) * 1000),
        backend_ms=round((finished - http.state.arrived) * 1000),
    )
    response.cost_usd = estimate_cost(response.model, response.usage)

    benchmarks.record(
        source="panel",
        user_id=user.id,
        provider=provider.name,
        request=request,
        response=response,
    )

    u, t = response.usage, response.timing
    log.info(
        "chat user=%s provider=%s model=%s effort=%s in=%d out=%d reasoning=%d "
        "cache_read=%d cache_write=%d model_ms=%d backend_ms=%d cost=%s",
        user.id, provider.name, response.model, settings.llm_effort or "default",
        u.input_tokens, u.output_tokens, u.reasoning_tokens,
        u.cache_read_input_tokens, u.cache_creation_input_tokens,
        t.model_ms, t.backend_ms,
        f"${response.cost_usd:.4f}" if response.cost_usd is not None else "n/a",
    )
    return response


@app.post("/solutions")
async def save_solution(
    request: SolutionRequest,
    user: User = Depends(current_user),
    token: str = Depends(user_token),
) -> SolutionResponse:
    """Stores an accepted submission with a short summary of it — once per
    submission, and once per distinct piece of code for a problem.

    That the submission was accepted is the extension's word: the backend has
    no LeetCode session to check it with, and the row is the caller's own.
    """
    # Looked up before the model call, so neither of these costs anything:
    # re-opening an old submission (which the extension reports again), and
    # submitting the same code again, which LeetCode gives a new id each time.
    # A different accepted approach to the same problem is still saved.
    try:
        existing = await db.find_solution(token, request.submission_id)
        reason = "already saved"
        if existing is None:
            existing = await db.find_same_code(token, request.problem.slug, request.code)
            reason = "same code as an earlier submission"
    except db.DbError as e:
        log.error("db: %s", e.log)
        raise HTTPException(e.status, e.detail) from None

    if existing:
        log.info("solution user=%s submission=%d %s", user.id, request.submission_id, reason)
        return SolutionResponse(
            summary=existing["summary"],
            already_saved=True,
            model=existing.get("summary_model"),
        )

    provider = get_provider()

    model_started = perf_counter()
    try:
        response = await provider.complete(
            instructions=SUMMARY_PROMPT,
            text=solution_block(request),
            effort=SUMMARY_EFFORT,
        )
    except ProviderError as e:
        log.error("%s: %s", provider.name, e.log)
        raise HTTPException(e.status, e.detail) from None
    model_ms = round((perf_counter() - model_started) * 1000)

    summary = response.reply.strip()
    if not summary or summary == REFUSAL_REPLY:
        # Nothing worth storing; the extension keeps the submission and retries.
        log.error("%s: no usable summary for submission %d", provider.name, request.submission_id)
        raise HTTPException(502, "The model returned no summary")

    try:
        await db.insert_solution(
            token,
            {
                "submission_id": request.submission_id,
                "problem_slug": request.problem.slug,
                "problem_title": request.problem.title,
                "problem_number": request.problem_number,
                "difficulty": request.problem.difficulty,
                "topic_tags": request.topic_tags,
                "language": request.language,
                "code": request.code,
                "summary": summary,
                "summary_model": response.model,
            },
        )
    except db.DbError as e:
        log.error("db: %s", e.log)
        raise HTTPException(e.status, e.detail) from None

    cost_usd = estimate_cost(response.model, response.usage)

    u = response.usage
    log.info(
        "solution user=%s submission=%d slug=%s provider=%s model=%s effort=%s in=%d out=%d "
        "reasoning=%d model_ms=%d cost=%s",
        user.id, request.submission_id, request.problem.slug, provider.name, response.model,
        SUMMARY_EFFORT, u.input_tokens, u.output_tokens, u.reasoning_tokens, model_ms,
        f"${cost_usd:.4f}" if cost_usd is not None else "n/a",
    )
    return SolutionResponse(summary=summary, already_saved=False, model=response.model, cost_usd=cost_usd)
