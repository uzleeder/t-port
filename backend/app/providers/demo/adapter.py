"""Demo provider adapter backed by the fictional timetable in ``dataset.py``."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from app.core.clock import Clock, SystemClock
from app.domain.models import Departure, Offer, ProviderInfo, TransportMode
from app.providers.base import ProviderAdapter, RateLimitPolicy
from app.providers.demo import dataset as ds
from app.services.catalog import LocationCatalog

DEMO_PROVIDER = ProviderInfo(
    id="demo",
    name="T-Port Demo Dataset",
    is_demo=True,
    attribution=(
        "Simulated timetable for demonstration only. Not real schedules, fares, availability or operators."
    ),
    booking_hosts=frozenset(),  # demo data is never bookable
)

_DEPARTURE_ID = re.compile(r"^(?P<code>[A-Z]{2}\d{3})\.(?P<date>\d{8})$")
_TZ = ZoneInfo("Asia/Tashkent")  # all demo services are domestic Uzbekistan


class DemoAdapter(ProviderAdapter):
    info = DEMO_PROVIDER
    rate_limit = RateLimitPolicy(requests_per_minute=None, timeout_seconds=1.0)

    def __init__(self, catalog: LocationCatalog, clock: Clock | None = None) -> None:
        self._catalog = catalog
        self._clock = clock or SystemClock()
        locs: set[str] = set()
        for tpl in ds.TEMPLATES:
            for sid in (tpl.origin_station, tpl.destination_station):
                station = catalog.station(sid)
                if station is None:
                    raise ValueError(f"Demo template {tpl.code} uses unknown station {sid}")
                locs.add(station.location_id)
        self._locations = frozenset(locs)

    def supported_location_ids(self) -> frozenset[str]:
        return self._locations

    # -- departures --------------------------------------------------------------
    def _location_of(self, station_id: str) -> str:
        station = self._catalog.station(station_id)
        assert station is not None  # validated in __init__
        return station.location_id

    def _build_departure(self, tpl: ds.ServiceTemplate, travel_date: date) -> Departure:
        dep_utc = arr_utc = None
        if tpl.depart_local is not None:
            local = datetime.combine(travel_date, time.fromisoformat(tpl.depart_local), _TZ)
            dep_utc = local.astimezone(UTC)
            arr_utc = dep_utc + timedelta(minutes=tpl.duration_minutes)
        return Departure(
            id=f"{tpl.code}.{travel_date:%Y%m%d}",
            provider_id=self.id,
            service_code=tpl.code,
            operator_name=tpl.operator,
            mode=tpl.mode,
            origin_station_id=tpl.origin_station,
            destination_station_id=tpl.destination_station,
            schedule_type=tpl.schedule_type,
            duration_minutes=tpl.duration_minutes,
            departure_utc=dep_utc,
            arrival_utc=arr_utc,
            retrieved_at=self._clock.now(),
            source_updated_at=ds.DATASET_UPDATED_AT,
        )

    async def get_departures(
        self,
        origin_location_id: str,
        destination_location_id: str,
        travel_date: date,
        modes: frozenset[TransportMode],
    ) -> Sequence[Departure]:
        out = []
        for tpl in ds.TEMPLATES:
            if modes and tpl.mode not in modes:
                continue
            if travel_date.weekday() not in tpl.days:
                continue
            if (
                self._location_of(tpl.origin_station) == origin_location_id
                and self._location_of(tpl.destination_station) == destination_location_id
            ):
                out.append(self._build_departure(tpl, travel_date))
        return out

    async def get_departure(self, departure_id: str) -> Departure | None:
        match = _DEPARTURE_ID.match(departure_id)
        if not match:
            return None
        tpl = ds.TEMPLATES_BY_CODE.get(match["code"])
        if tpl is None:
            return None
        try:
            travel_date = datetime.strptime(match["date"], "%Y%m%d").date()
        except ValueError:
            return None
        if travel_date.weekday() not in tpl.days:
            return None
        return self._build_departure(tpl, travel_date)

    # -- offers ---------------------------------------------------------------------
    async def get_offers(self, departure_ids: Sequence[str]) -> Sequence[Offer]:
        now = self._clock.now()
        offers: list[Offer] = []
        for dep_id in departure_ids:
            match = _DEPARTURE_ID.match(dep_id)
            tpl = ds.TEMPLATES_BY_CODE.get(match["code"]) if match else None
            if tpl is None or match is None:
                continue
            travel_date = datetime.strptime(match["date"], "%Y%m%d").date()
            surcharge = (
                ds.WEEKEND_MULTIPLIER
                if travel_date.weekday() in ds.WEEKEND and tpl.mode != TransportMode.TAXI
                else Decimal(1)
            )
            for fare in tpl.fares:
                price = _round_uzs(tpl.base_price * fare.multiplier * surcharge)
                offers.append(
                    Offer(
                        id=f"{dep_id}.{fare.name.split()[0].lower()}",
                        provider_id=self.id,
                        departure_id=dep_id,
                        fare_name=fare.name,
                        price=price,
                        currency=ds.CURRENCY,
                        retrieved_at=now,
                        source_updated_at=ds.DATASET_UPDATED_AT,
                        is_estimate=tpl.price_max is not None,
                        price_max=_round_uzs(tpl.price_max) if tpl.price_max else None,
                        booking_url=None,
                    )
                )
        return offers


def _round_uzs(value: Decimal) -> Decimal:
    """Round to the nearest 1,000 UZS (demo pricing granularity)."""
    return (value / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 1000
