from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str | None = None
    dezny_api_token: str | None = None
    dezny_api_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_allowed_user_ids: str = ""
    nvidia_api_key: str | None = None
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_chat_model: str = "nvidia/llama-3.3-nemotron-super-49b-v1"
    nvidia_embedding_model: str = "nvidia/nv-embedqa-e5-v5"
    embedding_dimensions: int = 1024
    tavily_api_key: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "auto"
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    local_storage_dir: Path = Path("./data/uploads")
    max_upload_mb: int = 20
    ocr_enabled: bool = True
    log_level: str = "INFO"

    @property
    def allowed_telegram_user_ids(self) -> set[int]:
        ids: set[int] = set()
        for value in self.telegram_allowed_user_ids.split(","):
            value = value.strip()
            if value:
                try:
                    ids.add(int(value))
                except ValueError as exc:
                    raise ValueError("TELEGRAM_ALLOWED_USER_IDS must contain comma-separated integers") from exc
        return ids

    @property
    def object_storage_enabled(self) -> bool:
        return all((self.s3_endpoint_url, self.s3_bucket, self.s3_access_key_id, self.s3_secret_access_key))


@lru_cache
def get_settings() -> Settings:
    return Settings()
