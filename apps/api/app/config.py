from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./korean_learning.db"
    pdf_import_root: Path = Path("./imports")
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_import_root(self) -> Path:
        return self.pdf_import_root.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
