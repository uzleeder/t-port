"""Administrative geography supplied for the Uzbekistan location catalog."""

from app.domain.models import Location

# Each group contains the region, its districts, and cities outside the existing catalog.
_AREAS = (
    (
        "Qoraqalpogʻiston Respublikasi",
        "Amudaryo, Beruniy, Boʻzatov, Chimboy, Ellikqalʼa, Kegeyli, Moʻynoq, Nukus, Qanlikoʻl, "
        "Qoʻngʻirot, Qoraoʻzak, Shumanay, Taxtakoʻpir, Taxiatosh, Toʻrtkoʻl, Xoʻjayli",
        "",
    ),
    (
        "Andijon viloyati",
        "Andijon, Asaka, Baliqchi, Boʻston, Buloqboshi, Izboskan, Jalaquduq, Marhamat, "
        "Oltinkoʻl, Paxtaobod, Qoʻrgʻontepa, Shahrixon, Ulugʻnor, Xoʻjaobod",
        "Xonobod",
    ),
    (
        "Buxoro viloyati",
        "Buxoro, Gʻijduvon, Jondor, Kogon, Olot, Peshku, Qorakoʻl, Qorovulbozor, Romitan, Shofirkon, Vobkent",
        "Kogon",
    ),
    (
        "Fargʻona viloyati",
        "Bagʻdod, Beshariq, Buvayda, Dangʻara, Fargʻona, Furqat, Oltiariq, Oʻzbekiston, "
        "Qoʻshtepa, Quva, Rishton, Soʻx, Toshloq, Uchkoʻprik, Yozyovon",
        "Margʻilon, Quvasoy",
    ),
    (
        "Jizzax viloyati",
        "Arnasoy, Baxmal, Doʻstlik, Forish, Gʻallaorol, Mirzachoʻl, Paxtakor, Sharof Rashidov, "
        "Yangiobod, Zafarobod, Zarbdor, Zomin",
        "",
    ),
    (
        "Namangan viloyati",
        "Chortoq, Chust, Kosonsoy, Mingbuloq, Namangan, Norin, Pop, Toʻraqoʻrgʻon, Uchqoʻrgʻon, "
        "Uychi, Yangiqoʻrgʻon",
        "",
    ),
    (
        "Navoiy viloyati",
        "Karmana, Konimex, Navbahor, Nurota, Qiziltepa, Tomdi, Uchquduq, Xatirchi",
        "Zarafshon, Gʻozgʻon",
    ),
    (
        "Qashqadaryo viloyati",
        "Chiroqchi, Dehqonobod, Gʻuzor, Kasbi, Kitob, Koʻkdala, Koson, Mirishkor, Muborak, "
        "Nishon, Qamashi, Qarshi, Shahrisabz, Yakkabogʻ",
        "Shahrisabz",
    ),
    (
        "Samarqand viloyati",
        "Bulungʻur, Ishtixon, Jomboy, Kattaqoʻrgʻon, Narpay, Nurobod, Oqdaryo, Pastdargʻom, "
        "Paxtachi, Payariq, Qoʻshrabot, Samarqand, Toyloq, Urgut",
        "Kattaqoʻrgʻon",
    ),
    (
        "Sirdaryo viloyati",
        "Boyovut, Guliston, Mirzaobod, Oqoltin, Sardoba, Sayxunobod, Sirdaryo, Xovos",
        "Guliston, Shirin, Yangiyer",
    ),
    (
        "Surxondaryo viloyati",
        "Angor, Bandixon, Boysun, Denov, Jarqoʻrgʻon, Muzrabot, Oltinsoy, Qiziriq, Qumqoʻrgʻon, "
        "Sariosiyo, Sherobod, Shoʻrchi, Termiz, Uzun",
        "",
    ),
    (
        "Toshkent viloyati",
        "Bekobod, Boʻka, Boʻstonliq, Chinoz, Ohangaron, Oqqoʻrgʻon, Oʻrta Chirchiq, Parkent, "
        "Piskent, Qibray, Quyi Chirchiq, Toshkent, Yangiyoʻl, Yuqori Chirchiq, Zangiota",
        "Nurafshon, Angren, Bekobod, Chirchiq, Ohangaron, Olmaliq, Yangiyoʻl",
    ),
    (
        "Xorazm viloyati",
        "Bogʻot, Gurlan, Qoʻshkoʻpir, Shovot, Tuproqqalʼa, Urganch, Xazorasp, Xiva, Xonqa, "
        "Yangiariq, Yangibozor",
        "",
    ),
    (
        "Toshkent shahri",
        "Bektemir, Chilonzor, Mirobod, Mirzo Ulugʻbek, Olmazor, Sergeli, Shayxontohur, Uchtepa, "
        "Yakkasaroy, Yangihayot, Yashnobod, Yunusobod",
        "",
    ),
)

_CAPITAL = "Toshkent shahri"
_NAMANGAN_CITY = "Namangan shahri"
_APOSTROPHES = str.maketrans("", "", "'ʻʼ")


def _slug(name: str) -> str:
    return name.casefold().translate(_APOSTROPHES).replace(" ", "-")


def administrative_locations(cities: tuple[Location, ...], timezone: str) -> tuple[Location, ...]:
    known_city_names = {_slug(name) for city in cities for name in (city.name, *city.aliases)}
    known_city_names.update(
        _slug(city) for _, _, extra_cities in _AREAS for city in extra_cities.split(", ") if city
    )
    locations = []
    for region, districts, extra_cities in _AREAS:
        region_id = _slug(region.split()[0])
        if region != _CAPITAL:
            locations.append(Location(f"region-{region_id}", region, "UZ", region, timezone, None, None))
        else:
            region_id = "toshkent-city"
        for city in filter(None, extra_cities.split(", ")):
            locations.append(Location(f"city-{_slug(city)}", city, "UZ", region, timezone, None, None))
        locations.extend(_districts(region, region_id, districts, timezone, known_city_names))
    locations.extend(
        _districts(_NAMANGAN_CITY, "namangan-city", "Davlatobod, Yangi Namangan", timezone, known_city_names)
    )
    return tuple(locations)


def _districts(
    region: str, region_id: str, names: str, timezone: str, known_city_names: set[str]
) -> list[Location]:
    return [
        Location(
            f"district-{region_id}-{_slug(name)}",
            f"{name} tumani",
            "UZ",
            region,
            timezone,
            None,
            None,
            (name,) if _slug(name) not in known_city_names else (),
        )
        for name in names.split(", ")
    ]
