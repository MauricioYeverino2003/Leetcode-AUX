"""
Who is calling.

The extension sends the user's Supabase access token as a bearer token. This
verifies it locally — signature, expiry, audience — and hands the route a User.

This is the only thing between the public internet and the Anthropic key, so
it runs before anything else on every chat request.

Supabase signs access tokens asymmetrically (ES256) and publishes the public
keys at <project>/auth/v1/.well-known/jwks.json — the local CLI stack included,
which the first test run of this file established the hard way. Verification
fetches those keys once and caches them. A shared-secret (HS256) path is kept
for instances still configured that way; which one runs is decided by the
token's own `alg` header, against an explicit allowlist.
"""

from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .config import settings

ASYMMETRIC_ALGORITHMS = {"ES256", "RS256"}
SYMMETRIC_ALGORITHMS = {"HS256"}

# auto_error=False so a missing header gets our 401 below rather than
# FastAPI's default 403, which misdescribes the situation.
bearer = HTTPBearer(auto_error=False)


class User(BaseModel):
    id: str
    email: str | None = None


@lru_cache
def _jwks() -> jwt.PyJWKClient:
    url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, cache_keys=True)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _verify(token: str) -> dict:
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid token") from None

    if alg in ASYMMETRIC_ALGORITHMS:
        key = _jwks().get_signing_key_from_jwt(token).key
        algorithms = [alg]
    elif alg in SYMMETRIC_ALGORITHMS and settings.supabase_jwt_secret:
        key = settings.supabase_jwt_secret
        algorithms = [alg]
    else:
        raise _unauthorized("Unsupported token algorithm")

    return jwt.decode(
        token,
        key,
        algorithms=algorithms,
        # Supabase sets this for signed-in users. The anon key is also a JWT
        # from the same issuer, but with aud "anon" — this is what stops it
        # from passing as a user.
        audience="authenticated",
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    if credentials is None:
        raise _unauthorized("Missing bearer token")

    try:
        claims = _verify(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token expired") from None
    except jwt.PyJWKClientError:
        # Could not fetch keys, or the token's key id is unknown to the issuer.
        raise _unauthorized("Could not verify token signature") from None
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid token") from None

    return User(id=claims["sub"], email=claims.get("email"))


def user_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    _: User = Depends(current_user),
) -> str:
    """The caller's raw access token, for acting as them against Supabase.

    Depends on current_user so it is only ever handed out once verified. Kept
    out of User because /me echoes that model back.
    """
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    return credentials.credentials
