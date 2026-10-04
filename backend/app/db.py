"""
The database, reached through Supabase's REST API as the signed-in user.

Every call carries the user's own access token, so Postgres row-level security
decides what it can read and write — the backend holds no elevated database
credential to leak or misuse. The anon key in the `apikey` header is the
public project key the extension also ships; it says which project, not who.
"""

import httpx2

from .config import settings

TABLE = "solutions"

_client: httpx2.AsyncClient | None = None


class DbError(Exception):
    """A failure the route should turn into an HTTP response. Same shape as
    ProviderError: `detail` is for the client, `log` for the server log."""

    def __init__(self, status: int, detail: str, *, log: str | None = None):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.log = log or detail


def _get_client() -> httpx2.AsyncClient:
    global _client
    if _client is None:
        _client = httpx2.AsyncClient(
            base_url=settings.supabase_url.rstrip("/") + "/rest/v1",
            timeout=10.0,
        )
    return _client


async def _send(method: str, token: str, *, prefer: str | None = None, **kwargs) -> httpx2.Response:
    if not settings.supabase_anon_key:
        raise DbError(503, "Saving is not configured: set SUPABASE_ANON_KEY in backend/.env")

    headers = {"apikey": settings.supabase_anon_key, "Authorization": f"Bearer {token}"}
    if prefer:
        headers["Prefer"] = prefer

    try:
        response = await _get_client().request(method, f"/{TABLE}", headers=headers, **kwargs)
    except httpx2.HTTPError as e:
        raise DbError(502, "Could not reach the database", log=f"Supabase request failed: {e!r}") from None

    if response.is_error:
        raise DbError(
            502,
            "The database rejected the request",
            log=f"Supabase {response.status_code}: {response.text[:500]}",
        )
    return response


async def find_solution(token: str, submission_id: int) -> dict | None:
    """The caller's saved solution for this submission, if there is one. Row-
    level security limits the search to their own rows."""
    response = await _send(
        "GET",
        token,
        params={
            "submission_id": f"eq.{submission_id}",
            "select": "summary,summary_model",
            "limit": "1",
        },
    )
    rows = response.json()
    return rows[0] if rows else None


async def find_same_code(token: str, problem_slug: str, code: str) -> dict | None:
    """A solution the caller already saved for this problem with exactly this
    code — the same thing submitted again under a new submission id.

    Compared here rather than in the query: the code is far too long for a
    URL, and a user has only a handful of rows per problem.
    """
    response = await _send(
        "GET",
        token,
        params={
            "problem_slug": f"eq.{problem_slug}",
            "select": "summary,summary_model,code",
            "order": "created_at.desc",
        },
    )
    for row in response.json():
        if row["code"] == code:
            return row
    return None


# Everything recall needs — and not the code, which the tutor never sees.
RECALL_COLUMNS = "problem_slug,problem_title,difficulty,topic_tags,summary,created_at"


def _array_literal(values: list[str]) -> str:
    """A PostgREST array literal with every element double-quoted. Tags
    contain spaces ("Hash Table"); quoting all of them is simpler than
    deciding which need it."""
    quoted = ['"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' for v in values]
    return "{" + ",".join(quoted) + "}"


async def list_solutions_by_tags(token: str, tags: list[str], limit: int = 50) -> list[dict]:
    """The caller's solutions sharing at least one of these tags, newest
    first — `ov` is Postgres array overlap."""
    response = await _send(
        "GET",
        token,
        params={
            "topic_tags": f"ov.{_array_literal(tags)}",
            "select": RECALL_COLUMNS,
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    return response.json()


async def list_solutions_for_problem(token: str, problem_slug: str, limit: int = 5) -> list[dict]:
    """The caller's solutions to one problem, newest first."""
    response = await _send(
        "GET",
        token,
        params={
            "problem_slug": f"eq.{problem_slug}",
            "select": RECALL_COLUMNS,
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    return response.json()


async def insert_solution(token: str, row: dict) -> None:
    """Stores one solution as the caller. `user_id` is not sent: the table
    fills it in from the token. A submission that is already there is left
    alone rather than treated as an error, so two saves racing is harmless."""
    await _send(
        "POST",
        token,
        prefer="resolution=ignore-duplicates,return=minimal",
        params={"on_conflict": "user_id,submission_id"},
        json=row,
    )
