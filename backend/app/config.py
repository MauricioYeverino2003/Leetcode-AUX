from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

# backend/.env, regardless of the working directory uvicorn was started from.
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # Which vendor answers /chat. The tutor (app/prompt.py) is the same either
    # way; only the API plumbing differs. See app/providers/.
    llm_provider: Literal["anthropic", "openai"] = "anthropic"

    # How hard the model thinks before answering. Both vendors accept exactly
    # these five levels. Unset = the provider's default. Reasoning tokens are
    # billed as output and are most of the latency, so for short hints "low"
    # is the first thing to try; raise it only if hint quality visibly drops.
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None

    # Where each model call is recorded as one JSON line (see app/benchmarks.py).
    # Relative to backend/. Set to an empty string to disable. The file holds
    # prompts and user code, so it is gitignored.
    benchmarks_path: str | None = "benchmarks/runs.jsonl"

    @property
    def benchmarks_file(self) -> Path | None:
        if not self.benchmarks_path:
            return None
        return BACKEND_DIR / self.benchmarks_path

    # Keys are optional so the server boots without them. A missing key
    # surfaces as a clear 503 on the first chat rather than a crash at startup.
    # If the Anthropic key is unset, its SDK also tries the process environment
    # and an `ant auth login` profile.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"

    openai_api_key: str | None = None
    openai_model: str = "gpt-5"

    # The model that writes solution summaries, if different from the chat
    # model (same vendor). Summaries are a small task and an import makes one
    # per solved problem, so a cheaper model here cuts that cost several-fold.
    # Unset = the chat model.
    summary_model: str | None = None

    # Where to fetch the public keys that verify Supabase access tokens
    # (<url>/auth/v1/.well-known/jwks.json). Current Supabase — local CLI and
    # hosted — signs tokens asymmetrically (ES256), so this is the normal path.
    supabase_url: str

    # The project's public anon key — the same one the extension ships. Sent as
    # the `apikey` header when the backend calls Supabase's REST API on a
    # user's behalf (see app/db.py). It identifies the project, not a user:
    # what a call may touch is decided by row-level security from the user's
    # own token. Optional so the server boots without it; saving solutions
    # answers 503 until it is set.
    supabase_anon_key: str | None = None

    # Only for a Supabase instance still configured to sign with a shared
    # secret (HS256). Leave empty otherwise.
    supabase_jwt_secret: str | None = None


settings = Settings()
