import { describe, expect, it } from "vitest";
import { compareHref, MAX_COMPARE, nextSelection } from "./compare-store";

describe("compare selection", () => {
  it("toggles and caps the selection", () => {
    expect(nextSelection([], "a")).toEqual(["a"]);
    expect(nextSelection(["a", "b"], "a")).toEqual(["b"]);
    const full = ["a", "b", "c", "d"];
    expect(MAX_COMPARE).toBe(4);
    expect(nextSelection(full, "e")).toBe(full); // refused, unchanged
    expect(nextSelection(full, "c")).toEqual(["a", "b", "d"]);
  });

  it("encodes multi-leg IDs so '+' survives the query string", () => {
    expect(compareHref(["x~demo:1+demo:2", "demo:3"])).toBe("/compare?ids=x~demo%3A1%2Bdemo%3A2,demo%3A3");
  });
});
