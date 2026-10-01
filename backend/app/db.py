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
