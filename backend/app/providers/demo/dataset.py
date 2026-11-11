"""DEMONSTRATION timetable. NOT real schedules, fares, or operators.

Operator names are fictional ("Demo ..."). Times, durations and prices are
plausible-looking placeholders chosen to exercise the search engine; they must
never be presented as real travel information.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.models import ScheduleType, TransportMode

DATASET_VERSION = "demo-2026.11"
DATASET_UPDATED_AT = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
CURRENCY = "UZS"

ALL_DAYS = frozenset(range(7))  # Monday=0 ... Sunday=6
WEEKEND = frozenset({4, 5, 6})  # Fri-Sun demand surcharge in demo pricing
WEEKEND_MULTIPLIER = Decimal("1.10")


@dataclass(frozen=True, slots=True)
class FareClass:
    name: str
    multiplier: Decimal


ECONOMY = (FareClass("Economy", Decimal("1")),)
EXPRESS_FARES = (FareClass("Economy", Decimal("1")), FareClass("Business", Decimal("1.6")))
NIGHT_TRAIN_FARES = (FareClass("Seat", Decimal("1")), FareClass("Couchette", Decimal("1.5")))
FLIGHT_FARES = (FareClass("Economy", Decimal("1")), FareClass("Business", Decimal("2.4")))
BUS_FARES = (FareClass("Standard", Decimal("1")),)
TAXI_FARES = (FareClass("Private car (estimate)", Decimal("1")),)


@dataclass(frozen=True, slots=True)
class ServiceTemplate:
    code: str
    mode: TransportMode
    operator: str
    origin_station: str
    destination_station: str
    depart_local: str | None  # "HH:MM" in Asia/Tashkent; None for on-demand
    duration_minutes: int
    base_price: Decimal
    fares: tuple[FareClass, ...]
    days: frozenset[int] = ALL_DAYS
    price_max: Decimal | None = None  # estimate upper bound (taxi)

    @property
    def schedule_type(self) -> ScheduleType:
        return ScheduleType.ON_DEMAND if self.depart_local is None else ScheduleType.SCHEDULED


RAIL_EXPRESS = "Demo Rail Express"
RAIL_REGIONAL = "Demo Rail Regional"
COACH = "Demo Coach Lines"
AIR = "Demo Air"
TAXI = "Demo Taxi Network"

T, B, F, X = TransportMode.TRAIN, TransportMode.BUS, TransportMode.FLIGHT, TransportMode.TAXI

_templates: list[ServiceTemplate] = []
_counter: dict[str, int] = {}


def _code(mode: TransportMode) -> str:
    prefix = {T: "TR", B: "BU", F: "FL", X: "TX"}[mode]
    _counter[prefix] = _counter.get(prefix, 100) + 1
    return f"{prefix}{_counter[prefix]}"


def route(
    mode: TransportMode,
    operator: str,
    a: str,
    b: str,
    minutes: int,
    price: int,
    out: tuple[str, ...],
    back: tuple[str, ...],
    fares: tuple[FareClass, ...],
    days: frozenset[int] = ALL_DAYS,
) -> None:
    suffix = {T: "rail", B: "bus", F: "air"}[mode]
    for origin, dest, times in ((a, b, out), (b, a, back)):
        for hhmm in times:
            _templates.append(
                ServiceTemplate(
                    _code(mode),
                    mode,
                    operator,
                    f"{origin}-{suffix}",
                    f"{dest}-{suffix}",
                    hhmm,
                    minutes,
                    Decimal(price),
                    fares,
                    days,
                )
            )


def taxi(a: str, b: str, minutes: int, low: int, high: int) -> None:
    for origin, dest in ((a, b), (b, a)):
        _templates.append(
            ServiceTemplate(
                _code(X),
                X,
                TAXI,
                f"{origin}-city",
                f"{dest}-city",
                None,
                minutes,
                Decimal(low),
                TAXI_FARES,
                ALL_DAYS,
                Decimal(high),
            )
        )


# --- Tashkent hub -------------------------------------------------------------
route(
    T,
    RAIL_EXPRESS,
    "tashkent",
    "samarkand",
    130,
    270_000,
    ("08:00", "17:00"),
    ("09:30", "18:30"),
    EXPRESS_FARES,
)
route(T, RAIL_REGIONAL, "tashkent", "samarkand", 250, 120_000, ("06:10",), ("14:40",), ECONOMY)
route(B, COACH, "tashkent", "samarkand", 300, 90_000, ("09:00", "22:00"), ("08:00", "21:30"), BUS_FARES)
taxi("tashkent", "samarkand", 270, 400_000, 600_000)

route(T, RAIL_EXPRESS, "tashkent", "bukhara", 240, 400_000, ("07:30",), ("15:00",), EXPRESS_FARES)
route(T, RAIL_REGIONAL, "tashkent", "bukhara", 600, 200_000, ("20:30",), ("19:00",), NIGHT_TRAIN_FARES)
route(B, COACH, "tashkent", "bukhara", 540, 150_000, ("08:30",), ("07:30",), BUS_FARES)
route(
    F, AIR, "tashkent", "bukhara", 75, 700_000, ("07:15",), ("19:40",), FLIGHT_FARES, frozenset({0, 2, 4, 6})
)
taxi("tashkent", "bukhara", 540, 900_000, 1_300_000)

route(T, RAIL_REGIONAL, "tashkent", "khiva", 900, 350_000, ("18:00",), ("16:00",), NIGHT_TRAIN_FARES)
route(F, AIR, "tashkent", "urgench", 100, 900_000, ("06:40", "16:20"), ("09:10", "19:00"), FLIGHT_FARES)
route(T, RAIL_REGIONAL, "tashkent", "urgench", 840, 320_000, ("19:00",), ("17:30",), NIGHT_TRAIN_FARES)
route(F, AIR, "tashkent", "nukus", 110, 950_000, ("08:20",), ("11:30",), FLIGHT_FARES, frozenset({1, 3, 5}))
route(F, AIR, "tashkent", "termez", 90, 850_000, ("09:30",), ("12:00",), FLIGHT_FARES)
route(T, RAIL_REGIONAL, "tashkent", "termez", 900, 280_000, ("17:30",), ("16:30",), NIGHT_TRAIN_FARES)
route(T, RAIL_EXPRESS, "tashkent", "karshi", 210, 300_000, ("07:00",), ("15:30",), EXPRESS_FARES)
route(B, COACH, "tashkent", "karshi", 420, 110_000, ("10:00",), ("09:00",), BUS_FARES)
route(T, RAIL_EXPRESS, "tashkent", "navoi", 190, 330_000, ("09:30",), ("16:00",), EXPRESS_FARES)
route(
    B,
    COACH,
    "tashkent",
    "jizzakh",
    180,
    60_000,
    ("08:00", "12:00", "17:00"),
    ("07:00", "11:00", "16:00"),
    BUS_FARES,
)
taxi("tashkent", "jizzakh", 150, 250_000, 350_000)

# --- Fergana Valley ----------------------------------------------------------
route(T, RAIL_REGIONAL, "tashkent", "andijan", 330, 160_000, ("07:35",), ("15:20",), ECONOMY)
route(B, COACH, "tashkent", "andijan", 360, 100_000, ("08:00",), ("08:30",), BUS_FARES)
route(F, AIR, "tashkent", "andijan", 60, 600_000, ("13:00",), ("15:10",), FLIGHT_FARES, frozenset({0, 4}))
taxi("tashkent", "andijan", 330, 450_000, 700_000)
route(T, RAIL_REGIONAL, "tashkent", "namangan", 300, 150_000, ("08:30",), ("16:10",), ECONOMY)
route(B, COACH, "tashkent", "namangan", 330, 95_000, ("09:30",), ("09:00",), BUS_FARES)
taxi("tashkent", "namangan", 300, 400_000, 650_000)
route(T, RAIL_REGIONAL, "tashkent", "fergana", 330, 155_000, ("07:00",), ("15:00",), ECONOMY)
route(B, COACH, "tashkent", "fergana", 360, 100_000, ("11:00",), ("10:30",), BUS_FARES)
route(F, AIR, "tashkent", "fergana", 60, 600_000, ("15:00",), ("17:10",), FLIGHT_FARES, frozenset({1, 5}))
taxi("tashkent", "fergana", 330, 450_000, 700_000)
route(T, RAIL_REGIONAL, "tashkent", "kokand", 240, 130_000, ("07:00",), ("15:30",), ECONOMY)
route(B, COACH, "andijan", "fergana", 90, 25_000, ("08:00", "14:00"), ("10:00", "16:00"), BUS_FARES)
route(B, COACH, "namangan", "andijan", 90, 25_000, ("09:00",), ("12:00",), BUS_FARES)
route(B, COACH, "kokand", "fergana", 90, 25_000, ("10:00",), ("13:00",), BUS_FARES)

# --- Silk Road corridor -----------------------------------------------------
route(T, RAIL_EXPRESS, "samarkand", "bukhara", 95, 180_000, ("10:20",), ("17:10",), EXPRESS_FARES)
route(B, COACH, "samarkand", "bukhara", 240, 80_000, ("13:00",), ("08:30",), BUS_FARES)
taxi("samarkand", "bukhara", 230, 350_000, 500_000)
route(B, COACH, "samarkand", "karshi", 180, 70_000, ("10:00",), ("14:00",), BUS_FARES)
route(T, RAIL_REGIONAL, "karshi", "termez", 300, 120_000, ("14:00",), ("07:00",), ECONOMY)
route(T, RAIL_REGIONAL, "bukhara", "khiva", 420, 180_000, ("09:00",), ("14:00",), ECONOMY)
route(B, COACH, "bukhara", "khiva", 480, 130_000, ("08:00",), ("07:30",), BUS_FARES)
route(
    B,
    COACH,
    "urgench",
    "khiva",
    45,
    8_000,
    ("09:00", "13:00", "17:00"),
    ("10:00", "14:00", "18:00"),
    BUS_FARES,
)
taxi("urgench", "khiva", 40, 60_000, 100_000)

TEMPLATES: tuple[ServiceTemplate, ...] = tuple(_templates)
TEMPLATES_BY_CODE: dict[str, ServiceTemplate] = {t.code: t for t in TEMPLATES}
