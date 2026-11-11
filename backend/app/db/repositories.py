"""Data-access layer. Repositories take a SQLAlchemy ``Session`` and never commit;
the caller owns the transaction (see ``app.db.session.transaction``)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import models as m
from app.domain.models import (
    Departure,
    Location,
    Offer,
    ProviderInfo,
    ScheduleType,
    Station,
    StationKind,
    TransportMode,
)


# --- reference data ---------------------------------------------------------------------
class ReferenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def sync_locations(self, locations: Iterable[Location], stations: Iterable[Station]) -> None:
        """Idempotent upsert of the reference geography."""
        for loc in locations:
            row = self.db.get(m.LocationRow, loc.id) or m.LocationRow(id=loc.id)
            row.name, row.country_code, row.region = loc.name, loc.country_code, loc.region
            row.timezone = loc.timezone
            row.latitude = Decimal(str(loc.latitude)) if loc.latitude is not None else None
            row.longitude = Decimal(str(loc.longitude)) if loc.longitude is not None else None
            row.aliases = list(loc.aliases)
            self.db.add(row)
        self.db.flush()
        for st in stations:
            row = self.db.get(m.StationRow, st.id) or m.StationRow(id=st.id)
            row.location_id, row.name, row.kind, row.code = st.location_id, st.name, st.kind.value, st.code
            self.db.add(row)
        self.db.flush()

    def upsert_provider(self, info: ProviderInfo, *, access_basis: str, update_frequency: str | None) -> None:
        row = self.db.get(m.Provider, info.id) or m.Provider(id=info.id)
        row.name, row.is_demo, row.attribution = info.name, info.is_demo, info.attribution
        row.website, row.booking_hosts = info.website, sorted(info.booking_hosts)
        row.access_basis, row.update_frequency = access_basis, update_frequency
        self.db.add(row)
        self.db.flush()

    def load_locations(self) -> tuple[list[Location], list[Station]]:
        locs = [
            Location(
                r.id,
                r.name,
                r.country_code,
                r.region,
                r.timezone,
                float(r.latitude) if r.latitude is not None else None,
                float(r.longitude) if r.longitude is not None else None,
                tuple(r.aliases or ()),
            )
            for r in self.db.scalars(select(m.LocationRow).order_by(m.LocationRow.name))
        ]
        stations = [
            Station(r.id, r.name, r.location_id, StationKind(r.kind), r.code)
            for r in self.db.scalars(select(m.StationRow).order_by(m.StationRow.id))
        ]
        return locs, stations


# --- accounts ---------------------------------------------------------------------------
class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: uuid.UUID) -> m.User | None:
        return self.db.get(m.User, user_id)

    def get_by_email(self, email: str) -> m.User | None:
        return self.db.scalar(select(m.User).where(m.User.email == email.strip().lower()))

    def create(self, email: str, password_hash: str, display_name: str | None) -> m.User:
        user = m.User(email=email.strip().lower(), password_hash=password_hash, display_name=display_name)
        self.db.add(user)
        self.db.flush()
        return user

    def delete(self, user: m.User) -> None:
        """Removes the account, its sessions and saved journeys. Activity rows keep no user link."""
        self.db.execute(delete(m.SavedJourney).where(m.SavedJourney.user_id == user.id))
        self.db.execute(delete(m.Session).where(m.Session.user_id == user.id))
        self.db.execute(
            update(m.JourneySearch).where(m.JourneySearch.user_id == user.id).values(user_id=None)
        )
        self.db.execute(update(m.AIRequest).where(m.AIRequest.user_id == user.id).values(user_id=None))
        self.db.execute(delete(m.User).where(m.User.id == user.id))


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self, user_id: uuid.UUID, token_hash: str, csrf_token: str, now: datetime, expires_at: datetime
    ) -> m.Session:
        s = m.Session(
            user_id=user_id,
            token_hash=token_hash,
            csrf_token=csrf_token,
            created_at=now,
            last_seen_at=now,
            expires_at=expires_at,
        )
        self.db.add(s)
        self.db.flush()
        return s

    def get_active(self, token_hash: str, now: datetime) -> m.Session | None:
        return self.db.scalar(
            select(m.Session)
            .options(selectinload(m.Session.user))
            .where(
                m.Session.token_hash == token_hash,
                m.Session.revoked_at.is_(None),
                m.Session.expires_at > now,
            )
        )

    def revoke(self, session_id: uuid.UUID, now: datetime) -> None:
        self.db.execute(update(m.Session).where(m.Session.id == session_id).values(revoked_at=now))

    def purge_expired(self, now: datetime) -> int:
        result = self.db.execute(
            delete(m.Session).where((m.Session.expires_at <= now) | m.Session.revoked_at.is_not(None))
        )
        return result.rowcount or 0


class SavedJourneyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: uuid.UUID, limit: int, offset: int) -> tuple[list[m.SavedJourney], int]:
        base = select(m.SavedJourney).where(m.SavedJourney.user_id == user_id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self.db.scalars(
            base.order_by(m.SavedJourney.created_at.desc(), m.SavedJourney.id).limit(limit).offset(offset)
        ).all()
        return list(rows), total

    def get_for_user(self, user_id: uuid.UUID, saved_id: uuid.UUID) -> m.SavedJourney | None:
        return self.db.scalar(
            select(m.SavedJourney).where(m.SavedJourney.id == saved_id, m.SavedJourney.user_id == user_id)
        )

    def find(self, user_id: uuid.UUID, journey_id: str) -> m.SavedJourney | None:
        return self.db.scalar(
            select(m.SavedJourney).where(
                m.SavedJourney.user_id == user_id, m.SavedJourney.journey_id == journey_id
            )
        )

    def count_for_user(self, user_id: uuid.UUID) -> int:
        return (
            self.db.scalar(
                select(func.count()).select_from(m.SavedJourney).where(m.SavedJourney.user_id == user_id)
            )
            or 0
        )

    def create(self, **fields: Any) -> m.SavedJourney:
        row = m.SavedJourney(**fields)
        self.db.add(row)
        self.db.flush()
        return row

    def delete(self, row: m.SavedJourney) -> None:
        self.db.delete(row)
        self.db.flush()


class ActivityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_search(self, **fields: Any) -> None:
        self.db.add(m.JourneySearch(**fields))

    def purge_older_than(self, cutoff: datetime) -> tuple[int, int]:
        searches = self.db.execute(delete(m.JourneySearch).where(m.JourneySearch.created_at < cutoff))
        ai = self.db.execute(delete(m.AIRequest).where(m.AIRequest.created_at < cutoff))
        return searches.rowcount or 0, ai.rowcount or 0

    def record_ai_request(self, **fields: Any) -> None:
        self.db.add(m.AIRequest(**fields))

    def recent_searches(self, user_id: uuid.UUID, limit: int = 5) -> list[m.JourneySearch]:
        return list(
            self.db.scalars(
                select(m.JourneySearch)
                .where(m.JourneySearch.user_id == user_id)
                .order_by(m.JourneySearch.created_at.desc())
                .limit(limit)
            )
        )


# --- timetable (stored provider data) ------------------------------------------------------
class TimetableRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def start_import(
        self, provider_id: str, source_reference: str, now: datetime, trigger: str = "manual"
    ) -> m.DataImport:
        imp = m.DataImport(
            provider_id=provider_id, source_reference=source_reference, started_at=now, trigger=trigger[:16]
        )
        self.db.add(imp)
        self.db.flush()
        return imp

    def finish_import(
        self,
        imp: m.DataImport,
        now: datetime,
        *,
        departures: int,
        offers: int,
        source_updated_at: datetime | None,
        error: str | None = None,
        retries: int = 0,
        rejected_records: int = 0,
        status: str | None = None,
        diagnostics: list[dict] | None = None,
    ) -> None:
        imp.finished_at = now
        imp.status = status or ("failed" if error else "succeeded")
        imp.departures_count, imp.offers_count = departures, offers
        imp.source_updated_at = source_updated_at
        imp.error_message = error[:2000] if error else None
        imp.retries, imp.rejected_records = retries, rejected_records
        imp.diagnostics = diagnostics[:50] if diagnostics else None
        if imp.started_at:
            imp.duration_ms = int((now - imp.started_at).total_seconds() * 1000)
        self.db.flush()

    def set_status(self, import_id: uuid.UUID, status: str) -> None:
        self.db.execute(update(m.DataImport).where(m.DataImport.id == import_id).values(status=status))

    def update_progress(self, import_id: uuid.UUID, done: int, total: int) -> bool:
        """Record progress; returns True if cancellation was requested."""
        self.db.execute(
            update(m.DataImport)
            .where(m.DataImport.id == import_id)
            .values(requests_done=done, requests_total=total)
        )
        return bool(self.db.scalar(select(m.DataImport.cancel_requested).where(m.DataImport.id == import_id)))

    def request_cancel(self, provider_id: str) -> int:
        """Ask every unfinished import of a provider to stop at its next checkpoint."""
        result = self.db.execute(
            update(m.DataImport)
            .where(
                m.DataImport.provider_id == provider_id,
                m.DataImport.status.in_(["pending", "running", "validating"]),
            )
            .values(cancel_requested=True)
        )
        return result.rowcount or 0

    def recent_imports(self, provider_id: str, limit: int = 20) -> list[m.DataImport]:
        return list(
            self.db.scalars(
                select(m.DataImport)
                .where(m.DataImport.provider_id == provider_id)
                .order_by(m.DataImport.started_at.desc())
                .limit(limit)
            )
        )

    # -- import locks --------------------------------------------------------------------
    def acquire_lock(self, provider_id: str, holder: str, now: datetime, ttl: timedelta) -> bool:
        """True if ``holder`` now owns the provider's import lock (new, re-entrant or taken over)."""
        lock = self.db.get(m.ProviderImportLock, provider_id, with_for_update=True)
        if lock is not None and lock.holder != holder and lock.expires_at > now:
            return False
        try:
            with self.db.begin_nested():  # savepoint: a lost insert race leaves the outer txn usable
                if lock is None:
                    self.db.add(
                        m.ProviderImportLock(
                            provider_id=provider_id, holder=holder, acquired_at=now, expires_at=now + ttl
                        )
                    )
                else:
                    lock.holder, lock.acquired_at, lock.expires_at = holder, now, now + ttl
        except IntegrityError:  # another process inserted the lock first
            return False
        return True

    def release_lock(self, provider_id: str, holder: str) -> None:
        self.db.execute(
            delete(m.ProviderImportLock).where(
                m.ProviderImportLock.provider_id == provider_id, m.ProviderImportLock.holder == holder
            )
        )

    def replace_window(
        self,
        provider_id: str,
        start: date,
        end: date,
        departures: Sequence[Departure],
        offers: Sequence[Offer],
        imp: m.DataImport,
        travel_dates: dict[str, date],
        timezone: str,
    ) -> None:
        """Replace this provider's departures in [start, end] with a fresh snapshot."""
        self.db.execute(
            delete(m.DepartureRow).where(
                m.DepartureRow.provider_id == provider_id,
                m.DepartureRow.travel_date >= start,
                m.DepartureRow.travel_date <= end,
            )
        )
        by_dep: dict[str, list[Offer]] = {}
        for o in offers:
            by_dep.setdefault(o.departure_id, []).append(o)
        for d in departures:
            row = m.DepartureRow(
                provider_id=provider_id,
                external_id=d.id,
                data_import_id=imp.id,
                service_code=d.service_code,
                operator_name=d.operator_name,
                mode=d.mode.value,
                schedule_type=d.schedule_type.value,
                origin_station_id=d.origin_station_id,
                destination_station_id=d.destination_station_id,
                travel_date=travel_dates[d.id],
                departure_tz=timezone,
                departure_utc=d.departure_utc,
                arrival_utc=d.arrival_utc,
                duration_minutes=d.duration_minutes,
                retrieved_at=d.retrieved_at,
                source_updated_at=d.source_updated_at,
            )
            row.offers = [
                m.OfferRow(
                    provider_id=provider_id,
                    external_id=o.id,
                    fare_name=o.fare_name,
                    price=o.price,
                    price_max=o.price_max,
                    currency=o.currency,
                    is_estimate=o.is_estimate,
                    booking_url=o.booking_url,
                    retrieved_at=o.retrieved_at,
                    source_updated_at=o.source_updated_at,
                )
                for o in by_dep.get(d.id, [])
            ]
            self.db.add(row)
        self.db.flush()

    def departures(
        self,
        provider_id: str,
        origin_station_ids: Sequence[str],
        destination_station_ids: Sequence[str],
        travel_date: date,
        modes: frozenset[TransportMode],
    ) -> list[Departure]:
        q = select(m.DepartureRow).where(
            m.DepartureRow.provider_id == provider_id,
            m.DepartureRow.origin_station_id.in_(origin_station_ids),
            m.DepartureRow.destination_station_id.in_(destination_station_ids),
            m.DepartureRow.travel_date == travel_date,
        )
        if modes:
            q = q.where(m.DepartureRow.mode.in_([x.value for x in modes]))
        return [_to_departure(r) for r in self.db.scalars(q.order_by(m.DepartureRow.id))]

    def departure(self, provider_id: str, external_id: str) -> Departure | None:
        row = self.db.scalar(
            select(m.DepartureRow).where(
                m.DepartureRow.provider_id == provider_id, m.DepartureRow.external_id == external_id
            )
        )
        return _to_departure(row) if row else None

    def offers(self, provider_id: str, external_ids: Sequence[str]) -> list[Offer]:
        if not external_ids:
            return []
        rows = self.db.execute(
            select(m.OfferRow, m.DepartureRow.external_id)
            .join(m.DepartureRow)
            .where(m.OfferRow.provider_id == provider_id, m.DepartureRow.external_id.in_(external_ids))
            .order_by(m.OfferRow.id)
        ).all()
        return [
            Offer(
                id=o.external_id,
                provider_id=o.provider_id,
                departure_id=dep_ext,
                fare_name=o.fare_name,
                price=o.price,
                currency=o.currency,
                retrieved_at=o.retrieved_at,
                source_updated_at=o.source_updated_at,
                is_estimate=o.is_estimate,
                price_max=o.price_max,
                booking_url=o.booking_url,
            )
            for o, dep_ext in rows
        ]

    def latest_import(self, provider_id: str) -> m.DataImport | None:
        return self.db.scalar(
            select(m.DataImport)
            .where(m.DataImport.provider_id == provider_id, m.DataImport.status == "succeeded")
            .order_by(m.DataImport.finished_at.desc())
            .limit(1)
        )


def _to_departure(r: m.DepartureRow) -> Departure:
    return Departure(
        id=r.external_id,
        provider_id=r.provider_id,
        service_code=r.service_code,
        operator_name=r.operator_name,
        mode=TransportMode(r.mode),
        origin_station_id=r.origin_station_id,
        destination_station_id=r.destination_station_id,
        schedule_type=ScheduleType(r.schedule_type),
        duration_minutes=r.duration_minutes,
        departure_utc=r.departure_utc,
        arrival_utc=r.arrival_utc,
        retrieved_at=r.retrieved_at,
        source_updated_at=r.source_updated_at,
    )
