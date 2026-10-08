import logging
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import benchmarks, db, embeddings, recall
from .auth import User, current_user, user_token
from .config import settings
from .prices import estimate_cost
from .prompt import SUMMARY_PROMPT, solution_block
from .providers import ProviderError, get_provider
from .providers.base import REFUSAL_REPLY
from .schemas import (
    ChatRequest,
    ChatResponse,
    PriorRef,
    PriorSolution,
    SolutionRequest,
    SolutionResponse,
    Timing,
    Usage,
)

log = logging.getLogger("leetcode-aux")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="LeetCode AUX backend", version="0.4.0")

# Summaries are a small, bounded task, so they always run at the cheapest
# effort. LLM_EFFORT is tuned for hint quality and does not apply to them.
SUMMARY_EFFORT = "low"

# A typical summary call, for the estimate the panel shows before an import:
# instructions + problem + code in, a short reply plus low-effort reasoning
# out. Rounded figures from the backend log; the panel only says "about".
SUMMARY_TYPICAL_USAGE = Usage(
    input_tokens=700, output_tokens=400, cache_read_input_tokens=0, cache_creation_input_tokens=0
)


def summary_model() -> str:
    return settings.summary_model or get_provider().model

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
        "summary_model": summary_model(),
    }


@app.get("/me")
def me(user: User = Depends(current_user)) -> User:
    """Echoes the verified user. Exists so auth can be tested without spending a
    model call."""
    return user


async def _recall(token: str, request: ChatRequest) -> tuple[list[PriorSolution], str]:
    """Recall must never take the chat down with it: a database problem is
    logged and the tutor simply goes without. Returns the solutions and
    which way found them ("embedding", "tags", or "none")."""
    if request.problem is None:
        return [], "none"
    try:
        return await recall.recall(token, request.problem)
    except db.DbError as e:
        log.warning("recall skipped: %s", e.log)
        return [], "none"


@app.post("/chat")
async def chat(
    request: ChatRequest,
    http: Request,
    user: User = Depends(current_user),
    token: str = Depends(user_token),
) -> ChatResponse:
    provider = get_provider()
    prior, recall_mode = await _recall(token, request)

    model_started = perf_counter()
    try:
        response = await provider.chat(request, prior)
    except ProviderError as e:
        log.error("%s: %s", provider.name, e.log)
        raise HTTPException(e.status, e.detail) from None
    finished = perf_counter()

    response.timing = Timing(
        model_ms=round((finished - model_started) * 1000),
        backend_ms=round((finished - http.state.arrived) * 1000),
    )
    response.cost_usd = estimate_cost(response.model, response.usage)
    response.prior_solutions = [PriorRef(slug=s.slug, title=s.title, similarity=s.similarity) for s in prior]

    benchmarks.record(
        source="panel",
        user_id=user.id,
        provider=provider.name,
        request=request,
        response=response,
    )

    u, t = response.usage, response.timing
    log.info(
        "chat user=%s provider=%s model=%s effort=%s recall=%s recalled=%d in=%d out=%d reasoning=%d "
        "cache_read=%d cache_write=%d model_ms=%d backend_ms=%d cost=%s",
        user.id, provider.name, response.model, settings.llm_effort or "default", recall_mode, len(prior),
        u.input_tokens, u.output_tokens, u.reasoning_tokens,
        u.cache_read_input_tokens, u.cache_creation_input_tokens,
        t.model_ms, t.backend_ms,
        f"${response.cost_usd:.4f}" if response.cost_usd is not None else "n/a",
    )
    return response


@app.get("/solutions/slugs")
async def saved_solution_slugs(
    user: User = Depends(current_user),
    token: str = Depends(user_token),
) -> dict:
    """Which problems the caller already has solutions for, so the
    extension's import can skip them before fetching any code — plus what one
    summary is likely to cost, so the panel can say what an import will."""
    try:
        slugs = await db.list_solution_slugs(token)
    except db.DbError as e:
        log.error("db: %s", e.log)
        raise HTTPException(e.status, e.detail) from None

    model = summary_model()
    return {
        "slugs": slugs,
        "summary_model": model,
        "summary_cost_usd": estimate_cost(model, SUMMARY_TYPICAL_USAGE),
    }


# How many of a user's unindexed solutions one call to /solutions/embed
# handles. The panel keeps calling until none remain.
EMBED_BATCH = 50


@app.post("/solutions/embed")
async def embed_missing(
    user: User = Depends(current_user),
    token: str = Depends(user_token),
) -> dict:
    """Embeds up to EMBED_BATCH of the caller's saved solutions that have no
    embedding yet — the rows an import just added, or everything the first
    time. Returns how many it did and how many are left."""
    try:
        rows = await db.list_unembedded(token, EMBED_BATCH)
        if rows:
            vectors = await embeddings.embed([embeddings.solution_text(row) for row in rows])
            for row, vector in zip(rows, vectors):
                await db.set_embedding(token, row["id"], vector, settings.embedding_model)
        remaining = await db.count_unembedded(token)
    except db.DbError as e:
        log.error("db: %s", e.log)
        raise HTTPException(e.status, e.detail) from None
    except embeddings.EmbeddingError as e:
        log.error("embeddings: %s", e.log)
        raise HTTPException(e.status, e.detail) from None

    log.info("embed user=%s embedded=%d remaining=%d", user.id, len(rows), remaining)
    return {"embedded": len(rows), "remaining": remaining}


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
            model=settings.summary_model,
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

    row = {
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
        "statement": request.problem.statement,
        "submitted_at": request.submitted_at.isoformat() if request.submitted_at else None,
    }

    # Indexed for recall in the same insert when possible. If embedding fails
    # the row is still saved; /solutions/embed picks it up later.
    try:
        [vector] = await embeddings.embed([embeddings.solution_text(row)])
        row["embedding"] = vector
        row["embedding_model"] = settings.embedding_model
    except embeddings.EmbeddingError as e:
        log.warning("solution saved without embedding: %s", e.log)

    try:
        await db.insert_solution(token, row)
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
