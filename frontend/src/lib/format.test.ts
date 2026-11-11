import { describe, expect, it } from "vitest";
import {
  buildSearchQuery,
  dayOffset,
  formatDuration,
  formatMoney,
  formatPriceRange,
  localTime,
  marketToday,
  parseSearchParams,
  safeNextPath,
  timeAgo,
} from "./format";

describe("formatting", () => {
  it("formats money without inventing decimals", () => {
    expect(formatMoney("270000", "UZS")).toBe("270,000 UZS");
    expect(formatMoney("abc", "UZS")).toBe("—");
  });

  it("formats estimate ranges", () => {
    expect(formatPriceRange("400000", "600000", "UZS")).toBe("400,000–600,000 UZS");
    expect(formatPriceRange("400000", null, "UZS")).toBe("400,000 UZS");
  });

  it("formats durations", () => {
    expect(formatDuration(130)).toBe("2h 10m");
    expect(formatDuration(45)).toBe("45m");
    expect(formatDuration(-1)).toBe("—");
  });

  it("keeps local wall time and detects overnight arrivals", () => {
    expect(localTime("2026-11-12T20:30:00+05:00")).toBe("20:30");
    expect(localTime(null)).toBe("Flexible");
    expect(dayOffset("2026-11-12T20:30:00+05:00", "2026-11-13T06:30:00+05:00")).toBe(1);
    expect(dayOffset("2026-11-12T08:00:00+05:00", "2026-11-12T10:10:00+05:00")).toBe(0);
  });

  it("computes the market date in Tashkent time", () => {
    // 20:00 UTC on 11 Nov is already 01:00 on 12 Nov in Tashkent.
    const now = new Date("2026-11-11T20:00:00Z");
    expect(marketToday(now)).toBe("2026-11-12");
    expect(marketToday(now, 1)).toBe("2026-11-13");
  });
});

describe("search params", () => {
  const now = new Date("2026-11-11T05:00:00Z");

  it("parses and normalises a full query", () => {
    expect(
      parseSearchParams(
        { origin: "Tashkent", destination: "samarkand", date: "2026-11-20", modes: "bus,train,zeppelin", sort: "price", page: "2" },
        now,
      ),
    ).toMatchObject({
      origin: "tashkent",
      destination: "samarkand",
      date: "2026-11-20",
      modes: ["bus", "train"],
      sort: "price",
      page: 2,
    });
  });

  it("defaults the date to tomorrow and rejects bad input", () => {
    expect(parseSearchParams({ origin: "a", destination: "b" }, now)?.date).toBe("2026-11-12");
    expect(parseSearchParams({ origin: "a", destination: "b", date: "today" }, now)?.date).toBe("2026-11-11");
    expect(parseSearchParams({ origin: "a", destination: "b", date: "12/11/2026" }, now)).toBeNull();
    expect(parseSearchParams({ origin: "a" }, now)).toBeNull();
    const filtered = parseSearchParams(
      { origin: "a", destination: "b", max_transfers: "2", arrive_before: "18:00", max_price: "400000", prefer_modes: "bus,rocket" },
      now,
    );
    expect(filtered).toMatchObject({ maxTransfers: 2, arriveBefore: "18:00", maxPrice: "400000", preferModes: ["bus"] });
    const junk = parseSearchParams({ origin: "a", destination: "b", max_transfers: "9", arrive_before: "25:00", max_price: "-5" }, now);
    expect(junk).toMatchObject({ maxTransfers: 1, arriveBefore: null, maxPrice: null });
    expect(parseSearchParams({ origin: "a", destination: "b", sort: "evil" }, now)?.sort).toBe(
      "recommended",
    );
  });

  it("builds a canonical query string", () => {
    expect(
      buildSearchQuery({ origin: "tashkent", destination: "bukhara", date: "2026-11-12", modes: ["train", "bus"], sort: "price" }),
    ).toBe("origin=tashkent&destination=bukhara&date=2026-11-12&modes=bus%2Ctrain&sort=price");
    // All modes selected == no filter; recommended sort and page 1 are omitted.
    expect(
      buildSearchQuery({ origin: "a", destination: "b", date: "2026-11-12", modes: ["train", "bus", "flight", "taxi"], sort: "recommended", page: 1 }),
    ).toBe("origin=a&destination=b&date=2026-11-12");
    expect(
      buildSearchQuery({ origin: "a", destination: "b", date: "2026-11-12", maxTransfers: 0, arriveBefore: "18:00", maxPrice: "400000" }),
    ).toBe("origin=a&destination=b&date=2026-11-12&max_transfers=0&arrive_before=18%3A00&max_price=400000");
  });
});

describe("safeNextPath", () => {
  it("allows only same-site relative paths", () => {
    expect(safeNextPath("/journeys/demo~TR101.20261112")).toBe("/journeys/demo~TR101.20261112");
    for (const bad of ["https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)", "", null, "/a\nb"]) {
      expect(safeNextPath(bad)).toBeNull();
    }
  });
});

describe("timeAgo", () => {
  const now = Date.parse("2026-11-11T10:00:00Z");
  it("formats ages and stays empty without a reference time", () => {
    expect(timeAgo("2026-11-11T09:59:40Z", now)).toBe("just now");
    expect(timeAgo("2026-11-11T09:45:00Z", now)).toBe("15 min ago");
    expect(timeAgo("2026-11-11T07:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo("2026-11-08T10:00:00Z", now)).toBe("3 days ago");
    expect(timeAgo("2026-11-11T09:45:00Z", undefined)).toBeNull();
    expect(timeAgo(null, now)).toBeNull();
  });
});
