"""Vercel deployment integration: URLs, connection pooling, ASGI startup, database setup."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.session import make_engine

BACKEND = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_marketplace_database_url_uses_installed_driver(monkeypatch, scheme):
    monkeypatch.delenv("TPORT_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"{scheme}://user:secret@db.example/db?sslmode=require")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg://user:secret@db.example/db?sslmode=require"


def test_explicit_tport_database_takes_precedence(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://other:secret@other.example/db")
    monkeypatch.setenv("TPORT_DATABASE_URL", "postgresql://user:secret@db.example/db")
    assert "@db.example/" in Settings(_env_file=None).database_url
    assert Settings(_env_file=None, database_url="sqlite://").database_url == "sqlite://"


def test_serverless_connections_are_not_kept_idle(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    engine = make_engine("postgresql+psycopg://user:secret@db.example/db")
    assert isinstance(engine.pool, NullPool)
    engine.dispose()


def test_entrypoint_does_not_seed_or_migrate(monkeypatch):
    from app import main

    calls = []
    sentinel = object()
    monkeypatch.setenv("TPORT_DATABASE_URL", "postgresql://user:secret@db.example/db")
    monkeypatch.setenv("TPORT_CORS_ORIGINS", '["https://t-port.example"]')
    monkeypatch.setenv("TPORT_ENVIRONMENT", "development")
    monkeypatch.setattr(main, "create_app", lambda settings, **kw: calls.append((settings, kw)) or sentinel)
    spec = importlib.util.spec_from_file_location("vercel_entrypoint_test", BACKEND / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert calls[0][1] == {"seed": False} and module.app is sentinel
    assert calls[0][0].is_production and calls[0][0].secure_cookies


def test_release_setup_migrates_and_is_idempotent(tmp_path, monkeypatch):
    from scripts.vercel_setup import setup_database

    runtime = f"sqlite:///{(tmp_path / 'runtime.db').as_posix()}"
    direct = f"sqlite:///{(tmp_path / 'release.db').as_posix()}"
    monkeypatch.setenv("TPORT_DATABASE_URL", runtime)
    monkeypatch.setenv("TPORT_MIGRATION_DATABASE_URL", direct)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.chdir(tmp_path)  # migration paths must not depend on the current working directory
    setup_database()
    setup_database()
    engine = make_engine(direct)
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM locations")) > 0
        assert db.scalar(text("SELECT count(*) FROM providers")) > 0
        assert db.scalar(text("SELECT count(*) FROM users")) == 0
    assert "alembic_version" in inspect(engine).get_table_names()
    engine.dispose()
    assert not (tmp_path / "runtime.db").exists()
