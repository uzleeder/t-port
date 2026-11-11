"""Reference geography for the initial market (Uzbekistan).

City names, regions and approximate coordinates are public geographic facts.
Station entries are *generic points* used to anchor demo services; they are
not a verified station registry. Airport IATA codes are included where well
known. This module is replaced by the ``locations``/``stations`` tables in
Milestone 3.
"""

from app.data.administrative import administrative_locations
from app.domain.models import Location, Station, StationKind

TZ = "Asia/Tashkent"

_CITIES: tuple[Location, ...] = (
    Location(
        "tashkent",
        "Tashkent",
        "UZ",
        "Tashkent City",
        TZ,
        41.2995,
        69.2401,
        ("Toshkent", "Ташкент", "Tashkent City", "Toshkent shahri"),
    ),
    Location(
        "samarkand", "Samarkand", "UZ", "Samarkand Region", TZ, 39.6542, 66.9597, ("Samarqand", "Самарканд")
    ),
    Location("bukhara", "Bukhara", "UZ", "Bukhara Region", TZ, 39.7681, 64.4556, ("Buxoro", "Бухара")),
    Location("khiva", "Khiva", "UZ", "Khorezm Region", TZ, 41.3783, 60.3639, ("Xiva", "Хива")),
    Location("urgench", "Urgench", "UZ", "Khorezm Region", TZ, 41.5500, 60.6333, ("Urganch", "Ургенч")),
    Location("nukus", "Nukus", "UZ", "Republic of Karakalpakstan", TZ, 42.4531, 59.6103, ("Nukus", "Нукус")),
    Location("navoi", "Navoi", "UZ", "Navoiy Region", TZ, 40.0844, 65.3792, ("Navoiy", "Навои")),
    Location("karshi", "Karshi", "UZ", "Kashkadarya Region", TZ, 38.8606, 65.7891, ("Qarshi", "Карши")),
    Location("termez", "Termez", "UZ", "Surkhandarya Region", TZ, 37.2242, 67.2783, ("Termiz", "Термез")),
    Location("jizzakh", "Jizzakh", "UZ", "Jizzakh Region", TZ, 40.1158, 67.8422, ("Jizzax", "Джизак")),
    Location("andijan", "Andijan", "UZ", "Andijan Region", TZ, 40.7821, 72.3442, ("Andijon", "Андижан")),
    Location("namangan", "Namangan", "UZ", "Namangan Region", TZ, 40.9983, 71.6726, ("Namangan", "Наманган")),
    Location(
        "fergana", "Fergana", "UZ", "Fergana Region", TZ, 40.3842, 71.7843, ("Farg'ona", "Fargona", "Фергана")
    ),
    Location("kokand", "Kokand", "UZ", "Fergana Region", TZ, 40.5286, 70.9425, ("Qo'qon", "Qoqon", "Коканд")),
)

LOCATIONS = _CITIES + administrative_locations(_CITIES, TZ)

_RAIL = StationKind.RAIL_STATION
_BUS = StationKind.BUS_TERMINAL
_AIR = StationKind.AIRPORT

STATIONS: tuple[Station, ...] = (
    Station("tashkent-rail", "Tashkent railway station", "tashkent", _RAIL),
    Station("tashkent-bus", "Tashkent intercity bus terminal", "tashkent", _BUS),
    Station("tashkent-air", "Tashkent International Airport", "tashkent", _AIR, "TAS"),
    Station("samarkand-rail", "Samarkand railway station", "samarkand", _RAIL),
    Station("samarkand-bus", "Samarkand bus terminal", "samarkand", _BUS),
    Station("samarkand-air", "Samarkand International Airport", "samarkand", _AIR, "SKD"),
    Station("bukhara-rail", "Bukhara railway station", "bukhara", _RAIL),
    Station("bukhara-bus", "Bukhara bus terminal", "bukhara", _BUS),
    Station("bukhara-air", "Bukhara International Airport", "bukhara", _AIR, "BHK"),
    Station("khiva-rail", "Khiva railway station", "khiva", _RAIL),
    Station("khiva-bus", "Khiva bus stop", "khiva", _BUS),
    Station("urgench-rail", "Urgench railway station", "urgench", _RAIL),
    Station("urgench-bus", "Urgench bus terminal", "urgench", _BUS),
    Station("urgench-air", "Urgench International Airport", "urgench", _AIR, "UGC"),
    Station("nukus-air", "Nukus Airport", "nukus", _AIR, "NCU"),
    Station("navoi-rail", "Navoi railway station", "navoi", _RAIL),
    Station("karshi-rail", "Karshi railway station", "karshi", _RAIL),
    Station("karshi-bus", "Karshi bus terminal", "karshi", _BUS),
    Station("termez-rail", "Termez railway station", "termez", _RAIL),
    Station("termez-air", "Termez Airport", "termez", _AIR, "TMJ"),
    Station("jizzakh-bus", "Jizzakh bus terminal", "jizzakh", _BUS),
    Station("andijan-rail", "Andijan railway station", "andijan", _RAIL),
    Station("andijan-bus", "Andijan bus terminal", "andijan", _BUS),
    Station("andijan-air", "Andijan Airport", "andijan", _AIR, "AZN"),
    Station("namangan-rail", "Namangan railway station", "namangan", _RAIL),
    Station("namangan-bus", "Namangan bus terminal", "namangan", _BUS),
    Station("fergana-rail", "Fergana railway station", "fergana", _RAIL),
    Station("fergana-bus", "Fergana bus terminal", "fergana", _BUS),
    Station("fergana-air", "Fergana International Airport", "fergana", _AIR, "FEG"),
    Station("kokand-rail", "Kokand railway station", "kokand", _RAIL),
    Station("kokand-bus", "Kokand bus terminal", "kokand", _BUS),
    # Door-to-door points for on-demand services such as taxis.
    *(
        Station(f"{loc.id}-city", f"{loc.name} (door-to-door)", loc.id, StationKind.CITY_POINT)
        for loc in _CITIES
    ),
)
