from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Which LLM drives the agent loop. Same 8 tools, same system prompt,
    # same render_component contract either way -- see app/agent/loop.py.
    agent_provider: str = "anthropic"  # "anthropic" | "gemini" | "openai"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    cors_origins: list[str] = ["http://localhost:3000"]

    data_dir: Path = REPO_ROOT / "data"
    raw_data_dir: Path = REPO_ROOT / "data" / "raw"
    cache_dir: Path = REPO_ROOT / "data" / "cache"

    openfda_base_url: str = "https://api.fda.gov"
    openfda_cache_ttl_seconds: int = 3600


settings = Settings()
