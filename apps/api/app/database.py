from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


def _engine_url() -> str:
    return get_settings().database_url


connect_args = {"check_same_thread": False} if _engine_url().startswith("sqlite") else {}
engine = create_engine(_engine_url(), connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
