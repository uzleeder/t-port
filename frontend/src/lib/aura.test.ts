import { describe, expect, it } from "vitest";
import { AURA_REGIONS, auraRegionUrl } from "./aura";

// Every region name the backend's locations use (backend/app/data/reference.py + administrative.py).
const T_PORT_REGIONS = [
  "Andijan Region", "Andijon viloyati", "Bukhara Region", "Buxoro viloyati", "Fargʻona viloyati",
  "Fergana Region", "Jizzakh Region", "Jizzax viloyati", "Kashkadarya Region", "Khorezm Region",
  "Namangan Region", "Namangan shahri", "Namangan viloyati", "Navoiy Region", "Navoiy viloyati",
  "Qashqadaryo viloyati", "Qoraqalpogʻiston Respublikasi", "Republic of Karakalpakstan",
  "Samarkand Region", "Samarqand viloyati", "Sirdaryo viloyati", "Surkhandarya Region",
  "Surxondaryo viloyati", "Tashkent City", "Toshkent shahri", "Toshkent viloyati", "Xorazm viloyati",
];

describe("auraRegionUrl", () => {
  it("links every T-Port region to an AURA region gallery", () => {
    for (const r of T_PORT_REGIONS) expect(auraRegionUrl(r), r).toMatch(/^https:\/\/aura\.uz\/content\?region=\d+$/);
  });

  it("uses the same AURA region for English and Uzbek names", () => {
    expect(auraRegionUrl("Bukhara Region")).toBe("https://aura.uz/content?region=2");
    expect(auraRegionUrl("Buxoro viloyati")).toBe("https://aura.uz/content?region=2");
    expect(auraRegionUrl("Tashkent City")).toBe("https://aura.uz/content?region=10");
    expect(auraRegionUrl("Toshkent viloyati")).toBe("https://aura.uz/content?region=11");
  });

  it("returns null for places outside Uzbekistan's regions", () => {
    expect(auraRegionUrl("Almaty Region")).toBeNull();
  });

  it("lists each AURA region once", () => {
    expect(new Set(AURA_REGIONS.map((r) => r.href)).size).toBe(AURA_REGIONS.length);
    expect(AURA_REGIONS).toHaveLength(14);
  });
});

describe("explore", () => {
  it("has 14 regions, each with an AURA link and exactly one landmark and one destination", async () => {
    const { UZ_REGIONS, regionPlaces } = await import("./regions");
    expect(UZ_REGIONS).toHaveLength(14);
    const aura = UZ_REGIONS.map((r) => auraRegionUrl(r.region));
    expect(aura.every(Boolean)).toBe(true);
    expect(new Set(aura).size).toBe(14);
    for (const r of UZ_REGIONS) {
      expect(regionPlaces(r.key).map((p) => p.kind).sort(), r.key).toEqual(["destination", "landmark"]);
    }
  });

  it("has 28 places with unique keys, an image file, sources and a valid journey search", async () => {
    const { EXPLORE_PLACES } = await import("./explore");
    const { existsSync } = await import("node:fs");
    expect(EXPLORE_PLACES).toHaveLength(28);
    expect(new Set(EXPLORE_PLACES.map((p) => p.key)).size).toBe(28);
    expect(new Set(EXPLORE_PLACES.map((p) => p.image)).size).toBe(28);
    for (const p of EXPLORE_PLACES) {
      expect(existsSync(`public${p.image}`), p.image).toBe(true);
      expect(p.sources.length, p.key).toBeGreaterThan(0);
      for (const s of p.sources) expect(s.url, p.key).toMatch(/^https:\/\//);
      expect(p.originId, p.key).not.toBe(p.cityId);
      for (const t of [p.history, p.see, p.tip]) expect(t.length, p.key).toBeGreaterThan(20);
    }
  });
});
