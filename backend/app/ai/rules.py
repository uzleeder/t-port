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


# One compiled alternation per catalogue (hundreds of names and aliases). Compiling a pattern per
# alias on every request overflowed the ``re`` cache and dominated assistant latency.
_NAME_INDEX: dict[int, tuple[LocationCatalog, re.Pattern[str], dict[str, str]]] = {}


def _name_index(catalog: LocationCatalog) -> tuple[re.Pattern[str], dict[str, str]]:
    cached = _NAME_INDEX.get(id(catalog))
    if cached is not None and cached[0] is catalog:
        return cached[1], cached[2]
    owner: dict[str, str] = {}
    for loc in catalog.search(None):
        for key in (_fold(loc.name), _fold(loc.id), *(_fold(a) for a in loc.aliases)):
            if len(key) >= 3:
                owner.setdefault(key, loc.id)  # first location in catalogue order wins a shared alias
    keys = sorted(owner, key=lambda k: (-len(k), k))  # longest first: leftmost-longest match
    pattern = re.compile(rf"(?<!\w)({'|'.join(re.escape(k) for k in keys)})\w{{0,3}}(?!\w)")
    _NAME_INDEX[id(catalog)] = (catalog, pattern, owner)
    return pattern, owner


def _find_locations(text: str, catalog: LocationCatalog) -> list[tuple[int, int, str]]:
    """(start, end, location_id) for every catalogued name/alias, longest match wins."""
    pattern, owner = _name_index(catalog)
    return [(m.start(), m.end(), owner[m.group(1)]) for m in pattern.finditer(text)]


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


# A clock time needs am/pm or minutes ("6 pm", "18:00", "9.30am"); a bare "by 6" is too ambiguous.
_TIME = r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?"


def _clock(hour: str, minute: str | None, ampm: str | None) -> str | None:
    if minute is None and ampm is None:
        return None
    h, m = int(hour), int(minute or 0)
    if ampm:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ampm.startswith("p") else 0)
    if h > 23 or m > 59:
        return None
    return f"{h:02d}:{m:02d}"


def _times(text: str) -> tuple[dict[str, str], str]:
    """Explicit clock constraints -> {depart_after, depart_before, arrive_before}, text without them."""
    found: dict[str, str] = {}
    patterns = [
        ("depart_after", rf"(?:leav\w*|depart\w*|set(?:ting)? off|go(?:ing)?)\s+(?:after|from)\s+{_TIME}"),
        ("depart_before", rf"(?:leav\w*|depart\w*|set(?:ting)? off|go(?:ing)?)\s+(?:before|by)\s+{_TIME}"),
        ("arrive_before", rf"(?:arriv\w*|be there|get there|reach\w*)\s+(?:by|before|until)\s+{_TIME}"),
        ("depart_after", rf"(?<!\w)(?:after|после)\s+{_TIME}"),
        ("depart_after", rf"{_TIME}\s*dan\s+keyin"),
        ("arrive_before", rf"(?<!\w)(?:by|before|к|до)\s+{_TIME}"),
        ("arrive_before", rf"{_TIME}\s*(?:gacha|ga qadar)"),
    ]
    for key, pattern in patterns:
        for m in re.finditer(pattern, text):
            value = _clock(m[1], m[2], m[3])
            if value and key not in found:
                found[key] = value
                text = text[: m.start()] + " " * (m.end() - m.start()) + text[m.end() :]
    return found, text


def _transfers(text: str) -> tuple[str, int | None]:
    if _has(
        text,
        [
            "direct",
            "non-stop",
            "nonstop",
            "no changes",
            "no transfers",
            "without changes",
            "without transfers",
            "to'g'ridan",
            "togridan",
            "прямой",
            "прямым",
            "без пересадок",
        ],
    ):
        return "direct", 0
    if re.search(r"(?:fewest|least|minimum|min|as few)\s+(?:\w+\s+)?(?:changes|transfers|connections)", text):
        return "fewest", None
    words = {"one": 1, "1": 1, "two": 2, "2": 2}
    change = r"(?:changes?|transfers?|connections?)"
    if m := re.search(rf"(?:up to|at most|max(?:imum)?)\s+(one|two|1|2)\s+{change}", text):
        return "any", words[m[1]]
    if m := re.search(rf"(?<!\w)(one|two|1|2)\s+{change}\s+(?:is |are )?(?:ok|fine|allowed)", text):
        return "any", words[m[1]]
    return "any", None


def _preferred(text: str) -> tuple[list[str], str]:
    """'prefer train', 'ideally by bus': a ranking preference, not a filter."""
    prefer: list[str] = []
    for mode, words in _MODE_WORDS.items():
        alt = "|".join(re.escape(w) for w in words)
        filler = r"(?:a\s+|the\s+|by\s+|to\s+take\s+(?:a\s+|the\s+)?)?"
        pattern = rf"(?:prefer\w*|ideally|preferably|rather)\s+{filler}(?:{alt})(?!\w)"
        for m in re.finditer(pattern, text):
            prefer.append(mode)
            text = text[: m.start()] + " " * (m.end() - m.start()) + text[m.end() :]
    return sorted(set(prefer)), text


_CURRENCIES = {
    "USD": r"\$|usd|dollars?|доллар\w*",
    "EUR": r"€|eur|euros?|евро",
    "RUB": r"rub|rubles?|roubles?|руб\w*",
}


def _foreign_budget(text: str) -> tuple[int, str] | None:
    for code, words in _CURRENCIES.items():
        m = re.search(rf"(?:{words})\s*(\d[\d,]*)(?!\w)", text) or re.search(
            rf"(?<![\w.])(\d[\d,]*)\s*(?:{words})(?!\w)", text
        )
        if m:
            return int(m[1].replace(",", "")), code
    return None


def parse(text: str, catalog: LocationCatalog, today: date) -> RawIntent:
    t = _fold(text)
    t = re.sub(r"[→>]|->|—|–", " to ", t)
    t = re.sub(r"\s+", " ", t)
    origin, destination = _route(t, catalog)
    times, t_rest = _times(t)
    prefer, t_rest = _preferred(t_rest)
    wanted, excluded = _modes(t_rest)
    transfer_pref, max_transfers = _transfers(t_rest)
    compare = bool(
        re.search(r"(?<!\w)(?:compare|comparison|versus|vs\.?|сравн\w*|solishtir\w*)(?!\w)", t)
        or (len(wanted) >= 2 and re.search(r"(?<!\w)(?:or|yoki|или)(?!\w)", t))
    )
    foreign = _foreign_budget(t)
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
        max_price_uzs=None if foreign else _max_price(t),
        time_preference=time_pref,
        depart_after=times.get("depart_after"),
        depart_before=times.get("depart_before"),
        arrive_before=times.get("arrive_before"),
        transfer_preference=transfer_pref,
        max_transfers=max_transfers,
        prefer_modes=prefer,
        compare_modes=compare,
        budget_amount=foreign[0] if foreign else None,
        budget_currency=foreign[1] if foreign else None,
        unsupported_reason=unsupported,
    )
