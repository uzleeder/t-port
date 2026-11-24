import knowledge from "./explore-places.json";

/**
 * The 28 Explore places: a landmark and a destination for each of Uzbekistan's 14 regions.
 * Text is the place-card pack's own English copy (content/place-cards/en.md), with its sources;
 * T-AI answers from the same file. Pictures are the pack's artistic illustrations, shown whole.
 *
 * Each place links to journeys to the nearest city T-Port routes to (`cityId`), which is not
 * always the place's own town; the UI says so when they differ.
 */

export type ExploreKind = "landmark" | "destination";

export interface PlaceSource {
  label: string;
  url: string;
}

export interface ExplorePlace {
  key: string;
  regionKey: string;
  kind: ExploreKind;
  name: string;
  nameUz: string;
  /** Where it is, e.g. "Bukhara · Old City". */
  area: string;
  category: string;
  history: string;
  see: string;
  tip: string;
  sources: PlaceSource[];
  image: string;
  /** Journey search: nearest city T-Port routes to, and where from. */
  cityId: string;
  cityName: string;
  originId: string;
  originName: string;
}

/** Pictures are 803×675 (the pack's picture panel, uncropped). */
export const PLACE_IMAGE = { width: 803, height: 675 } as const;

/** Text, sources and nearest city come from the place-card pack via scripts/build_place_knowledge.py. */
export const EXPLORE_PLACES: ExplorePlace[] = knowledge.places.map((p) => {
  const fromSamarkand = p.city_id === "tashkent";
  return {
    key: p.key,
    regionKey: p.region,
    kind: p.kind as ExploreKind,
    name: p.en.name,
    nameUz: p.uz.name,
    area: p.en.area,
    category: p.en.category,
    history: p.en.history,
    see: p.en.see,
    tip: p.en.tip,
    sources: p.sources,
    image: p.image,
    cityId: p.city_id,
    cityName: p.city_name,
    originId: fromSamarkand ? "samarkand" : "tashkent",
    originName: fromSamarkand ? "Samarkand" : "Tashkent",
  };
});

export const EXPLORE_SECTIONS: { kind: ExploreKind; title: string }[] = [
  { kind: "destination", title: "Travel destinations" },
  { kind: "landmark", title: "Architectural landmarks" },
];

/** Journey search; the search page fills in tomorrow's date. */
export const placeSearchHref = (p: ExplorePlace) => `/search?origin=${p.originId}&destination=${p.cityId}`;
