"""Application settings, loaded from environment variables (and .env for local dev)."""
from functools import lru_cache
from importlib.util import find_spec

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # LLM (NVIDIA-hosted, OpenAI-compatible)
    nvidia_api_key: SecretStr = SecretStr("")
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3-super-120b-a12b"
    llm_timeout_s: float = 180.0
    llm_max_retries: int = 3
    llm_max_output_tokens: int = 4096

    # Long-document map-reduce sizing (~4 chars/token)
    single_pass_chars: int = 100_000
    chunk_chars: int = 60_000
    reduce_max_chars: int = 100_000
    llm_workers: int = 4

    # Local model
    finbert_model: str = "ProsusAI/finbert"
    extreme_threshold: float = 0.85
    max_sentences: int = 6000

    # API / jobs
    max_upload_mb: int = 50
    max_concurrent_jobs: int = 2
    max_queued_jobs: int = 20
    job_ttl_seconds: int = 3600
    cors_origins: str = ""  # comma-separated; empty = same-origin only
    log_level: str = "INFO"

    @property
    def llm_configured(self) -> bool:
        return bool(self.nvidia_api_key.get_secret_value().strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def local_model_available(self) -> bool:
        return find_spec("torch") is not None and find_spec("transformers") is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
