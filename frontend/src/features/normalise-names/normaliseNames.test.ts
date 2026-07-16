// Tests for the name-normalisation pure logic (Session 96 — Graph-quality S6b).

import { describe, expect, it } from "vitest";

import { ApiError } from "../../lib/api/client";
import type { LabelSynonymView, LabelVocabularyResponse } from "../../lib/api/useLabelVocabulary";
import {
  armRename,
  armedRenameHint,
  flattenVocabulary,
  pairKey,
  reduceNormaliseKey,
  renameSummaryMessage,
  scoreLabels,
  vocabularyErrorMessage,
  type LabelPairItem,
} from "./normaliseNames";

function synonym(overrides: Partial<LabelSynonymView> = {}): LabelSynonymView {
  return {
    label_lo: "LOCATED_AT",
    label_hi: "LOCATED_IN",
    count_lo: 3,
    count_hi: 12,
    name_score: 91,
    cosine_score: 0.88,
    combined_score: 0.9,
    ...overrides,
  };
}

function vocabulary(overrides: Partial<LabelVocabularyResponse> = {}): LabelVocabularyResponse {
  return {
    predicate_suggestions: [synonym(), synonym({ label_lo: "PART_OF", label_hi: "MEMBER_OF" })],
    type_suggestions: [synonym({ label_lo: "Place", label_hi: "Location" })],
    ...overrides,
  };
}

function predicateItem(overrides: Partial<LabelSynonymView> = {}): LabelPairItem {
  return { surface: "predicate", pair: synonym(overrides) };
}

describe("flattenVocabulary", () => {
  it("concatenates predicates first, then types, tagging each with its surface", () => {
    const items = flattenVocabulary(vocabulary());
    expect(items.map((i) => i.surface)).toEqual(["predicate", "predicate", "type"]);
    expect(items[0]?.pair.label_hi).toBe("LOCATED_IN");
    expect(items[2]?.pair.label_hi).toBe("Location");
  });

  it("is empty when both vocabularies are empty", () => {
    expect(flattenVocabulary({ predicate_suggestions: [], type_suggestions: [] })).toEqual([]);
  });
});

describe("pairKey", () => {
  it("is order-independent within a surface", () => {
    expect(pairKey("predicate", "A", "B")).toBe(pairKey("predicate", "B", "A"));
  });

  it("distinguishes identically-named pairs across surfaces", () => {
    expect(pairKey("predicate", "A", "B")).not.toBe(pairKey("type", "A", "B"));
  });
});

describe("scoreLabels", () => {
  it("labels name + embedding scores honestly", () => {
    expect(scoreLabels(synonym())).toEqual({
      nameLabel: "name match 91",
      similarityLabel: "embedding 0.88",
    });
  });

  it("renders a name-only pair when the cosine score is null", () => {
    expect(scoreLabels(synonym({ cosine_score: null })).similarityLabel).toBe("name-only");
  });

  it("rounds a fractional name score", () => {
    expect(scoreLabels(synonym({ name_score: 90.6 })).nameLabel).toBe("name match 91");
  });
});

describe("armRename", () => {
  it("keeps the chosen label and folds the other into it, with its count", () => {
    // Keep LOCATED_IN (label_hi, count 12) → fold LOCATED_AT (label_lo, count 3).
    expect(armRename(predicateItem(), "LOCATED_IN")).toEqual({
      surface: "predicate",
      fromLabel: "LOCATED_AT",
      toLabel: "LOCATED_IN",
      fromCount: 3,
    });
    // Keep LOCATED_AT (label_lo, count 3) → fold LOCATED_IN (label_hi, count 12).
    expect(armRename(predicateItem(), "LOCATED_AT")).toEqual({
      surface: "predicate",
      fromLabel: "LOCATED_IN",
      toLabel: "LOCATED_AT",
      fromCount: 12,
    });
  });

  it("passes the stored from_label through VERBATIM (no trim/normalise — S95 guard)", () => {
    // A label with surrounding whitespace must reach the request untouched: the backend matches
    // the stored label exactly, so a client-side strip would rename nothing.
    const item = predicateItem({ label_lo: "  spaced  ", label_hi: "CLEAN" });
    expect(armRename(item, "CLEAN").fromLabel).toBe("  spaced  ");
  });

  it("carries the type surface through", () => {
    const item: LabelPairItem = {
      surface: "type",
      pair: synonym({ label_lo: "Place", label_hi: "Location" }),
    };
    expect(armRename(item, "Location").surface).toBe("type");
  });
});

describe("armedRenameHint", () => {
  it("describes a predicate rename in edges and defers the commit", () => {
    const armed = armRename(predicateItem(), "LOCATED_IN");
    expect(armedRenameHint(armed)).toBe(
      "Rename 3 edges from “LOCATED_AT” to “LOCATED_IN”. Nothing happens until you press Rename.",
    );
  });

  it("describes a type rename in entities and singularises a count of one", () => {
    const item: LabelPairItem = {
      surface: "type",
      pair: synonym({ label_lo: "Place", label_hi: "Location", count_lo: 1, count_hi: 9 }),
    };
    expect(armedRenameHint(armRename(item, "Location"))).toBe(
      "Rename 1 entity from “Place” to “Location”. Nothing happens until you press Rename.",
    );
  });
});

describe("renameSummaryMessage", () => {
  it("reports a predicate rename with its folded count", () => {
    expect(
      renameSummaryMessage(
        { surface: "predicate", renamed_count: 3, folded_count: 1 },
        "LOCATED_AT",
        "LOCATED_IN",
      ),
    ).toBe("Renamed 3 edges from “LOCATED_AT” to “LOCATED_IN”, folding 1 duplicate edge.");
  });

  it("omits the folded clause when nothing folded (types never fold)", () => {
    expect(
      renameSummaryMessage(
        { surface: "type", renamed_count: 4, folded_count: 0 },
        "Place",
        "Location",
      ),
    ).toBe("Renamed 4 entities from “Place” to “Location”.");
  });
});

describe("vocabularyErrorMessage", () => {
  it("maps the routes' declared statuses and falls back safely", () => {
    expect(vocabularyErrorMessage(new ApiError(404, "story not found", null))).toBe(
      "This story no longer exists.",
    );
    expect(vocabularyErrorMessage(new ApiError(503, "a data store is unavailable", null))).toBe(
      "The label-vocabulary data is temporarily unavailable — try again shortly.",
    );
    // A never-declared status falls through to the detail.
    expect(vocabularyErrorMessage(new ApiError(400, "bad", null))).toBe("bad");
  });

  it("gives a non-empty message for a thrown (non-ApiError) fetch failure", () => {
    expect(vocabularyErrorMessage(new TypeError("Failed to fetch"))).toBe("Please try again.");
    expect(vocabularyErrorMessage(undefined)).toBe("Please try again.");
  });
});

describe("reduceNormaliseKey", () => {
  const list = [predicateItem(), predicateItem(), predicateItem()];

  it("advances and retreats the cursor, clamped to the list", () => {
    expect(reduceNormaliseKey("j", { selectedIndex: 0 }, list)?.state.selectedIndex).toBe(1);
    expect(reduceNormaliseKey("ArrowDown", { selectedIndex: 2 }, list)?.state.selectedIndex).toBe(
      2,
    );
    expect(reduceNormaliseKey("k", { selectedIndex: 0 }, list)?.state.selectedIndex).toBe(0);
    expect(reduceNormaliseKey("ArrowUp", { selectedIndex: 2 }, list)?.state.selectedIndex).toBe(1);
  });

  it("emits a dismiss intent on D without moving the cursor", () => {
    expect(reduceNormaliseKey("d", { selectedIndex: 1 }, list)).toEqual({
      state: { selectedIndex: 1 },
      intent: "dismiss",
    });
  });

  it("ignores keys outside the scheme", () => {
    expect(reduceNormaliseKey("x", { selectedIndex: 0 }, list)).toBeNull();
  });
});
