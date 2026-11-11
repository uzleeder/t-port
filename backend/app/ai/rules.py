"""Deterministic natural-language parser (no network, no credentials).

Understands English plus common Uzbek/Russian travel words, e.g.
"cheapest way from Tashkent to Samarkand tomorrow", "Buxoro ertaga poyezd",
"flight to Termez on Friday under 900k", "no taxis, morning, Toshkent - Xiva".
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from app.ai.intent import RawIntent
from app.services.catalog import LocationCatalog, _fold

_MODE_WORDS = {
    "train": ["train", "trains", "rail", "railway", "poyezd", "poezd", "поезд", "поезде", "поездом"],
    "bus": ["bus", "buses", "coach", "coaches", "avtobus", "автобус", "автобусе", "автобусом"],
    "flight": [
        "flight",
        "flights",
        "fly",
        "flying",
        "plane",
        "air",
        "airplane",
        "samolyot",
        "самолет",
        "самолёт",
        "самолетом",
        "рейс",
    ],
    "taxi": ["taxi", "taxis", "cab", "car", "taksi", "такси"],
}
_NEGATORS = r"(?:no|not|without|avoid|except|bez|без|не)"
_WEEKDAYS = {
    0: ["monday", "mon", "dushanba", "понедельник"],
    1: ["tuesday", "tue", "seshanba", "вторник"],
    2: ["wednesday", "wed", "chorshanba", "среда", "среду"],
    3: ["thursday", "thu", "payshanba", "четверг"],
    4: ["friday", "fri", "juma", "пятница", "пятницу"],
    5: ["saturday", "sat", "shanba", "суббота", "субботу"],
    6: ["sunday", "sun", "yakshanba", "воскресенье"],
}
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _has(text: str, words: list[str]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text) for w in words)


def _find_locations(text: str, catalog: LocationCatalog) -> list[tuple[int, int, str]]:
    """(start, end, location_id) for every catalogued name/alias, longest match wins."""
    hits: list[tuple[int, int, str]] = []
    for loc in catalog.search(None):
        for key in {_fold(loc.name), _fold(loc.id), *(_fold(a) for a in loc.aliases)}:
            if len(key) < 3:
                continue
            for m in re.finditer(rf"(?<!\w){re.escape(key)}\w{{0,3}}(?!\w)", text):
                hits.append((m.start(), m.end(), loc.id))
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    out: list[tuple[int, int, str]] = []
    for h in hits:
        if out and h[0] < out[-1][1]:
            continue  # overlaps a longer/earlier match
        out.append(h)
    return out


def _route(text: str, catalog: LocationCatalog) -> tuple[str | None, str | None]:
    hits = _find_locations(text, catalog)
    origin = destination = None
    for start, _, loc_id in hits:
        before = text[max(0, start - 12) : start]
        if re.search(r"(?<!\w)(?:from|из|от)\s*$", before):
            origin = origin or loc_id
        elif re.search(r"(?<!\w)(?:to|towards|into|в|до)\s*$", before):
            destination = destination or loc_id
    # Uzbek suffixes: "Toshkentdan" (from) / "Samarqandga" (to)
    for _start, end, loc_id in hits:
        tail = text[end - 3 : end + 3]
        if origin is None and re.search(r"dan(?!\w)", tail):
            origin = loc_id
        elif destination is None and re.search(r"ga(?!\w)", tail):
            destination = loc_id
    remaining = [h[2] for h in hits if h[2] not in (origin, destination)]
    if origin is None and remaining:
        origin = remaining.pop(0)
    if destination is None and remaining:
        destination = remaining.pop(0)
    return origin, destination


def _date(text: str, today: date) -> str | None:
    if _has(text, ["day after tomorrow", "indinga", "послезавтра"]):
        return (today + timedelta(days=2)).isoformat()
    if _has(text, ["tomorrow", "ertaga", "завтра"]):
        return (today + timedelta(days=1)).isoformat()
    if _has(text, ["today", "tonight", "bugun", "сегодня"]):
        return today.isoformat()
    if m := re.search(r"in (\d{1,2}) days?", text):
        return (today + timedelta(days=int(m.group(1)))).isoformat()
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", text):
        try:
            return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            return "invalid"
    month_names = "|".join(_MONTHS)
    m = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})\w*", text) or re.search(
        rf"({month_names})\w*\s+(\d{{1,2}})(?:st|nd|rd|th)?(?!\d)", text
    )
    if m:
        day_s, mon_s = (m[1], m[2]) if m[1].isdigit() else (m[2], m[1])
        return _future(int(day_s), _MONTHS[mon_s[:3]], today)
    if m := re.search(r"(?<![\d:])(\d{1,2})[./](\d{1,2})(?![\d:])", text):
        return _future(int(m[1]), int(m[2]), today)
    for weekday, words in _WEEKDAYS.items():
        if _has(text, words):
            delta = (weekday - today.weekday()) % 7
            if delta == 0 or re.search(rf"next\s+(?:{'|'.join(words)})", text):
                delta = delta or 7
            return (today + timedelta(days=delta)).isoformat()
    return None


def _future(day: int, month: int, today: date) -> str:
    """Day/month without a year: the next occurrence on or after today."""
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return "invalid"
        if d >= today:
            return d.isoformat()
    return "invalid"


def _modes(text: str) -> tuple[list[str], list[str]]:
    wanted, excluded = [], []
    for mode, words in _MODE_WORDS.items():
        alt = "|".join(re.escape(w) for w in words)
        if re.search(rf"(?<!\w){_NEGATORS}\s+(?:\w+\s+)?(?:{alt})(?!\w)", text):
            excluded.append(mode)
        elif _has(text, words):
            wanted.append(mode)
    return wanted, excluded


def _max_price(text: str) -> int | None:
    m = re.search(
        r"(?:under|below|less than|max(?:imum)?|up to|within|budget(?: of)?|до|gacha)\s*"
        r"(\d[\d\s,.]*)\s*(k|thousand|ming|тыс\w*|m|million|mln|млн)?",
        text,
    )
    if not m:
        return None
    try:
        value = float(re.sub(r"[\s,]", "", m[1]).rstrip("."))
    except ValueError:
        return None
    unit = (m[2] or "").lower()
    if unit in ("k", "thousand", "ming") or unit.startswith("тыс"):
        value *= 1_000
    elif unit in ("m", "million", "mln", "млн"):
        value *= 1_000_000
    return int(value) if value >= 1_000 else None


def parse(text: str, catalog: LocationCatalog, today: date) -> RawIntent:
    t = _fold(text)
    t = re.sub(r"[→>]|->|—|–", " to ", t)
    t = re.sub(r"\s+", " ", t)
    origin, destination = _route(t, catalog)
    wanted, excluded = _modes(t)
    time_pref = "any"
    if _has(t, ["fastest", "quickest", "shortest", "tez", "быстр"]) or re.search(r"быстр\w*", t):
        time_pref = "fastest"
    elif _has(t, ["earliest", "first", "as soon as possible", "asap", "ertalabki birinchi"]):
        time_pref = "earliest"
    elif _has(t, ["morning", "ertalab", "утром", "утро"]):
        time_pref = "morning"
    elif _has(t, ["afternoon", "tushdan keyin", "днем", "днём"]):
        time_pref = "afternoon"
    elif _has(t, ["evening", "tonight", "kechqurun", "вечером", "вечер"]):
        time_pref = "evening"
    elif _has(t, ["night", "overnight", "kechasi", "ночью", "ночной"]):
        time_pref = "night"
    budget = (
        "lowest"
        if (
            _has(t, ["cheapest", "cheap", "cheaper", "budget", "lowest price", "arzon", "eng arzon"])
            or re.search(r"дешев\w*", t)
        )
        else "any"
    )
    unsupported = None
    if _has(t, ["hotel", "hostel", "mehmonxona", "гостиница", "отель"]) and not (origin or destination):
        unsupported = "T-Port plans journeys; it does not search accommodation."
    return RawIntent(
        origin_id=origin,
        destination_id=destination,
        travel_date=_date(t, today),
        modes=wanted,
        excluded_modes=excluded,
        budget_preference=budget,
        max_price_uzs=_max_price(t),
        time_preference=time_pref,
        unsupported_reason=unsupported,
    )
