import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PDF_IMPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("PRIVATE_STORAGE_ROOT", str(tmp_path / "private"))
    monkeypatch.setenv("PRIVATE_API_TOKEN", "test-private-token")
    monkeypatch.setenv("PRIVATE_OWNER_ID", "test-owner")
    from app.config import get_settings
    from app import database
    from app.database import Base
    from app.main import create_app

    get_settings.cache_clear()
    database.configure_database(database_url)
    if database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=database.engine)
    else:
        table_names = ", ".join(
            f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables)
        )
        with database.engine.begin() as connection:
            connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    with TestClient(create_app()) as test_client:
        test_client.headers.update({"Authorization": "Bearer test-private-token"})
        yield test_client
