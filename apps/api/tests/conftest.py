from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("PDF_IMPORT_ROOT", str(tmp_path))
    from app.config import get_settings
    from app import database
    from app.database import Base
    from app.main import create_app

    get_settings.cache_clear()
    database.configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=database.engine)
    with TestClient(create_app()) as test_client:
        yield test_client
