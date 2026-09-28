from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, regardless of the working directory uvicorn was started from.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # Which vendor answers /chat. The tutor (app/prompt.py) is the same either
    # way; only the API plumbing differs. See app/providers/.
    llm_provider: Literal["anthropic", "openai"] = "anthropic"

    # Keys are optional so the server boots without them. A missing key
    # surfaces as a clear 503 on the first chat rather than a crash at startup.
    # If the Anthropic key is unset, its SDK also tries the process environment
    # and an `ant auth login` profile.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"

    openai_api_key: str | None = None
    openai_model: str = "gpt-5"

    # Where to fetch the public keys that verify Supabase access tokens
    # (<url>/auth/v1/.well-known/jwks.json). Current Supabase — local CLI and
    # hosted — signs tokens asymmetrically (ES256), so this is the normal path.
    supabase_url: str

    # Only for a Supabase instance still configured to sign with a shared
    # secret (HS256). Leave empty otherwise.
    supabase_jwt_secret: str | None = None


settings = Settings()
