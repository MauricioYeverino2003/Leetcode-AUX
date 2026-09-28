import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import User, current_user
from .config import settings
from .providers import ProviderError, get_provider
from .schemas import ChatRequest, ChatResponse

log = logging.getLogger("leetcode-aux")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="LeetCode AUX backend", version="0.2.0")

# The side panel runs on chrome-extension://<id>/ — 32 letters a–p. In practice
# Chrome skips CORS for hosts the extension holds host_permissions for, but
# any other client (a web dashboard, later) needs this, and it costs nothing.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^chrome-extension://[a-p]{32}$",
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health() -> dict:
    provider = get_provider()
    return {"status": "ok", "provider": provider.name, "model": provider.model}


@app.get("/me")
def me(user: User = Depends(current_user)) -> User:
    """Echoes the verified user. Exists so auth can be tested without spending a
    model call."""
    return user


@app.post("/chat")
async def chat(request: ChatRequest, user: User = Depends(current_user)) -> ChatResponse:
    provider = get_provider()

    try:
        response = await provider.chat(request)
    except ProviderError as e:
        log.error("%s: %s", provider.name, e.log)
        raise HTTPException(e.status, e.detail) from None

    # The seed of usage_log: everything needed to know what a hint costs.
    u = response.usage
    log.info(
        "chat user=%s provider=%s model=%s in=%d out=%d cache_read=%d cache_write=%d",
        user.id, provider.name, response.model, u.input_tokens, u.output_tokens,
        u.cache_read_input_tokens, u.cache_creation_input_tokens,
    )
    return response
