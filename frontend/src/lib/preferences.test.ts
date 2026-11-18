import { describe, expect, it } from "vitest";
import { buildSearchQuery } from "./format";
import { DEFAULT_PREFERENCES, searchDefaults } from "./preferences";

describe("searchDefaults", () => {
  it("adds nothing when signed out or on built-in defaults", () => {
    expect(searchDefaults(null)).toEqual({});
    const qs = buildSearchQuery({ ...searchDefaults(DEFAULT_PREFERENCES), origin: "a", destination: "b", date: "2026-11-12" });
    expect(qs).toBe("origin=a&destination=b&date=2026-11-12");
  });

  it("starts new searches from saved preferences", () => {
    const qs = buildSearchQuery({
      ...searchDefaults({ ...DEFAULT_PREFERENCES, sort: "price", max_transfers: 2, prefer_modes: ["train"], max_price: "450000.00" }),
      origin: "a",
      destination: "b",
      date: "2026-11-12",
    });
    expect(qs).toBe("origin=a&destination=b&date=2026-11-12&sort=price&max_transfers=2&max_price=450000&prefer_modes=train");
  });
});
