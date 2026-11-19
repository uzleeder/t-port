"""T-AI's place knowledge: Uzbekistan's 14 regions and 28 places, in English and Uzbek.

The text comes verbatim from the T-Port place-card pack (app/data/places.json, built by
scripts/build_place_knowledge.py) with its sources. T-AI only looks things up here; it never
writes facts about places itself, so every answer can be traced to a listed source.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

from app.ai.rules import _find_locations
from app.services.catalog import LocationCatalog, _fold

DATA = Path(__file__).resolve().parent.parent / "data" / "places.json"
Lang = Literal["en", "uz"]


@dataclass(frozen=True)
class PlaceText:
    name: str
    area: str
    category: str
    history: str
    see: str
    tip: str


@dataclass(frozen=True)
class Place:
    key: str
    region: str
    kind: str
    image: str
    city_id: str
    city_name: str
    sources: tuple[tuple[str, str], ...]  # (label, url)
    text: dict[str, PlaceText]
    aliases: tuple[str, ...]

    @property
    def explore_url(self) -> str:
        return f"/explore/{self.region}#{self.key}"


@dataclass(frozen=True)
class Region:
    key: str
    name: str
    name_uz: str
    location_regions: tuple[str, ...]
    aliases: tuple[str, ...]


def _pattern(words: set[str]) -> re.Pattern[str]:
    alts = sorted(words, key=lambda w: (-len(w), w))
    return re.compile(rf"(?<!\w)({'|'.join(re.escape(w) for w in alts)})(?!\w)")


# Words that mark a question about a place rather than (only) a trip request.
_ASK = {
    # English
    "what",
    "see",
    "visit",
    "about",
    "tell",
    "history",
    "worth",
    "sights",
    "sightseeing",
    "attractions",
    "interesting",
    "famous",
    "info",
    "information",
    "know",
    "explain",
    "recommend",
    "things",
    "places",
    "explore",
    # Uzbek
    "haqida",
    "nima",
    "nimalar",
    "korish",
    "qiziq",
    "qiziqarli",
    "tarix",
    "tarixi",
    "mashhur",
    "tavsiya",
    "joylar",
    "aytib",
    "ayting",
    "bilasanmi",
    "bilasizmi",
    # Russian
    "что",
    "посмотреть",
    "достопримечательности",
    "расскажи",
    "расскажите",
    "история",
    "интересное",
}
# Words (after folding) that show the request is written in Uzbek.
_UZBEK = {
    "haqida",
    "nima",
    "nimalar",
    "qayer",
    "qayerga",
    "qayerdan",
    "qanday",
    "korish",
    "borish",
    "borsam",
    "sayohat",
    "joylar",
    "tarix",
    "viloyati",
    "viloyat",
    "shahri",
    "menga",
    "ayting",
    "aytib",
    "qiziq",
    "mumkin",
    "ertaga",
    "bugun",
    "yaxshi",
    "kerak",
    "bor",
    "chipta",
    "poyezd",
    "avtobus",
    "uchun",
    "bilan",
    "va",
}


class PlaceKnowledge:
    def __init__(self, data: dict) -> None:
        self.regions = {
            r["key"]: Region(
                key=r["key"],
                name=r["name"],
                name_uz=r["name_uz"],
                location_regions=tuple(r["location_regions"]),
                aliases=tuple(r["aliases"]),
            )
            for r in data["regions"]
        }
        self.places = [
            Place(
                key=p["key"],
                region=p["region"],
                kind=p["kind"],
                image=p["image"],
                city_id=p["city_id"],
                city_name=p["city_name"],
                sources=tuple((s["label"], s["url"]) for s in p["sources"]),
                text={lang: PlaceText(**p[lang]) for lang in ("en", "uz")},
                aliases=tuple(p["aliases"]),
            )
            for p in data["places"]
        ]
        self._place_by_alias = {_fold(a): p for p in self.places for a in p.aliases if len(_fold(a)) >= 4}
        self._place_re = _pattern(set(self._place_by_alias))
        self._region_by_alias = {_fold(a): r.key for r in self.regions.values() for a in r.aliases}
        self._region_re = _pattern(set(self._region_by_alias)) if self._region_by_alias else None
        self._region_by_location_region = {
            _fold(name): r.key for r in self.regions.values() for name in r.location_regions
        }

    @classmethod
    @cache
    def load(cls) -> PlaceKnowledge:
        return cls(json.loads(DATA.read_text(encoding="utf-8")))

    # --- lookups -------------------------------------------------------------------------------
    def in_region(self, region_key: str) -> list[Place]:
        """Destination first, then the landmark."""
        here = [p for p in self.places if p.region == region_key]
        return sorted(here, key=lambda p: p.kind != "destination")

    def region_of_location(self, location_id: str | None, catalog: LocationCatalog) -> str | None:
        loc = catalog.get(location_id) if location_id else None
        return self._region_by_location_region.get(_fold(loc.region)) if loc else None

    def find(self, text: str, catalog: LocationCatalog) -> list[Place]:
        """Places a message is about: named places first; otherwise the regions or cities it names."""
        folded = _fold(text)
        named: list[Place] = []
        for m in self._place_re.finditer(folded):
            p = self._place_by_alias[m.group(1)]
            if p not in named:
                named.append(p)
        if named:
            return named[:4]
        regions: list[str] = []
        if self._region_re:
            regions += [self._region_by_alias[m.group(1)] for m in self._region_re.finditer(folded)]
        for _, _, location_id in _find_locations(folded, catalog):
            if key := self.region_of_location(location_id, catalog):
                regions.append(key)
        seen: list[str] = list(dict.fromkeys(regions))
        return [p for key in seen[:2] for p in self.in_region(key)]

    def names_place(self, text: str) -> bool:
        """The message names one of the 28 places (not just a city or region)."""
        return bool(self._place_re.search(_fold(text)))

    @staticmethod
    def asks_about_places(text: str) -> bool:
        words = set(re.findall(r"\w+", _fold(text)))
        return bool(words & _ASK)

    @staticmethod
    def language(text: str) -> Lang:
        # oʻ / gʻ are distinctly Uzbek (but not the "o'" of "o'clock", which has no letter before it).
        if re.search(r"[oOgG][ʻ‘]", text) or re.search(r"\w[oOgG]['’`]\w", text):
            return "uz"
        words = set(re.findall(r"\w+", _fold(text)))
        return "uz" if len(words & _UZBEK) >= 1 and not words & {"the", "to", "from", "what", "is"} else "en"

    # --- wording ---------------------------------------------------------------------------------
    def region_name(self, key: str, lang: Lang) -> str:
        r = self.regions[key]
        return r.name_uz if lang == "uz" else r.name

    def intro(self, places: list[Place], lang: Lang, *, for_trip: bool = False) -> str:
        names = [p.text[lang].name for p in places]
        conj = "va" if lang == "uz" else "and"
        joined = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} {conj} {names[-1]}"
        regions = list(dict.fromkeys(p.region for p in places))
        if lang == "uz":
            if for_trip:
                return f"Manzilingizda ko‘rish mumkin bo‘lgan joylar: {joined}."
            if len(places) == 1:
                return f"{joined} haqida bilganlarim:"
            if len(regions) == 1:
                return f"{self.region_name(regions[0], lang)} haqida bilganlarim: {joined}."
            return f"Bilganlarim: {joined}."
        if for_trip:
            return f"While you're there: {joined}."
        if len(places) == 1:
            return f"Here's what I know about {joined}:"
        if len(regions) == 1:
            return f"Here's what I know about {self.region_name(regions[0], lang)}: {joined}."
        return f"Here's what I know: {joined}."

    @staticmethod
    def follow_up(lang: Lang) -> str:
        if lang == "uz":
            return "U yerga borishni xohlaysizmi? Qayerdan va qachon yo‘lga chiqishingizni yozing."
        return "Want to go there? Tell me where you're starting from and when."
