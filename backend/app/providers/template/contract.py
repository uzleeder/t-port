"""Contract skeleton for a REST provider. Deliberately NOT enableable.

Every field marked TODO must be filled from the signed agreement and the provider's technical
documentation. Until then ``contract_problems(TEMPLATE_CONTRACT, today)`` lists what is missing,
and the registry would refuse it. Never add this object to ``registry.CONTRACTS`` as-is.
"""

from __future__ import annotations

from datetime import timedelta

from app.domain.models import ProviderInfo, TransportMode
from app.providers.contracts import (
    Authorization,
    Capabilities,
    IngestionPolicy,
    Onboarding,
    ProviderContract,
)

TEMPLATE_INFO = ProviderInfo(
    id="template",
    name="TODO provider name",
    is_demo=False,
    attribution="TODO: wording the provider requires next to its data",
    booking_hosts=frozenset(),  # TODO: exact hosts from the agreement, if redirects are permitted
)

TEMPLATE_CONTRACT = ProviderContract(
    info=TEMPLATE_INFO,
    authorization=Authorization(
        basis="written_agreement",
        reference="",  # TODO: agreement number
        attribution=TEMPLATE_INFO.attribution,
        permits_price_display=False,  # TODO: only True if the agreement says so
        permits_booking_redirects=False,
        verified_by=None,  # TODO: person who checked the paperwork
        verified_on=None,
        expires_on=None,
    ),
    capabilities=Capabilities(
        modes=frozenset({TransportMode.BUS}),  # TODO
        live_prices=False,
        seat_availability=False,
    ),
    ingestion=IngestionPolicy(
        mode="live",
        max_concurrency=2,
        requests_per_minute=30,  # TODO: from the provider's rate-limit terms
        request_timeout_seconds=10.0,
    ),
    stale_after=timedelta(minutes=30),
    expire_after=timedelta(hours=6),
    price_stale_after=timedelta(minutes=10),
    price_expire_after=timedelta(hours=1),
    freshness_basis="retrieved_at",
    data_mapping="",  # TODO: stop-code table, time zone handling, currency
    onboarding=Onboarding(
        official_identity="",
        access_method="rest_api",
        allowed_usage="",
        redistribution_restrictions="",
        commercial_use_restrictions="",
        rate_limit_terms="",
        refresh_expectations="",
        contact_escalation="",
        technical_docs="",
        test_environment=None,
    ),
    enabled=False,
)
