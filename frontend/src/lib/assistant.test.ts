import { describe, expect, it } from "vitest";
import { understoodAs, type InterpretResponse } from "./assistant";

const base: InterpretResponse["intent"] = {
  origin_id: "samarkand",
  destination_id: "khiva",
  travel_date: "2026-11-12",
  modes: [],
  budget_preference: "any",
  max_price: null,
  time_preference: "any",
  sort: "recommended",
  depart_after: null,
  depart_before: null,
  arrive_before: null,
  max_transfers: 1,
  transfer_preference: "any",
  prefer_modes: [],
  compare_modes: false,
};

describe("understoodAs", () => {
  it("is empty for a plain request", () => {
    expect(understoodAs(base)).toEqual([]);
  });

  it("lists validated constraints only", () => {
    expect(
      understoodAs({
        ...base,
        modes: ["train", "bus"],
        arrive_before: "18:00",
        max_transfers: 2,
        transfer_preference: "fewest",
        max_price: "400000",
        compare_modes: true,
      }),
    ).toEqual(["train or bus", "arrive by 18:00", "fewest changes", "max 400,000 UZS", "compare modes"]);
    expect(understoodAs({ ...base, max_transfers: 0, prefer_modes: ["train"] })).toEqual([
      "prefer train",
      "direct only",
    ]);
  });
});
