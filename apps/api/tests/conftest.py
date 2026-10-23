from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("PDF_IMPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("PRIVATE_STORAGE_ROOT", str(tmp_path / "private"))
    monkeypatch.setenv("PRIVATE_API_TOKEN", "test-private-token")
    monkeypatch.setenv("PRIVATE_OWNER_ID", "test-owner")
    from app.config import get_settings
    from app import database
    from app.database import Base
    from app.main import create_app

    get_settings.cache_clear()
    database.configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=database.engine)
    with TestClient(create_app()) as test_client:
        test_client.headers.update({"Authorization": "Bearer test-private-token"})
        yield test_client
