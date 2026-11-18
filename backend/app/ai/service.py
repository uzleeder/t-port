"""Journey assistant: interpret -> validate -> deterministic search -> grounded explanation.

The explanation is assembled from the search results by template, so every
number or name in it comes from provider data, never from a language model.
"""

from __future__ import annotations

import logging
import time as _time
from dataclasses import dataclass
from datetime import date

from app.ai import rules
from app.ai.intent import RawIntent, ValidatedIntent, validate_intent
from app.ai.llm import AnthropicInterpreter, InterpreterError
from app.domain.models import Freshness, Journey, PriceType, TransportMode
from app.services.catalog import LocationCatalog
from app.services.search import SearchQuery, SearchResult, SearchService

log = logging.getLogger("tport.ai")


@dataclass(slots=True)
class InterpretOutcome:
    raw: RawIntent
    intent: ValidatedIntent
    engine: str
    model: str | None
    outcome: str  # ok | fallback | invalid_output | provider_error | rejected
    error_code: str | None
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class AssistantService:
    def __init__(
        self,
        catalog: LocationCatalog,
        search: SearchService,
        *,
        llm: AnthropicInterpreter | None,
        max_days_ahead: int,
    ) -> None:
        self.catalog = catalog
        self.search = search
        self.llm = llm
        self.max_days_ahead = max_days_ahead

    async def interpret(self, text: str, today: date) -> InterpretOutcome:
        started = _time.perf_counter()
        engine, model, outcome, error = "rules", None, "ok", None
        tokens: tuple[int | None, int | None] = (None, None)
        raw: RawIntent | None = None
        if self.llm is not None:
            try:
                result = await self.llm.interpret(text, today, self.catalog.search(None))
                raw, engine, model = result.intent, self.llm.engine, result.model
                tokens = (result.input_tokens, result.output_tokens)
            except InterpreterError as exc:
                error = exc.code
                outcome = "invalid_output" if exc.code == "invalid_output" else "provider_error"
                log.warning("LLM interpreter failed (%s); using rules", exc.code)
        if raw is None:
            raw = rules.parse(text, self.catalog, today)
            if self.llm is not None:
                engine = "rules"
        intent = validate_intent(raw, self.catalog, today, self.max_days_ahead)
        if self.llm is not None and engine == "rules" and outcome == "ok":
            outcome = "fallback"
        return InterpretOutcome(
            raw=raw,
            intent=intent,
            engine=engine,
            model=model,
            outcome="rejected" if intent.unsupported_reason else outcome,
            error_code=error,
            latency_ms=int((_time.perf_counter() - started) * 1000),
            input_tokens=tokens[0],
            output_tokens=tokens[1],
        )

    async def run_search(self, intent: ValidatedIntent) -> SearchResult:
        assert intent.origin_id and intent.destination_id and intent.travel_date
        return await self.search.search(search_query_for(intent))


def search_query_for(intent: ValidatedIntent, page_size: int | None = None) -> SearchQuery:
    """The deterministic search an interpreted request maps to (also exposed as a query string)."""
    assert intent.origin_id and intent.destination_id and intent.travel_date
    return SearchQuery(
        origin_id=intent.origin_id,
        destination_id=intent.destination_id,
        travel_date=intent.travel_date,
        modes=intent.modes,
        sort=intent.sort,
        max_price=intent.max_price,
        depart_after=intent.depart_after,
        depart_before=intent.depart_before,
        arrive_before=intent.arrive_before,
        max_transfers=intent.max_transfers,
        prefer_modes=intent.prefer_modes,
        # Comparing modes needs more than the top five to find each mode's best option.
        page_size=page_size or (50 if intent.compare_modes else 5),
    )


def query_string(intent: ValidatedIntent) -> str:
    """Parameters for /search reproducing this request (no free text, only validated values)."""
    assert intent.origin_id and intent.destination_id and intent.travel_date
    qs = [
        f"origin={intent.origin_id}",
        f"destination={intent.destination_id}",
        f"date={intent.travel_date.isoformat()}",
    ]
    if intent.modes:
        qs.append(f"modes={','.join(sorted(m.value for m in intent.modes))}")
    if intent.sort.value != "recommended":
        qs.append(f"sort={intent.sort.value}")
    if intent.max_price is not None:
        qs.append(f"max_price={intent.max_price:f}")
    if intent.depart_after:
        qs.append(f"depart_after={intent.depart_after:%H:%M}")
    if intent.depart_before:
        qs.append(f"depart_before={intent.depart_before:%H:%M}")
    if intent.arrive_before:
        qs.append(f"arrive_before={intent.arrive_before:%H:%M}")
    if intent.max_transfers != 1:
        qs.append(f"max_transfers={intent.max_transfers}")
    if intent.prefer_modes:
        qs.append(f"prefer_modes={','.join(sorted(m.value for m in intent.prefer_modes))}")
    return "&".join(qs).replace(":", "%3A")


def clarification(intent: ValidatedIntent) -> str | None:
    if intent.unsupported_reason:
        return intent.unsupported_reason
    if intent.problems:
        return " ".join(intent.problems)
    if intent.missing == ["origin", "destination"]:
        return "Where are you travelling from, and where to? For example: “Tashkent to Bukhara on Friday”."
    if "origin" in intent.missing:
        return "Where will you be starting from?"
    if "destination" in intent.missing:
        return "Where would you like to go?"
    return None


_BASIS = {
    "price": "the lowest fare",
    "duration": "the shortest travel time",
    "departure": "the earliest departure",
    "transfers": "the fewest changes",
    "recommended": "the best balance of price, time and changes",
}
_PRICE_TYPE = {
    PriceType.CONFIRMED: "a live fare from the source",
    PriceType.INDICATIVE: "an indicative fare; confirm it with the operator before travelling",
    PriceType.ESTIMATED: "an estimate, not a fixed fare",
    PriceType.DEMO: "demonstration data, not a real fare",
}


def _money(j: Journey) -> str:
    if j.price_max and j.is_price_estimate:
        return f"{j.price:,.0f}–{j.price_max:,.0f} {j.currency}"
    return f"{j.price:,.0f} {j.currency}"


def _duration(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def _local(dt, tz_name: str) -> str:
    return dt.astimezone(_tz(tz_name)).strftime("%H:%M")


def _describe(j: Journey, result: SearchResult) -> str:
    first = j.legs[0].departure
    modes = " + ".join(m.value for m in j.modes)
    operators = ", ".join(dict.fromkeys(leg.departure.operator_name for leg in j.legs))
    when = (
        f"departing {_local(first.departure_utc, result.origin.timezone)}"
        if first.departure_utc
        else "with a flexible departure time"
    )
    if j.arrival_utc:
        when += f", arriving {_local(j.arrival_utc, result.destination.timezone)}"
    changes = "direct"
    if j.transfers:
        hubs = [leg.destination.name for leg in j.legs[:-1]]
        changes = f"{j.transfers} change{'s' if j.transfers > 1 else ''} ({', '.join(hubs)})"
    taking = _duration(j.total_minutes)
    return f"the {modes} by {operators}, {when}, {changes}, taking {taking}, from {_money(j)}"


def explain(intent: ValidatedIntent, result: SearchResult) -> str:
    """Plain-language summary built only from the returned search data.

    Every name, time and price below is read from ``result``; nothing comes from a language model,
    and no provider text is ever sent to one, so text inside provider data cannot steer it.
    """
    route = f"{result.origin.name} to {result.destination.name} on {result.query.travel_date:%A %d %B}"
    q = result.query
    if result.total == 0:
        reasons = []
        if result.excluded.over_budget:
            reasons.append(f"{result.excluded.over_budget} option(s) were over your budget")
        if result.excluded.outside_time_window:
            window = "your arrival or departure time" if q.arrive_before else "your preferred time"
            reasons.append(f"{result.excluded.outside_time_window} did not fit {window}")
        if result.excluded.already_departed:
            reasons.append(f"{result.excluded.already_departed} had already left")
        if result.excluded.expired_data:
            reasons.append(f"{result.excluded.expired_data} were hidden because their data is out of date")
        failed = [s.provider.name for s in result.sources if not s.ok]
        if failed:
            reasons.append(f"{', '.join(failed)} could not be reached")
        why = f" ({'; '.join(reasons)})" if reasons else ""
        hint = "Try a different date, more transport modes, or a wider time window."
        if q.max_transfers == 0:
            hint = "Try allowing a change, a different date, or more transport modes."
        return (
            f"I couldn't find a matching journey from {route} in the data T-Port currently has{why}. " + hint
        )

    best = result.journeys[0]
    parts = [
        f"I found {result.total} option(s) from {route}.",
        f"Sorted by {_BASIS[q.sort.value]}, the top result is {_describe(best, result)}.",
        f"That price is {_PRICE_TYPE[best.price_type]}.",
    ]
    if best.freshness in (Freshness.STALE, Freshness.UNKNOWN):
        parts.append("Its data has not been refreshed recently, so check the schedule before you travel.")
    sources = sorted({leg.provider.name for leg in best.legs if leg.provider})
    if sources:
        parts.append(f"Source: {', '.join(sources)}.")

    applied = []
    if q.arrive_before:
        applied.append(f"arriving by {q.arrive_before:%H:%M}")
    if q.depart_after or q.depart_before:
        lo = f"{q.depart_after:%H:%M}" if q.depart_after else "any time"
        hi = f"{q.depart_before:%H:%M}" if q.depart_before else "midnight"
        applied.append(f"departing between {lo} and {hi}")
    if q.max_price is not None:
        applied.append(f"up to {q.max_price:,.0f} UZS")
    if q.max_transfers == 0:
        applied.append("direct journeys only")
    if q.prefer_modes:
        applied.append(f"preferring {' or '.join(sorted(m.value for m in q.prefer_modes))}")
    if applied:
        parts.append(f"Applied: {'; '.join(applied)}.")

    if intent.compare_modes:
        per_mode: dict[TransportMode, Journey] = {}
        for j in result.journeys:  # already ranked: first seen is best for its mode
            if len(j.modes) == 1:
                per_mode.setdefault(j.modes[0], j)
        if len(per_mode) >= 2:
            lines = [
                f"{mode.value} {_money(j)}, {_duration(j.total_minutes)}"
                for mode, j in sorted(per_mode.items(), key=lambda kv: kv[0].value)
            ]
            parts.append(f"Best option by mode: {'; '.join(lines)}.")
        else:
            parts.append("Only one transport mode has matching journeys, so there is nothing to compare.")
    if best.is_demo:
        parts.append("These results come from demonstration data, not real schedules.")
    return " ".join(parts)


def _tz(name: str):
    from zoneinfo import ZoneInfo

    return ZoneInfo(name)
