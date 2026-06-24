from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    cors_origins: list[str] = ["http://localhost:3000"]

    data_dir: Path = REPO_ROOT / "data"
    raw_data_dir: Path = REPO_ROOT / "data" / "raw"
    cache_dir: Path = REPO_ROOT / "data" / "cache"

    openfda_base_url: str = "https://api.fda.gov"
    openfda_cache_ttl_seconds: int = 3600

    # Phase 1 scope decision: big 3 wholesale distributors only.
    # Expanded to the full DSCSA list in a later phase.
    distributor_scope: str = "big3"
    big3_distributor_names: tuple[str, ...] = (
        "mckesson",
        "cardinal health",
        "amerisourcebergen",
        "cencora",  # AmerisourceBergen renamed to Cencora in 2023
    )


settings = Settings()
