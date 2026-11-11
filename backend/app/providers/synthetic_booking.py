"""TEST-ONLY bookable provider for development and end-to-end tests of the booking hand-off.

Enabled only with ``TPORT_ENABLE_SYNTHETIC_BOOKING=true``; the settings validator refuses it in
production. Its operator is fictional and named "TEST", its booking host is on the reserved
``.test`` domain (it can never resolve on the internet; e2e tests intercept it), and its contract
reference says plainly that no agreement exists. It exists so the booking flow (fresh-price check,
host allow-list, interstitial, redirect, aggregate count) can be exercised without a real partner.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.domain.models import ProviderInfo, TransportMode
from app.providers.contracts import (
    Authorization,
    Capabilities,
    IngestionPolicy,
    Onboarding,
    ProviderContract,
)

BOOKING_HOST = "booking.synthrail.test"

SYNTHETIC_BOOKING_INFO = ProviderInfo(
    id="synthbook",
    name="SynthRail TEST (fictional, dev only)",
    is_demo=False,
    attribution="Fictional test operator for development. Not real travel information.",
    booking_hosts=frozenset({BOOKING_HOST}),
)

SYNTHETIC_BOOKING_CONTRACT = ProviderContract(
    info=SYNTHETIC_BOOKING_INFO,
    authorization=Authorization(
        basis="written_agreement",
        reference="TEST-ONLY: no real agreement exists; development and e2e environments only",
        attribution=SYNTHETIC_BOOKING_INFO.attribution,
        permits_price_display=True,
        permits_booking_redirects=True,
        verified_by="T-Port engineering (test fixture)",
        verified_on=date(2026, 11, 11),
    ),
    capabilities=Capabilities(
        modes=frozenset({TransportMode.TRAIN}),
        live_prices=False,
        seat_availability=False,
        operations=frozenset({"locations", "schedules", "offers", "booking_links"}),
    ),
    ingestion=IngestionPolicy(mode="live", max_concurrency=1),
    stale_after=timedelta(hours=24),
    expire_after=timedelta(hours=48),
    data_mapping="Feed uses T-Port station IDs; times local to Asia/Tashkent; UZS.",
    onboarding=Onboarding(
        official_identity="Fictional test operator (no legal entity)",
        access_method="provider_export",
        allowed_usage="Development and automated tests only",
        redistribution_restrictions="Not applicable (synthetic)",
        commercial_use_restrictions="Must never run in production",
        rate_limit_terms="Not applicable (in-process)",
        refresh_expectations="Loaded at start-up",
        contact_escalation="Engineering team",
        technical_docs="backend/app/providers/synthetic_booking.py",
        test_environment="in-process",
    ),
)

_EVERY_DAY = list(range(7))
SYNTHETIC_BOOKING_FEED = {
    "feed_version": "synthbook-dev-1",
    "generated_at": "2026-11-01T00:00:00Z",
    "timezone": "Asia/Tashkent",
    "currency": "UZS",
    "booking_url_template": f"https://{BOOKING_HOST}/book?service={{service}}&date={{date}}",
    "services": [
        {
            "code": "SBK101",
            "mode": "train",
            "operator": "SynthRail TEST",
            "from": "tashkent-rail",
            "to": "samarkand-rail",
            "depart": "09:40",
            "minutes": 140,
            "days": _EVERY_DAY,
            "fares": [{"name": "Economy", "price": "240000.00"}],
        },
        {
            "code": "SBK102",
            "mode": "train",
            "operator": "SynthRail TEST",
            "from": "samarkand-rail",
            "to": "tashkent-rail",
            "depart": "17:20",
            "minutes": 140,
            "days": _EVERY_DAY,
            "fares": [{"name": "Economy", "price": "240000.00"}],
        },
    ],
}
