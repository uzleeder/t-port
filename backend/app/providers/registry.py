"""Provider registry: every data source T-Port may use, declared as a ProviderContract.

A provider can be enabled only when ``contract_problems`` returns nothing: real sources
need a named, verified, unexpired authorization that permits showing prices, plus a
documented data mapping. No live provider is registered because T-Port has no confirmed
data agreements yet (see docs/provider-integration-status.md). New REST sources start from
``app/providers/template``; its contract is intentionally rejected by the gate.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.domain.models import TransportMode
from app.providers.contracts import (
    Authorization,
    Capabilities,
    IngestionPolicy,
    ProviderContract,
    contract_problems,
)
from app.providers.demo.adapter import DEMO_PROVIDER

DEMO_CONTRACT = ProviderContract(
    info=DEMO_PROVIDER,
    authorization=Authorization(
        basis="internal_synthetic",
        reference="internal: backend/app/providers/demo/dataset.py",
        attribution=DEMO_PROVIDER.attribution,
        permits_price_display=True,
        permits_booking_redirects=False,
    ),
    capabilities=Capabilities(
        modes=frozenset(TransportMode), live_prices=False, seat_availability=False, on_demand=True
    ),
    ingestion=IngestionPolicy(mode="live", max_concurrency=8, update_interval_minutes=10),
    stale_after=timedelta(minutes=15),
    expire_after=timedelta(hours=6),
    data_mapping="Uses T-Port station IDs directly; times generated in Asia/Tashkent; UZS.",
    reliability_notes="Synthetic. Must never be presented as real travel information.",
    update_frequency="Generated on request (live mode) or per import run (stored mode).",
)

CONTRACTS: tuple[ProviderContract, ...] = (DEMO_CONTRACT,)


def adapter_factories(catalog, clock) -> dict:
    """Provider id -> zero-argument adapter constructor (used by imports, checks and the scheduler)."""
    from app.providers.demo.adapter import DemoAdapter

    return {"demo": lambda: DemoAdapter(catalog, clock)}


def contract_for(provider_id: str) -> ProviderContract | None:
    return next((c for c in CONTRACTS if c.info.id == provider_id), None)


def enabled_contracts(today: date) -> list[ProviderContract]:
    return [c for c in CONTRACTS if not contract_problems(c, today)]
