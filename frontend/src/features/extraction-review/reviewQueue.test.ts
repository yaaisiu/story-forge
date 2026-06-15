// Tests for the review-queue keyboard logic (Session 25 — M3.S4b Stage 4).
//
// The §8.3 keyboard scheme lives here as a pure reducer so the queue component stays
// render-and-dispatch (frontend/src/CLAUDE.md): J/K navigate, A accepts the cascade
// proposal, N forces create, R rejects, M cycles a merge target through the candidate's
// top-3 alternatives, Enter commits the picked merge (or the proposal if none picked).

import { describe, expect, it } from "vitest";

import { alternativesOf, reduceReviewKey, type NavState } from "./reviewQueue";
import type { CandidateView } from "../../lib/api/useCandidates";

function candidate(over: Partial<CandidateView> = {}): CandidateView {
  return {
    id: "c1",
    paragraph_id: "p1",
    candidate_name: "Janek",
    type: "Character",
    context: "Janek entered the mill...",
    proposal: "merge",
    target_entity_id: "e1",
    stage_reached: 3,
    confidence: 0.9,
    reasoning: "diminutive of Jan",
    alternatives: [
      { entity_id: "e1", canonical_name: "Jan", score: 91 },
      { entity_id: "e2", canonical_name: "Janusz", score: 70 },
    ],
    ...over,
  };
}

const TWO = [candidate({ id: "c1" }), candidate({ id: "c2" })];
const START: NavState = { selectedIndex: 0, mergeTargetIndex: null };

describe("reduceReviewKey — navigation", () => {
  it("J / ArrowDown advance the selection, clamped at the end", () => {
    expect(reduceReviewKey("j", START, TWO)?.state.selectedIndex).toBe(1);
    expect(reduceReviewKey("ArrowDown", START, TWO)?.state.selectedIndex).toBe(1);
    // already last → stays
    expect(
      reduceReviewKey("j", { selectedIndex: 1, mergeTargetIndex: null }, TWO)?.state.selectedIndex,
    ).toBe(1);
  });

  it("K / ArrowUp retreat the selection, clamped at the start", () => {
    const at1: NavState = { selectedIndex: 1, mergeTargetIndex: null };
    expect(reduceReviewKey("k", at1, TWO)?.state.selectedIndex).toBe(0);
    expect(reduceReviewKey("ArrowUp", START, TWO)?.state.selectedIndex).toBe(0);
  });

  it("navigation clears any in-progress merge-target pick", () => {
    const picking: NavState = { selectedIndex: 0, mergeTargetIndex: 1 };
    expect(reduceReviewKey("j", picking, TWO)?.state.mergeTargetIndex).toBeNull();
  });

  it("returns null for an unhandled key", () => {
    expect(reduceReviewKey("x", START, TWO)).toBeNull();
  });
});

describe("reduceReviewKey — single-key commits", () => {
  it("A commits the cascade proposal (no override body)", () => {
    const r = reduceReviewKey("a", START, TWO);
    expect(r?.intent).toEqual({ decision: "accept" });
  });

  it("N forces accept-as-create", () => {
    const r = reduceReviewKey("n", START, TWO);
    expect(r?.intent).toEqual({ decision: "accept", accept: { action: "create" } });
  });

  it("R rejects", () => {
    const r = reduceReviewKey("r", START, TWO);
    expect(r?.intent).toEqual({ decision: "reject" });
  });

  it("a commit resets any merge pick in the returned state", () => {
    const picking: NavState = { selectedIndex: 0, mergeTargetIndex: 1 };
    expect(reduceReviewKey("a", picking, TWO)?.state.mergeTargetIndex).toBeNull();
  });
});

describe("reduceReviewKey — merge picker", () => {
  it("M cycles a target through the alternatives (null → 0 → 1 → wrap to 0), no commit yet", () => {
    let r = reduceReviewKey("m", START, TWO);
    expect(r?.state.mergeTargetIndex).toBe(0);
    expect(r?.intent).toBeUndefined();
    r = reduceReviewKey("m", r!.state, TWO);
    expect(r?.state.mergeTargetIndex).toBe(1);
    r = reduceReviewKey("m", r!.state, TWO); // wraps (only 2 alternatives)
    expect(r?.state.mergeTargetIndex).toBe(0);
  });

  it("M on a candidate with no alternatives is a no-op (no pick, no commit)", () => {
    const noAlts = [candidate({ id: "c1", alternatives: [] })];
    const r = reduceReviewKey("m", START, noAlts);
    expect(r?.state.mergeTargetIndex).toBeNull();
    expect(r?.intent).toBeUndefined();
  });

  it("Enter with a picked target commits accept-as-merge to that entity", () => {
    const picking: NavState = { selectedIndex: 0, mergeTargetIndex: 1 };
    const r = reduceReviewKey("Enter", picking, TWO);
    expect(r?.intent).toEqual({
      decision: "accept",
      accept: { action: "merge", target_entity_id: "e2" },
    });
    expect(r?.state.mergeTargetIndex).toBeNull();
  });

  it("Enter with no pick commits the cascade proposal", () => {
    const r = reduceReviewKey("Enter", START, TWO);
    expect(r?.intent).toEqual({ decision: "accept" });
  });
});

describe("alternativesOf", () => {
  it("coerces the untyped alternatives array into typed entries", () => {
    const alts = alternativesOf(candidate());
    expect(alts).toEqual([
      { entity_id: "e1", canonical_name: "Jan", score: 91 },
      { entity_id: "e2", canonical_name: "Janusz", score: 70 },
    ]);
  });

  it("is empty for a candidate with no alternatives", () => {
    expect(alternativesOf(candidate({ alternatives: [] }))).toEqual([]);
  });
});
