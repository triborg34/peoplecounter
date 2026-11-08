"""Engine / session management.

The URL decides the backend; switching to PostgreSQL is a single config value.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from .base import Base

log = logging.getLogger(__name__)


def _make_engine(url: str, echo: bool = False) -> Engine:
    if url.startswith("sqlite"):
        path = url.split("sqlite:///", 1)[-1]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            url,
            echo=echo,
            future=True,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _record):  # pragma: no cover - driver level
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    # PostgreSQL / other SQLAlchemy URLs
    return create_engine(url, echo=echo, future=True, pool_pre_ping=True, pool_size=10, max_overflow=20)


class Database:
    """Owns the SQLAlchemy engine and session factory."""

    def __init__(self, url: Optional[str] = None, echo: Optional[bool] = None):
        settings = get_settings()
        self.url = url or settings.database_url
        self.echo = settings.db_echo if echo is None else echo
        self.engine: Engine = _make_engine(self.url, self.echo)
        self._session_factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False, future=True)

    # -- schema ---------------------------------------------------------
    def create_all(self) -> None:
        from . import models  # noqa: F401  (register mappers)

        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        Base.metadata.drop_all(self.engine)

    # -- sessions -------------------------------------------------------
    @property
    def session_factory(self) -> sessionmaker:
        return self._session_factory

    def session(self) -> Session:
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


_default_db: Optional[Database] = None


def get_database() -> Database:
    global _default_db
    if _default_db is None:
        _default_db = Database()
    return _default_db


def set_database(db: Optional[Database]) -> None:
    global _default_db
    _default_db = db
