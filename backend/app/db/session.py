"""Engine and session factory."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


def make_engine(url: str, *, echo: bool = False) -> Engine:
    kwargs: dict = {"echo": echo, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:") or "mode=memory" in url:
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
    else:
        # Fail fast when the database is unreachable instead of hanging requests for minutes.
        kwargs.update(
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=10,
            connect_args={"connect_timeout": 5},
        )
        if os.environ.get("VERCEL") == "1":
            # Use the managed database's external pooler; avoid 15 idle connections per instance.
            for key in ("pool_size", "max_overflow", "pool_timeout"):
                kwargs.pop(key)
            kwargs["poolclass"] = NullPool
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores FKs unless enabled per connection
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False, autoflush=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session, session.begin():
        yield session
