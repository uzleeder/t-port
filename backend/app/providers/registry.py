"""Provider registry: every data source T-Port may use, with its documented basis.

A provider may be enabled only when ``access_basis`` names the authorisation
under which its data is used (licence, written agreement, open-data terms).
No live provider is registered in Phase 1: T-Port has no confirmed agreements.
See docs/providers.md for the onboarding checklist.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import ProviderInfo
from app.providers.demo.adapter import DEMO_PROVIDER


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    info: ProviderInfo
    access_basis: str
    update_frequency: str | None
    reliability_notes: str


REGISTRATIONS: tuple[ProviderRegistration, ...] = (
    ProviderRegistration(
        info=DEMO_PROVIDER,
        access_basis=(
            "Internal simulated dataset created by T-Port. No external source; no permissions required."
        ),
        update_frequency="Generated on request (live mode) or per import run (stored mode).",
        reliability_notes="Synthetic. Must never be presented as real travel information.",
    ),
)
