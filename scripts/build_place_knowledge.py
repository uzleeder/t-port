"""Build T-AI's place knowledge from the place-card pack.

Reads content/place-cards/en.md (English copy) and uz.md (Uzbek copy), the text that came with
the 28 illustrated cards, and writes the same JSON to

    backend/app/data/places.json            (T-AI answers questions from it)
    frontend/src/lib/explore-places.json     (the Explore pages show it)

so both always say the same thing. Text is copied verbatim; nothing is generated. T-Port-specific
details that are not in the pack (stable keys, search aliases, nearest city with journeys) are in
META below.

    python scripts/build_place_knowledge.py          # write both files
    python scripts/build_place_knowledge.py --check  # fail if they are out of date
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {"en": ROOT / "content/place-cards/en.md", "uz": ROOT / "content/place-cards/uz.md"}
OUTPUTS = [ROOT / "backend/app/data/places.json", ROOT / "frontend/src/lib/explore-places.json"]

# The 14 regions: English and Uzbek names, the region names T-Port's location catalogue uses, and
# extra words people use for the region itself.
REGIONS = [
    ("tashkent-city", "Tashkent", "Toshkent shahri", ["Tashkent City", "Toshkent shahri"], []),
    ("tashkent-region", "Tashkent Region", "Toshkent viloyati", ["Tashkent Region", "Toshkent viloyati"],
     ["tashkent region", "toshkent viloyati"]),
    ("samarkand", "Samarkand", "Samarqand viloyati", ["Samarkand Region", "Samarqand viloyati"], []),
    ("bukhara", "Bukhara", "Buxoro viloyati", ["Bukhara Region", "Buxoro viloyati"], []),
    ("khorezm", "Khorezm", "Xorazm viloyati", ["Khorezm Region", "Xorazm viloyati"], ["khorezm", "xorazm", "khwarazm"]),
    ("fergana", "Fergana", "Fargʻona viloyati", ["Fergana Region", "Fargʻona viloyati"], ["fergana valley", "ferghana"]),
    ("andijan", "Andijan", "Andijon viloyati", ["Andijan Region", "Andijon viloyati"], []),
    ("namangan", "Namangan", "Namangan viloyati", ["Namangan Region", "Namangan viloyati", "Namangan shahri"], []),
    ("kashkadarya", "Kashkadarya", "Qashqadaryo viloyati", ["Kashkadarya Region", "Qashqadaryo viloyati"],
     ["kashkadarya", "qashqadaryo"]),
    ("surkhandarya", "Surkhandarya", "Surxondaryo viloyati", ["Surkhandarya Region", "Surxondaryo viloyati"],
     ["surkhandarya", "surxondaryo"]),
    ("jizzakh", "Jizzakh", "Jizzax viloyati", ["Jizzakh Region", "Jizzax viloyati"], []),
    ("syrdarya", "Syrdarya", "Sirdaryo viloyati", ["Syrdarya Region", "Sirdaryo viloyati"], ["syrdarya", "sirdaryo"]),
    ("navoi", "Navoi", "Navoiy viloyati", ["Navoiy Region", "Navoiy viloyati"], []),
    ("karakalpakstan", "Karakalpakstan", "Qoraqalpogʻiston Respublikasi",
     ["Republic of Karakalpakstan", "Qoraqalpogʻiston Respublikasi"], ["karakalpakstan", "qoraqalpogiston"]),
]

# Per card number: key, region, kind, nearest city T-Port finds journeys to, search aliases.
META = {
    1: ("humo-arena", "tashkent-city", "landmark", ("tashkent", "Tashkent"), ["humo arena", "humo"]),
    2: ("hazrati-imam", "tashkent-city", "destination", ("tashkent", "Tashkent"),
        ["hazrati imam", "hazrati imom", "hazrat imam", "khast imam", "hast imam"]),
    3: ("charvak-dam", "tashkent-region", "landmark", ("tashkent", "Tashkent"), ["charvak", "chorvoq", "charvaq"]),
    4: ("amirsoy", "tashkent-region", "destination", ("tashkent", "Tashkent"), ["amirsoy", "amirsay"]),
    5: ("registan", "samarkand", "landmark", ("samarkand", "Samarkand"), ["registan", "registon"]),
    6: ("shah-i-zinda", "samarkand", "destination", ("samarkand", "Samarkand"),
        ["shah-i-zinda", "shah i zinda", "shahi zinda", "shohi zinda", "shakhi zinda"]),
    7: ("poi-kalon", "bukhara", "landmark", ("bukhara", "Bukhara"),
        ["poi kalon", "po-i-kalyan", "poi kalyan", "kalon minaret", "kalyan minaret", "minorai kalon"]),
    8: ("lyabi-hauz", "bukhara", "destination", ("bukhara", "Bukhara"),
        ["lyabi-hauz", "lyabi hauz", "labi hovuz", "labi-hauz", "lyab-i hauz"]),
    9: ("kalta-minor", "khorezm", "landmark", ("khiva", "Khiva"), ["kalta minor", "kalta minar"]),
    10: ("itchan-kala", "khorezm", "destination", ("khiva", "Khiva"),
         ["itchan kala", "ichan kala", "ichan qala", "ichan qal'a", "ichon qal'a"]),
    11: ("khudayor-khan-palace", "fergana", "landmark", ("kokand", "Kokand"),
         ["khudayor khan", "khudayar khan", "khudoyar khan", "xudoyorxon"]),
    12: ("rishtan-ceramics", "fergana", "destination", ("fergana", "Fergana"), ["rishtan", "rishton"]),
    13: ("andijan-jami", "andijan", "landmark", ("andijan", "Andijan"),
         ["jami complex", "jome majmuasi", "andijan jami", "andijon jome"]),
    14: ("babur-park", "andijan", "destination", ("andijan", "Andijan"),
         ["babur memorial park", "babur park", "bobur bog'i", "bobur bogi", "bogishamol", "bog'ishamol"]),
    15: ("mulla-kyrgyz", "namangan", "landmark", ("namangan", "Namangan"),
         ["mulla kyrgyz", "mullah kyrgyz", "mulla qirg'iz", "mulla qirgiz"]),
    16: ("chartak", "namangan", "destination", ("namangan", "Namangan"), ["chartak", "chortoq"]),
    17: ("ak-saray", "kashkadarya", "landmark", ("samarkand", "Samarkand"),
         ["ak-saray", "ak saray", "aksaray", "oqsaroy"]),
    18: ("dorut-tilovat", "kashkadarya", "destination", ("samarkand", "Samarkand"),
         ["dorut tilovat", "dorut-tilovat", "kok gumbaz", "ko'k gumbaz"]),
    19: ("sultan-saodat", "surkhandarya", "landmark", ("termez", "Termez"), ["sultan saodat", "sulton saodat"]),
    20: ("boysun", "surkhandarya", "destination", ("termez", "Termez"), ["boysun", "baysun"]),
    21: ("jizzakh-station", "jizzakh", "landmark", ("jizzakh", "Jizzakh"),
         ["jizzakh railway station", "jizzakh station", "jizzax vokzal", "jizzax temiryo'l"]),
    22: ("zaamin", "jizzakh", "destination", ("jizzakh", "Jizzakh"), ["zaamin", "zomin"]),
    23: ("yogochli-sardoba", "syrdarya", "landmark", ("jizzakh", "Jizzakh"),
         ["yogochli sardoba", "yog'ochli sardoba", "sardoba"]),
    24: ("syr-darya-riverbank", "syrdarya", "destination", ("jizzakh", "Jizzakh"),
         ["syr darya riverbank", "sirdaryo bo'yi", "syr darya river"]),
    25: ("rabati-malik", "navoi", "landmark", ("navoi", "Navoi"), ["rabati malik", "raboti malik", "rabat-i malik"]),
    26: ("nurata-chashma", "navoi", "destination", ("navoi", "Navoi"), ["nurata", "nurota", "chashma"]),
    27: ("savitsky-museum", "karakalpakstan", "landmark", ("nukus", "Nukus"), ["savitsky", "savitskiy"]),
    28: ("moynaq-ships", "karakalpakstan", "destination", ("nukus", "Nukus"),
         ["moynaq", "muynak", "mo'ynoq", "moynoq", "ship graveyard", "aral sea"]),
}

HEADINGS = {
    "en": {"history": "History & significance", "see": "What to see", "tip": "Plan your visit"},
    "uz": {"history": "Tarix va ahamiyat", "see": "Nimalarni ko‘rish mumkin", "tip": "Tashrif uchun maslahat"},
}
IMAGE_LINE = re.compile(r"(?:Image file —|PNG:)\s*`(\d+)_(landmark|destination)-([a-z-]+)\.png`")
LINK = re.compile(r"^- \[([^\]]+)\]\((https://[^)\s]+)\)$")


def parse(lang: str, text: str) -> dict[int, dict]:
    cards: dict[int, dict] = {}
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = [ln.rstrip() for ln in block.splitlines()]
        image = next((IMAGE_LINE.search(ln) for ln in lines if IMAGE_LINE.search(ln)), None)
        if not image:
            continue
        n = int(image.group(1))
        title = re.sub(r"^\d+\s*·\s*", "", lines[0]).strip()
        parts = [p.strip() for p in lines[1].split("·")]
        body = "\n".join(lines)
        sections = {}
        for field, heading in HEADINGS[lang].items():
            m = re.search(rf"\*\*{re.escape(heading)}\.\*\*\s*(.+)", body)
            if not m:
                raise SystemExit(f"{lang} card {n}: missing '{heading}'")
            sections[field] = m.group(1).strip()
        sources = [{"label": m.group(1).removeprefix("www."), "url": m.group(2)} for ln in lines if (m := LINK.match(ln))]
        cards[n] = {
            "name": title,
            "area": " · ".join(parts[:-1]),
            "category": parts[-1],
            **sections,
            "sources": sources,
            "image_region": image.group(3),
            "image_kind": image.group(2),
        }
    return cards


def build() -> dict:
    parsed = {lang: parse(lang, path.read_text(encoding="utf-8")) for lang, path in SOURCES.items()}
    if set(parsed["en"]) != set(META) or set(parsed["uz"]) != set(META):
        raise SystemExit(f"Expected cards 1-28; got en={sorted(parsed['en'])} uz={sorted(parsed['uz'])}")
    places = []
    for n, (key, region, kind, (city_id, city_name), aliases) in sorted(META.items()):
        en, uz = parsed["en"][n], parsed["uz"][n]
        if (en["image_region"].replace("-city", ""), en["image_kind"]) != (region.replace("-city", ""), kind):
            raise SystemExit(f"card {n}: image {en['image_region']}/{en['image_kind']} vs META {region}/{kind}")
        places.append(
            {
                "n": n,
                "key": key,
                "region": region,
                "kind": kind,
                "image": f"/images/explore/{region}-{kind}.webp",
                "city_id": city_id,
                "city_name": city_name,
                "aliases": sorted({a.lower() for a in [*aliases, en["name"], uz["name"]]}),
                # Both packs cite the same pages; the English pack's list is used.
                "sources": en["sources"],
                "en": {k: en[k] for k in ("name", "area", "category", "history", "see", "tip")},
                "uz": {k: uz[k] for k in ("name", "area", "category", "history", "see", "tip")},
            }
        )
    regions = [
        {"key": k, "name": name, "name_uz": name_uz, "location_regions": loc_regions,
         "aliases": sorted({a.lower() for a in extra})}
        for k, name, name_uz, loc_regions, extra in REGIONS
    ]
    return {
        "about": "Generated by scripts/build_place_knowledge.py from content/place-cards. Do not edit by hand.",
        "image_note": "Pictures are artistic illustrations, not photos.",
        "regions": regions,
        "places": places,
    }


def main() -> None:
    data = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        stale = [str(p.relative_to(ROOT)) for p in OUTPUTS if not p.exists() or p.read_text(encoding="utf-8") != data]
        if stale:
            raise SystemExit(f"Out of date: {', '.join(stale)}. Run python scripts/build_place_knowledge.py")
        print("Place knowledge is up to date.")
        return
    for p in OUTPUTS:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding="utf-8")
        print(f"wrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
