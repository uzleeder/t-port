"""FastAPI application factory (modular monolith wiring)."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from contextlib import asynccontextmanager
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.ai.llm import AnthropicInterpreter, InterpreterError
from app.ai.service import AssistantService
from app.api.v1.account_routes import router as account_router
from app.api.v1.ai_routes import router as ai_router
from app.api.v1.routes import router as v1_router
from app.api.v1.schemas import HealthResponse, ProviderOut
from app.core.clock import Clock, SystemClock
from app.core.config import Settings, get_settings
from app.core.errors import error_body, install_error_handlers
from app.data.reference import LOCATIONS, STATIONS
from app.db.repositories import ReferenceRepository
from app.db.session import make_engine, make_session_factory, transaction
from app.providers.base import ProviderAdapter
from app.providers.demo.adapter import DEMO_PROVIDER, DemoAdapter
from app.providers.registry import REGISTRATIONS
from app.providers.stored import StoredTimetableAdapter
from app.services.auth import AuthService
from app.services.catalog import LocationCatalog
from app.services.freshness import FreshnessPolicy
from app.services.search import SearchService
from app.services.transfers import TransferPolicy

VERSION = "0.8.0"
log = logging.getLogger("tport")

_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def seed_reference(factory: sessionmaker[Session]) -> None:
    """Idempotent upsert of reference geography and the provider registry."""
    with transaction(factory) as db:
        repo = ReferenceRepository(db)
        repo.sync_locations(LOCATIONS, STATIONS)
        for reg in REGISTRATIONS:
            repo.upsert_provider(
                reg.info, access_basis=reg.access_basis, update_frequency=reg.update_frequency
            )


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    providers: Sequence[ProviderAdapter] | None = None,
    session_factory: sessionmaker[Session] | None = None,
    llm: AnthropicInterpreter | None = None,
    seed: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    clock = clock or SystemClock()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if session_factory is None:
        session_factory = make_session_factory(
            make_engine(settings.database_url, echo=settings.database_echo)
        )

    catalog = LocationCatalog(LOCATIONS, STATIONS)
    if providers is None:
        providers = []
        if settings.enable_demo_provider:
            if settings.demo_provider_mode == "stored":
                live = DemoAdapter(catalog, clock)
                providers.append(
                    StoredTimetableAdapter(
                        DEMO_PROVIDER, catalog, session_factory, live.supported_location_ids()
                    )
                )
            else:
                providers.append(DemoAdapter(catalog, clock))

    if llm is None and settings.ai_engine == "anthropic":
        if settings.ai_api_key:
            try:
                llm = AnthropicInterpreter(
                    settings.ai_api_key, settings.ai_model, settings.ai_timeout_seconds
                )
            except InterpreterError as exc:
                log.warning("AI engine unavailable (%s); using deterministic parser", exc.code)
        else:
            log.warning(
                "TPORT_AI_ENGINE=anthropic but TPORT_AI_API_KEY is not set; using deterministic parser"
            )

    search = SearchService(
        catalog,
        providers,
        clock,
        FreshnessPolicy(
            timedelta(seconds=settings.data_stale_after_seconds),
            timedelta(seconds=settings.data_expire_after_seconds),
        ),
        market_timezone=settings.market_timezone,
        max_days_ahead=settings.search_max_days_ahead,
        max_page_size=settings.search_max_page_size,
        transfer_policy=TransferPolicy(
            same_station_minutes=settings.transfer_min_minutes_same_station,
            station_change_minutes=settings.transfer_min_minutes_station_change,
            before_flight_minutes=settings.transfer_min_minutes_to_flight,
            max_wait_minutes=settings.transfer_max_wait_minutes,
        ),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if seed:
            try:
                seed_reference(session_factory)
            except Exception as exc:  # noqa: BLE001 - search still works without a database
                log.error("could not seed reference data: %s", type(exc).__name__)
        yield

    app = FastAPI(
        title="T-Port API",
        version=VERSION,
        description=(
            "Deterministic multimodal transit search for Uzbekistan. Phase 1 serves a clearly "
            "labelled DEMO dataset. T-Port is a planning tool: it does not sell tickets."
        ),
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.clock = clock
    app.state.catalog = catalog
    app.state.providers = list(providers)
    app.state.session_factory = session_factory
    app.state.search = search
    app.state.auth = AuthService(timedelta(hours=settings.session_ttl_hours))
    app.state.assistant = AssistantService(
        catalog, search, llm=llm, max_days_ahead=settings.search_max_days_ahead
    )

    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        allow_credentials=True,
    )

    trusted_origins = {o.rstrip("/") for o in settings.cors_origins}
    # Fixed-window per-IP rate limits. In-memory: correct for a single process only.
    windows: dict[tuple[str, str], tuple[int, int]] = {}
    strict_prefixes = {
        "/api/v1/auth/": settings.auth_rate_limit_per_minute,
        "/api/v1/ai/": settings.ai_rate_limit_per_minute,
    }

    def over_limit(ip: str, bucket: str, limit: int) -> bool:
        minute = int(time.time() // 60)
        win, count = windows.get((ip, bucket), (minute, 0))
        count = count + 1 if win == minute else 1
        windows[(ip, bucket)] = (minute, count)
        if len(windows) > 20_000:
            windows.clear()
        return count > limit

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/"):
            # Reject cross-site state-changing requests (defence in depth with SameSite + CSRF token).
            origin = request.headers.get("origin")
            if request.method in _UNSAFE and origin:
                host = request.headers.get("host", "")
                if origin.rstrip("/") not in trusted_origins and urlsplit(origin).netloc != host:
                    return JSONResponse(error_body("forbidden", "Cross-origin request rejected."), 403)
            try:
                length = int(request.headers.get("content-length") or 0)
            except ValueError:
                length = 0
            if length > 64 * 1024:
                return JSONResponse(error_body("payload_too_large", "Request body too large."), 413)
            ip = request.client.host if request.client else "unknown"
            limited = over_limit(ip, "api", settings.rate_limit_per_minute)
            for prefix, limit in strict_prefixes.items():
                if path.startswith(prefix) and request.method in _UNSAFE:
                    limited = over_limit(ip, prefix, limit) or limited
            if limited:
                return JSONResponse(
                    error_body("rate_limited", "Too many requests. Please wait a minute."),
                    429,
                    headers={"Retry-After": "60"},
                )
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            # Access log without query strings, cookies or bodies (they may contain personal data).
            elapsed = (time.perf_counter() - started) * 1000
            log.info("%s %s %s %.0fms", request.method, path, response.status_code, elapsed)
        return response

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> JSONResponse:
        db_ok = True
        try:
            with session_factory() as db:
                db.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001
            db_ok = False
        assistant = app.state.assistant
        body = HealthResponse(
            status="ok" if db_ok else "degraded",
            version=VERSION,
            environment=settings.environment,
            database="ok" if db_ok else "unavailable",
            ai_engine=assistant.llm.engine if assistant.llm else "rules",
            providers=[
                ProviderOut(
                    id=p.info.id, name=p.info.name, is_demo=p.info.is_demo, attribution=p.info.attribution
                )
                for p in app.state.providers
            ],
        )
        return JSONResponse(body.model_dump(), status_code=200 if db_ok else 503)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"name": "T-Port API", "version": VERSION, "health": "/health"}

    app.include_router(v1_router)
    app.include_router(account_router)
    app.include_router(ai_router)
    return app


def __getattr__(name: str):
    # `uvicorn app.main:app` builds the app lazily, so importing this module has no side effects.
    if name == "app":
        instance = create_app()
        globals()["app"] = instance
        return instance
    raise AttributeError(name)
