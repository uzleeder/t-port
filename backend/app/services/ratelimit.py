"""Fixed-window rate limiting shared by every API worker, stored in PostgreSQL.

Used for low-volume, abuse-sensitive endpoints (auth, AI) and per-account failed-login
throttling. Keys are SHA-256 hashes: no IP addresses or emails are stored. The high-volume
general API limit stays in process memory (see docs/security.md for the trade-off).
If the database is unreachable the limiter fails open (and logs), so an outage of the
limiter never locks every user out; the in-memory limit still applies.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from app.db import models as m
from app.db.session import transaction

log = logging.getLogger("tport.ratelimit")


def limiter_key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


class SharedRateLimiter:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    @staticmethod
    def _window(now: datetime, seconds: int) -> int:
        return int(now.timestamp()) // seconds

    def hit(self, key: str, window_seconds: int, now: datetime) -> int:
        """Count one event in the current window; returns the count including this one."""
        window = self._window(now, window_seconds)
        try:
            with transaction(self._factory) as db:
                dialect = db.bind.dialect.name if db.bind else "postgresql"
                insert = sqlite_insert if dialect == "sqlite" else pg_insert
                table = m.RateLimitCounter.__table__
                expires = datetime.fromtimestamp((window + 1) * window_seconds, tz=UTC)
                stmt = insert(table).values(key=key, window=window, count=1, expires_at=expires)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["key"],
                    set_={
                        # Same window: increment. New window: restart at 1.
                        "count": case((table.c.window == stmt.excluded.window, table.c.count + 1), else_=1),
                        "window": stmt.excluded.window,
                        "expires_at": stmt.excluded.expires_at,
                    },
                ).returning(table.c.count)
                return int(db.execute(stmt).scalar_one())
        except Exception as exc:  # noqa: BLE001 - fail open, see module docstring
            log.warning("shared rate limiter unavailable: %s", type(exc).__name__)
            return 0

    def peek(self, key: str, window_seconds: int, now: datetime) -> int:
        try:
            with self._factory() as db:
                row = db.execute(
                    select(m.RateLimitCounter.count, m.RateLimitCounter.window).where(
                        m.RateLimitCounter.key == key
                    )
                ).first()
        except Exception as exc:  # noqa: BLE001
            log.warning("shared rate limiter unavailable: %s", type(exc).__name__)
            return 0
        if row is None or row.window != self._window(now, window_seconds):
            return 0
        return int(row.count)

    def purge(self, now: datetime) -> int:
        """Remove counters whose window has ended (housekeeping)."""
        with transaction(self._factory) as db:
            return (
                db.execute(delete(m.RateLimitCounter).where(m.RateLimitCounter.expires_at < now)).rowcount
                or 0
            )
