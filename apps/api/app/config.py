from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./korean_learning.db"
    pdf_import_root: Path = Path("./imports")
    private_storage_root: Path = Path("./private-data")
    private_api_token: str | None = None
    private_owner_id: str = "local-owner"
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_import_root(self) -> Path:
        return self.pdf_import_root.expanduser().resolve()

    @property
    def resolved_private_storage_root(self) -> Path:
        return self.private_storage_root.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
