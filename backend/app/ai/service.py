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
        return await self.search.search(
            SearchQuery(
                origin_id=intent.origin_id,
                destination_id=intent.destination_id,
                travel_date=intent.travel_date,
                modes=intent.modes,
                sort=intent.sort,
                max_price=intent.max_price,
                depart_after=intent.depart_after,
                depart_before=intent.depart_before,
                page_size=5,
            )
        )


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


def explain(intent: ValidatedIntent, result: SearchResult) -> str:
    """Plain-language summary built only from the returned search data."""
    route = f"{result.origin.name} to {result.destination.name} on {result.query.travel_date:%A %d %B}"
    if result.total == 0:
        reasons = []
        if result.excluded.over_budget:
            reasons.append(f"{result.excluded.over_budget} option(s) were over your budget")
        if result.excluded.outside_time_window:
            reasons.append(f"{result.excluded.outside_time_window} departed outside your preferred time")
        if result.excluded.already_departed:
            reasons.append(f"{result.excluded.already_departed} had already left")
        why = f" ({'; '.join(reasons)})" if reasons else ""
        return (
            f"I couldn't find a matching journey from {route} in the data T-Port currently has{why}. "
            "Try a different date, more transport modes, or a wider time window."
        )
    best = result.journeys[0]
    leg = best.legs[0].departure
    when = (
        f"departing {leg.departure_utc.astimezone(_tz(result.origin.timezone)):%H:%M}"
        if leg.departure_utc
        else "with a flexible departure time"
    )
    price = f"{best.price:,.0f} {best.currency}" + (
        f"–{best.price_max:,.0f}" if best.price_max and best.is_price_estimate else ""
    )
    basis = {
        "price": "the lowest fare",
        "duration": "the shortest travel time",
        "departure": "the earliest departure",
        "recommended": "the best balance of price and time",
    }[result.query.sort.value]
    parts = [
        f"I found {result.total} option(s) from {route}.",
        f"Sorted by {basis}, the top result is the {leg.mode.value} by {leg.operator_name}, {when}, "
        f"taking {best.total_minutes // 60}h {best.total_minutes % 60:02d}m, from {price}.",
    ]
    if best.is_price_estimate:
        parts.append("That price is an estimate range, not a fixed fare.")
    if best.is_demo:
        parts.append("These results come from demonstration data, not real schedules.")
    return " ".join(parts)


def _tz(name: str):
    from zoneinfo import ZoneInfo

    return ZoneInfo(name)
