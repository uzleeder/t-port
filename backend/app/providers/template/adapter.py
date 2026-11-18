"""REST adapter template: provider API -> T-Port Departure/Offer objects.

Endpoints assumed by the template (replace with the provider's documented ones):

* ``GET {base_url}/v1/trips?from=<stop>&to=<stop>&date=YYYY-MM-DD`` -> ``ApiTripList``
* ``GET {base_url}/v1/trips/{trip_id}`` -> ``ApiTripDetail``
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from urllib.parse import quote, urlencode, urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from app.core.clock import Clock, SystemClock
from app.core.outbound import OutboundBlocked, check_outbound_url, guarded_client
from app.domain.models import Departure, Offer, ProviderInfo, ScheduleType, TransportMode
from app.providers.base import ProviderAdapter, ProviderError, ProviderRateLimited, RateLimitPolicy
from app.providers.template.schemas import ApiTrip, ApiTripDetail, ApiTripList
from app.services.catalog import LocationCatalog

_FARE_CACHE_SIZE = 2_000
_TRIP_ID = re.compile(r"[A-Za-z0-9._-]{1,40}")


class StopMapping:
    """Provider stop code <-> T-Port station ID, from the documented data mapping.

    Unknown codes are an error, never a guess: a wrong station would put a real service in the
    wrong city.
    """

    def __init__(self, provider_to_station: Mapping[str, str], catalog: LocationCatalog) -> None:
        bad = [code for code, sid in provider_to_station.items() if catalog.station(sid) is None]
        if bad:
            raise ValueError(f"stop codes mapped to unknown T-Port stations: {sorted(bad)}")
        self._to_station = dict(provider_to_station)
        self._catalog = catalog

    def station(self, stop_code: str) -> str | None:
        return self._to_station.get(stop_code)

    def stops_for_location(self, location_id: str) -> list[str]:
        return sorted(
            code
            for code, sid in self._to_station.items()
            if (st := self._catalog.station(sid)) is not None and st.location_id == location_id
        )

    def location_ids(self) -> frozenset[str]:
        return frozenset(self._catalog.station(sid).location_id for sid in self._to_station.values())


class RestTemplateAdapter(ProviderAdapter):
    def __init__(
        self,
        info: ProviderInfo,
        *,
        base_url: str,
        stops: StopMapping,
        clock: Clock | None = None,
        rate_limit: RateLimitPolicy | None = None,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        resolve_dns: bool = True,
    ) -> None:
        self.info = info
        self.rate_limit = rate_limit or RateLimitPolicy(timeout_seconds=10.0)
        self._base = base_url.rstrip("/")
        self._host = (urlsplit(self._base).hostname or "").lower()
        self._hosts = frozenset({self._host})
        check_outbound_url(self._base, self._hosts, resolve=False)  # fail fast on a bad config
        self._stops = stops
        self._clock = clock or SystemClock()
        self._api_key = api_key
        # Tests inject a client with httpx.MockTransport; URLs are still checked per request.
        self._client = client or guarded_client(
            self._hosts, self.rate_limit.timeout_seconds, resolve=resolve_dns
        )
        self._fares: OrderedDict[str, tuple[list[Offer], datetime]] = OrderedDict()

    # -- interface ---------------------------------------------------------------------------

    def supported_location_ids(self) -> frozenset[str]:
        return self._stops.location_ids()

    async def get_departures(
        self,
        origin_location_id: str,
        destination_location_id: str,
        travel_date: date,
        modes: frozenset[TransportMode],
    ) -> Sequence[Departure]:
        out: list[Departure] = []
        for o in self._stops.stops_for_location(origin_location_id):
            for d in self._stops.stops_for_location(destination_location_id):
                query = urlencode({"from": o, "to": d, "date": travel_date.isoformat()})
                body = await self._get(f"{self._base}/v1/trips?{query}", ApiTripList)
                retrieved = self._clock.now()
                for trip in body.trips:
                    dep = self._departure(trip, body.generated_at, retrieved)
                    if modes and dep.mode not in modes:
                        continue
                    out.append(dep)
                    self._remember(trip, body.generated_at, retrieved)
        return out

    async def get_departure(self, departure_id: str) -> Departure | None:
        detail = await self._trip(departure_id)
        if detail is None:
            return None
        retrieved = self._clock.now()
        self._remember(detail.trip, detail.generated_at, retrieved)
        return self._departure(detail.trip, detail.generated_at, retrieved)

    async def get_offers(self, departure_ids: Sequence[str]) -> Sequence[Offer]:
        offers: list[Offer] = []
        for dep_id in departure_ids:
            cached = self._fares.get(dep_id)
            if cached is None:
                detail = await self._trip(dep_id)
                if detail is None:
                    continue
                self._remember(detail.trip, detail.generated_at, self._clock.now())
                cached = self._fares[dep_id]
            offers += cached[0]
        return offers

    # -- mapping -----------------------------------------------------------------------------

    def _departure(self, t: ApiTrip, generated_at: datetime, retrieved: datetime) -> Departure:
        origin, destination = self._stops.station(t.from_stop), self._stops.station(t.to_stop)
        if origin is None or destination is None:
            raise ProviderError(self.id, f"trip {t.trip_id}: stop code not in the documented mapping")
        dep, arr = t.departs_at.astimezone(UTC), t.arrives_at.astimezone(UTC)
        return Departure(
            id=t.trip_id,
            provider_id=self.id,
            service_code=t.trip_id,
            operator_name=t.operator,
            mode=TransportMode(t.mode),
            origin_station_id=origin,
            destination_station_id=destination,
            schedule_type=ScheduleType.SCHEDULED,
            duration_minutes=int((arr - dep).total_seconds() // 60),
            departure_utc=dep,
            arrival_utc=arr,
            retrieved_at=retrieved,
            source_updated_at=generated_at,
        )

    def _remember(self, t: ApiTrip, generated_at: datetime, retrieved: datetime) -> None:
        offers = [
            Offer(
                id=f"{t.trip_id}.{f.fare_id}",
                provider_id=self.id,
                departure_id=t.trip_id,
                fare_name=f.name,
                price=f.amount,
                currency=f.currency,
                retrieved_at=retrieved,
                source_updated_at=f.updated_at or generated_at,
                booking_url=f.booking_url,  # validated against booking_hosts by the search engine
            )
            for f in t.fares
        ]
        self._fares[t.trip_id] = (offers, retrieved)
        self._fares.move_to_end(t.trip_id)
        while len(self._fares) > _FARE_CACHE_SIZE:
            self._fares.popitem(last=False)

    # -- HTTP --------------------------------------------------------------------------------

    async def _trip(self, trip_id: str) -> ApiTripDetail | None:
        if not _TRIP_ID.fullmatch(trip_id):
            return None
        try:
            return await self._get(f"{self._base}/v1/trips/{quote(trip_id, safe='')}", ApiTripDetail)
        except _NotFound:
            return None

    async def _get[M: BaseModel](self, url: str, model: type[M]) -> M:
        try:
            check_outbound_url(url, self._hosts, resolve=False)
            headers = {"Accept": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            response = await self._client.get(url, headers=headers)
        except OutboundBlocked as exc:
            raise ProviderError(self.id, f"blocked outbound request: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(self.id, "timeout", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(self.id, f"connection error: {type(exc).__name__}", retryable=True) from exc
        if response.status_code == 404:
            raise _NotFound
        if response.status_code == 429:
            raise ProviderRateLimited(self.id, _retry_after(response.headers.get("Retry-After")))
        if response.status_code >= 500:
            raise ProviderError(self.id, f"HTTP {response.status_code}", retryable=True)
        if response.status_code != 200:
            raise ProviderError(self.id, f"HTTP {response.status_code}")
        try:
            return model.model_validate_json(response.content)
        except ValidationError as exc:
            # Never pass on partially understood data.
            raise ProviderError(self.id, f"invalid response: {exc.error_count()} schema error(s)") from exc

    async def aclose(self) -> None:
        await self._client.aclose()


class _NotFound(Exception):
    pass


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
