// Pins the optimistic cache edits the rename/dismiss hooks apply before their refetch lands
// (Session 100). The suggest pass is a whole-vocabulary recompute — ~1.7 s even with the
// backend's embedding cache — so without these the queue visibly stalls after every decision.
// The refetch is still authoritative; these only decide what the author sees in the meantime,
// so the rules must match what the server will return or the list would flicker back.

import { describe, expect, it } from "vitest";

import { dropPairsInvolving, dropPair } from "./labelVocabularyCache";
import type { LabelSynonymView, LabelVocabularyResponse } from "./useLabelVocabulary";

function pair(lo: string, hi: string): LabelSynonymView {
  return {
    label_lo: lo,
    label_hi: hi,
    count_lo: 1,
    count_hi: 2,
    name_score: 90,
    cosine_score: 0.9,
    combined_score: 0.9,
  };
}

const DATA: LabelVocabularyResponse = {
  predicate_suggestions: [
    pair("STANDS_ON", "STAND_ON"),
    pair("STANDS_ON", "STOOD_ON"),
    pair("HUNTS", "CHASES"),
  ],
  type_suggestions: [pair("PERSON", "Person")],
};

describe("dropPairsInvolving (a rename removes the label entirely)", () => {
  it("drops every pair naming the renamed-away label, on that surface only", () => {
    const next = dropPairsInvolving(DATA, "predicate", "STANDS_ON");

    expect(next?.predicate_suggestions).toEqual([pair("HUNTS", "CHASES")]);
    // The other surface is untouched — a predicate is never a synonym of a type (DM-NN-1).
    expect(next?.type_suggestions).toEqual(DATA.type_suggestions);
  });

  it("matches the label in either position of the unordered pair", () => {
    const next = dropPairsInvolving(DATA, "predicate", "CHASES");
    expect(next?.predicate_suggestions.map((s) => s.label_hi)).toEqual(["STAND_ON", "STOOD_ON"]);
  });

  it("leaves the other surface's identical label alone", () => {
    // "PERSON" exists as a type; renaming a *predicate* of that name must not touch it.
    const next = dropPairsInvolving(DATA, "predicate", "PERSON");
    expect(next?.type_suggestions).toEqual(DATA.type_suggestions);
    expect(next?.predicate_suggestions).toEqual(DATA.predicate_suggestions);
  });

  it("returns undefined when there is no cached list to edit", () => {
    expect(dropPairsInvolving(undefined, "predicate", "STANDS_ON")).toBeUndefined();
  });
});

describe("dropPair (a dismissal removes one pair, both labels survive)", () => {
  it("drops only the dismissed pair, leaving the labels' other pairs", () => {
    const next = dropPair(DATA, "predicate", "STANDS_ON", "STAND_ON");

    // STANDS_ON still pairs with STOOD_ON — dismissing one pair says nothing about the other.
    expect(next?.predicate_suggestions).toEqual([
      pair("STANDS_ON", "STOOD_ON"),
      pair("HUNTS", "CHASES"),
    ]);
  });

  it("is order-insensitive — the pair is unordered", () => {
    const next = dropPair(DATA, "predicate", "STAND_ON", "STANDS_ON");
    expect(next?.predicate_suggestions).toHaveLength(2);
  });

  it("is a no-op when the pair is not in the list", () => {
    const next = dropPair(DATA, "predicate", "HUNTS", "STANDS_ON");
    expect(next?.predicate_suggestions).toEqual(DATA.predicate_suggestions);
  });

  it("targets the named surface", () => {
    const next = dropPair(DATA, "type", "PERSON", "Person");
    expect(next?.type_suggestions).toEqual([]);
    expect(next?.predicate_suggestions).toEqual(DATA.predicate_suggestions);
  });
});
