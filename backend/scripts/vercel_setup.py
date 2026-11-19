"""Explicit release step: migrate and seed the selected environment's database.

Run from backend/: python -m scripts.vercel_setup
Never called by Vercel request handling or the frontend build. Run once per environment,
after reviewing the migrations and taking a backup. Never run two setup commands concurrently.
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.db.session import make_engine, make_session_factory
from app.main import seed_reference

BACKEND = Path(__file__).resolve().parents[1]


def setup_database() -> None:
    settings = Settings()
    # Runtime uses a pooled URL; migrations should use the provider's direct URL when available.
    url = (
        os.environ.get("TPORT_MIGRATION_DATABASE_URL")
        or os.environ.get("DATABASE_URL_UNPOOLED")
        or settings.database_url
    )
    parsed = make_url(url)
    if parsed.drivername in ("postgres", "postgresql"):
        parsed = parsed.set(drivername="postgresql+psycopg")
    url = parsed.render_as_string(hide_password=False)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    engine = make_engine(url)
    try:
        seed_reference(make_session_factory(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        setup_database()
    except Exception as exc:
        # SQLAlchemy errors can include URLs and connection details: don't print their messages.
        raise SystemExit(
            f"Database setup failed ({type(exc).__name__}). Check database access and migrations."
        ) from None
    print("Database migrations and reference seed completed.")
