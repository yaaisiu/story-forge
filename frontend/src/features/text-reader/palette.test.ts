import { describe, expect, it } from "vitest";

import { colorForType, legendEntries } from "./palette";

// DM-IH-5: a small fixed palette for the common entity types + a deterministic
// hash fallback for the open-world long tail (INV-4 — `type` is a free string, not
// an enum, so a hand-built map can never be exhaustive and must never throw on a
// never-before-seen type). Colours are reader-local by the owner's call (Session 33);
// the graph viewer keeps its own pure-hash colouring.

describe("colorForType", () => {
  it("gives the common types stable, distinct fixed colours", () => {
    const common = ["character", "place", "object", "concept"].map(colorForType);
    expect(new Set(common).size).toBe(common.length); // all distinct
    common.forEach((c) => expect(c).toMatch(/^#[0-9a-f]{6}$/i));
  });

  it("is case-insensitive (so 'Character' and 'character' match)", () => {
    expect(colorForType("Character")).toBe(colorForType("character"));
    expect(colorForType("PLACE")).toBe(colorForType("place"));
  });

  it("falls back to a deterministic colour for an unknown (open-world) type", () => {
    expect(colorForType("dragon")).toBe(colorForType("dragon")); // stable
    expect(colorForType("Dragon")).toBe(colorForType("dragon")); // normalised
    expect(colorForType("dragon")).toMatch(/^#[0-9a-f]{6}$/i);
  });

  it("never throws and always returns a colour, even for an empty type", () => {
    expect(colorForType("")).toMatch(/^#[0-9a-f]{6}$/i);
  });
});

describe("legendEntries", () => {
  it("returns one entry per distinct type with its colour", () => {
    expect(legendEntries(["character", "place", "character"])).toEqual([
      { type: "character", color: colorForType("character") },
      { type: "place", color: colorForType("place") },
    ]);
  });

  it("dedupes case-insensitively, preserving the first-seen label", () => {
    expect(legendEntries(["Character", "character"])).toEqual([
      { type: "Character", color: colorForType("Character") },
    ]);
  });

  it("skips empty / whitespace-only types", () => {
    expect(legendEntries(["", "  ", "place"])).toEqual([
      { type: "place", color: colorForType("place") },
    ]);
  });
});
