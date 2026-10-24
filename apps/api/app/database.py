from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


def build_engine(database_url: str):
    connect_args = (
        {"check_same_thread": False, "timeout": 30}
        if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def disable_driver_transaction_control(dbapi_connection, _connection_record) -> None:
            dbapi_connection.isolation_level = None
            dbapi_connection.execute("PRAGMA busy_timeout=30000")
            dbapi_connection.execute("PRAGMA journal_mode=WAL")

        @event.listens_for(engine, "begin")
        def emit_sqlite_begin(connection) -> None:
            connection.exec_driver_sql("BEGIN")
    return engine


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def configure_database(database_url: str) -> None:
    """Replace the bind deliberately; used by isolated tests and application factories."""
    global engine, SessionLocal
    engine.dispose()
    engine = build_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
