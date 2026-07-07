// Tests for the duplicate-review pure logic (Session 79 — Graph-quality S4b).

import { describe, expect, it } from "vitest";

import type { DuplicateSuggestionView } from "../../lib/api/useDuplicateSuggestions";
import {
  markMentions,
  mergeVarsFor,
  pairKey,
  reduceDuplicateKey,
  scoreLabels,
} from "./duplicateReview";

function suggestion(overrides: Partial<DuplicateSuggestionView> = {}): DuplicateSuggestionView {
  return {
    entity_a: {
      entity_id: "a-id",
      canonical_name: "Elara",
      type: "Person",
      aliases: [],
      context_quote: "Elara stepped forward.",
    },
    entity_b: {
      entity_id: "b-id",
      canonical_name: "Elira",
      type: "Person",
      aliases: ["El"],
      context_quote: null,
    },
    name_score: 88,
    cosine_score: 0.912,
    combined_score: 0.9,
    ...overrides,
  };
}

describe("pairKey", () => {
  it("is order-independent", () => {
    expect(pairKey("a-id", "b-id")).toBe(pairKey("b-id", "a-id"));
  });

  it("distinguishes different pairs", () => {
    expect(pairKey("a-id", "b-id")).not.toBe(pairKey("a-id", "c-id"));
  });
});

describe("scoreLabels", () => {
  it("labels name + embedding scores honestly", () => {
    expect(scoreLabels(suggestion())).toEqual({
      nameLabel: "name match 88",
      similarityLabel: "embedding 0.91",
    });
  });

  it("renders a name-only suggestion when the cosine score is null", () => {
    expect(scoreLabels(suggestion({ cosine_score: null })).similarityLabel).toBe("name-only");
  });

  it("rounds a fractional name score", () => {
    expect(scoreLabels(suggestion({ name_score: 87.6 })).nameLabel).toBe("name match 88");
  });
});

describe("mergeVarsFor", () => {
  it("keeps side A as survivor, absorbs B", () => {
    expect(mergeVarsFor("a", suggestion())).toEqual({
      targetEntityId: "a-id",
      absorbedId: "b-id",
    });
  });

  it("keeps side B as survivor, absorbs A", () => {
    expect(mergeVarsFor("b", suggestion())).toEqual({
      targetEntityId: "b-id",
      absorbedId: "a-id",
    });
  });
});

describe("markMentions", () => {
  it("marks a name occurrence, case-insensitively, leaving the rest unmarked", () => {
    expect(markMentions("The crew roared.", ["crew"])).toEqual([
      { text: "The ", match: false },
      { text: "crew", match: true },
      { text: " roared.", match: false },
    ]);
    // Case-insensitive: a lowercased mention of a capitalised name still marks.
    expect(markMentions("then Crew and crew", ["Crew"])).toEqual([
      { text: "then ", match: false },
      { text: "Crew", match: true },
      { text: " and ", match: false },
      { text: "crew", match: true },
    ]);
  });

  it("prefers the longest term so a multi-word alias wins over its substring", () => {
    expect(markMentions("the merchant crew sailed", ["crew", "merchant crew"])).toEqual([
      { text: "the ", match: false },
      { text: "merchant crew", match: true },
      { text: " sailed", match: false },
    ]);
  });

  it("returns the whole quote unmarked when no term matches or the term list is empty", () => {
    expect(markMentions("nothing here", ["absent"])).toEqual([
      { text: "nothing here", match: false },
    ]);
    expect(markMentions("nothing here", [" ", ""])).toEqual([
      { text: "nothing here", match: false },
    ]);
  });

  it("treats regex-special characters in a name literally", () => {
    expect(markMentions("Dr. (A.) speaks", ["(A.)"])).toEqual([
      { text: "Dr. ", match: false },
      { text: "(A.)", match: true },
      { text: " speaks", match: false },
    ]);
  });
});

describe("reduceDuplicateKey", () => {
  const list = [suggestion(), suggestion(), suggestion()];

  it("advances and retreats the cursor, clamped to the list", () => {
    expect(reduceDuplicateKey("j", { selectedIndex: 0 }, list)?.state.selectedIndex).toBe(1);
    expect(reduceDuplicateKey("ArrowDown", { selectedIndex: 2 }, list)?.state.selectedIndex).toBe(
      2,
    );
    expect(reduceDuplicateKey("k", { selectedIndex: 0 }, list)?.state.selectedIndex).toBe(0);
    expect(reduceDuplicateKey("ArrowUp", { selectedIndex: 2 }, list)?.state.selectedIndex).toBe(1);
  });

  it("emits a dismiss intent on D without moving the cursor", () => {
    const result = reduceDuplicateKey("d", { selectedIndex: 1 }, list);
    expect(result).toEqual({ state: { selectedIndex: 1 }, intent: "dismiss" });
  });

  it("ignores keys outside the scheme", () => {
    expect(reduceDuplicateKey("x", { selectedIndex: 0 }, list)).toBeNull();
  });
});
