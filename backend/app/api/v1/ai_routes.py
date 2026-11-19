"""POST /api/v1/ai/interpret — T-AI: natural-language request -> validated parameters -> real results,
plus what T-AI knows about the places mentioned (from the place-card pack, with sources)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator

from app.ai.knowledge import Lang, Place, PlaceKnowledge
from app.ai.service import AssistantService, clarification, explain, query_string
from app.api.deps import Principal, optional_principal
from app.api.v1.schemas import SearchResponse
from app.core.errors import AppError, ValidationFailed
from app.db.repositories import ActivityRepository
from app.db.session import transaction

router = APIRouter(prefix="/api/v1")


class InterpretRequest(BaseModel):
    text: str = Field(
        min_length=1, max_length=2000, examples=["Cheapest way from Tashkent to Samarkand tomorrow"]
    )

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Enter a request.")
        return v


class IntentOut(BaseModel):
    origin_id: str | None
    destination_id: str | None
    travel_date: date | None
    modes: list[str] = Field(description="Empty = all modes.")
    budget_preference: str
    max_price: Decimal | None
    time_preference: str
    sort: str
    depart_after: str | None
    depart_before: str | None
    arrive_before: str | None = None
    max_transfers: int = 1
    transfer_preference: str = "any"
    prefer_modes: list[str] = Field(default_factory=list, description="Ranking preference only.")
    compare_modes: bool = False


class PlaceSourceOut(BaseModel):
    label: str
    url: str


class PlaceOut(BaseModel):
    """A place from T-AI's knowledge, in the language of the request. Text is quoted, not generated."""

    key: str
    region: str
    region_name: str
    kind: str
    name: str
    area: str
    category: str
    history: str
    see: str
    tip: str
    sources: list[PlaceSourceOut]
    image: str = Field(description="An artistic illustration, not a photo.")
    explore_url: str
    city_id: str = Field(description="Nearest city T-Port finds journeys to.")
    city_name: str

    @classmethod
    def of(cls, p: Place, lang: Lang, knowledge: PlaceKnowledge) -> PlaceOut:
        t = p.text[lang]
        return cls(
            key=p.key,
            region=p.region,
            region_name=knowledge.region_name(p.region, lang),
            kind=p.kind,
            name=t.name,
            area=t.area,
            category=t.category,
            history=t.history,
            see=t.see,
            tip=t.tip,
            sources=[PlaceSourceOut(label=label, url=url) for label, url in p.sources],
            image=p.image,
            explore_url=p.explore_url,
            city_id=p.city_id,
            city_name=p.city_name,
        )


class InterpretResponse(BaseModel):
    assistant: str = "T-AI"
    language: str = Field(default="en", description="Language T-AI answered place questions in: en or uz.")
    engine: str = Field(description="'rules' (deterministic) or the LLM engine used.")
    fallback_used: bool
    intent: IntentOut
    needs_clarification: bool
    clarification: str | None
    search_query: str | None = Field(description="Query string for /search reproducing this request.")
    explanation: str | None = Field(description="Generated from returned data only.")
    results: SearchResponse | None
    answer: str | None = Field(default=None, description="T-AI's lead-in to the places below.")
    places: list[PlaceOut] = Field(default_factory=list)
    disclaimer: str = (
        "T-AI only interprets your request. Prices, times and operators come from the listed data "
        "sources; place information comes from the sources listed with each place."
    )


@router.post("/ai/interpret", response_model=InterpretResponse, tags=["ai"])
async def interpret(
    body: InterpretRequest,
    request: Request,
    principal: Annotated[Principal | None, Depends(optional_principal)],
) -> InterpretResponse:
    settings = request.app.state.settings
    if len(body.text) > settings.ai_max_input_chars:
        raise ValidationFailed(
            f"Please keep requests under {settings.ai_max_input_chars} characters.",
            details=[{"field": "text", "message": "Too long."}],
        )
    assistant: AssistantService = request.app.state.assistant
    today = assistant.search.today()
    result = await assistant.interpret(body.text, today)
    await _record(request, principal, result, len(body.text))
    _record_metrics(request, result)

    intent = result.intent
    modes = sorted(m.value for m in intent.modes)
    intent_out = IntentOut(
        origin_id=intent.origin_id,
        destination_id=intent.destination_id,
        travel_date=intent.travel_date,
        modes=modes,
        budget_preference=intent.budget_preference,
        max_price=intent.max_price,
        time_preference=intent.time_preference,
        sort=intent.sort.value,
        depart_after=intent.depart_after.strftime("%H:%M") if intent.depart_after else None,
        depart_before=intent.depart_before.strftime("%H:%M") if intent.depart_before else None,
        arrive_before=intent.arrive_before.strftime("%H:%M") if intent.arrive_before else None,
        max_transfers=intent.max_transfers,
        transfer_preference=intent.transfer_preference,
        prefer_modes=sorted(m.value for m in intent.prefer_modes),
        compare_modes=intent.compare_modes,
    )
    knowledge = PlaceKnowledge.load()
    catalog = request.app.state.catalog
    lang = knowledge.language(body.text)
    mentioned = knowledge.find(body.text, catalog)
    common = dict(
        language=lang,
        engine=result.engine,
        fallback_used=result.outcome in ("fallback", "provider_error", "invalid_output"),
        intent=intent_out,
    )
    if not intent.complete:
        asks = knowledge.asks_about_places(body.text) or knowledge.names_place(body.text)
        if mentioned and asks:
            # A question about places (or just a place's name): answer from the knowledge base. A
            # specific problem with the trip (e.g. a foreign-currency budget) is still explained;
            # otherwise T-AI offers to plan the trip.
            issue = intent.unsupported_reason or intent.problems
            return InterpretResponse(
                **common,
                needs_clarification=True,
                clarification=clarification(intent) if issue else knowledge.follow_up(lang),
                search_query=None,
                explanation=None,
                results=None,
                answer=knowledge.intro(mentioned, lang),
                places=[PlaceOut.of(p, lang, knowledge) for p in mentioned],
            )
        return InterpretResponse(
            **common,
            needs_clarification=True,
            clarification=clarification(intent),
            search_query=None,
            explanation=None,
            results=None,
        )

    # A trip: also share what T-AI knows about the destination's region.
    region = knowledge.region_of_location(intent.destination_id, catalog)
    trip_places = knowledge.in_region(region) if region else []
    extras = dict(
        answer=knowledge.intro(trip_places, lang, for_trip=True) if trip_places else None,
        places=[PlaceOut.of(p, lang, knowledge) for p in trip_places],
    )

    try:
        search_result = await assistant.run_search(intent)
    except AppError as exc:  # e.g. providers unavailable: say so plainly
        return InterpretResponse(
            **common,
            needs_clarification=False,
            clarification=None,
            search_query=None,
            explanation=exc.message,
            results=None,
            **extras,
        )
    return InterpretResponse(
        **common,
        needs_clarification=False,
        clarification=None,
        search_query=query_string(intent),
        explanation=explain(intent, search_result),
        results=SearchResponse.of(search_result),
        **extras,
    )


def _record_metrics(request: Request, result) -> None:
    """Counters only (engine, outcome, tokens, latency); never the request text."""
    metrics = getattr(request.app.state, "metrics", None)
    if metrics is None:
        return
    metrics.inc("tport_ai_requests_total", engine=result.engine, outcome=result.outcome)
    metrics.inc("tport_ai_latency_seconds_sum", result.latency_ms / 1000, engine=result.engine)
    metrics.inc("tport_ai_latency_seconds_count", engine=result.engine)
    if result.error_code:
        metrics.inc("tport_ai_errors_total", code=result.error_code)
    if not result.intent.complete:
        metrics.inc("tport_ai_clarifications_total")
    for direction, tokens in (("input", result.input_tokens), ("output", result.output_tokens)):
        if tokens:
            metrics.inc("tport_ai_tokens_total", tokens, direction=direction, model=result.model or "")
    # Cost is only reported when the operator configures their contracted per-token prices.
    settings = request.app.state.settings
    in_price, out_price = settings.ai_input_usd_per_mtok, settings.ai_output_usd_per_mtok
    if in_price is not None and out_price is not None and (result.input_tokens or result.output_tokens):
        cost = ((result.input_tokens or 0) * in_price + (result.output_tokens or 0) * out_price) / 1_000_000
        metrics.inc("tport_ai_estimated_cost_usd_total", float(cost), model=result.model or "")


async def _record(request: Request, principal: Principal | None, result, input_chars: int) -> None:
    """AI request metadata (no prompt text). Failures never break the response."""

    def write() -> None:
        with transaction(request.app.state.session_factory) as db:
            ActivityRepository(db).record_ai_request(
                user_id=principal.user.id if principal else None,
                engine=result.engine,
                model=result.model,
                outcome=result.outcome,
                input_chars=input_chars,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                error_code=result.error_code,
                created_at=request.app.state.clock.now(),
            )

    try:
        await run_in_threadpool(write)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("tport.ai").warning("could not record AI request metadata")
