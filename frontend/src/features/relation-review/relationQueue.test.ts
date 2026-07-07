// Tests for the relation-review keyboard logic (Session 30 — M3.S4f, spec §3.3's
// 5th human action "decide on relations" / §8.3).
//
// The keyboard scheme lives here as a pure reducer so the queue component stays
// render-and-dispatch (frontend/src/CLAUDE.md). A subset of the §8.3 scheme, firmed
// with the owner (S30): J/K (or ↓/↑) navigate; A commits the edge; R rejects the
// relation. There is no merge-target cycling — a relation has two fixed endpoints.

import { describe, expect, it } from "vitest";

import { reduceRelationKey, type NavState } from "./relationQueue";
import type { RelationView } from "../../lib/api/useRelations";

function relation(over: Partial<RelationView> = {}): RelationView {
  return {
    id: "r1",
    paragraph_id: "p1",
    subject: "Janek",
    predicate: "works_at",
    object: "the mill",
    confidence: 0.9,
    subject_entity_id: "e1",
    object_entity_id: "e2",
    ...over,
  };
}

const TWO = [relation({ id: "r1" }), relation({ id: "r2" })];
const START: NavState = { selectedIndex: 0 };

describe("reduceRelationKey — navigation", () => {
  it("J / ArrowDown advance the selection, clamped at the end", () => {
    expect(reduceRelationKey("j", START, TWO)?.state.selectedIndex).toBe(1);
    expect(reduceRelationKey("ArrowDown", START, TWO)?.state.selectedIndex).toBe(1);
    // already last → stays
    expect(reduceRelationKey("j", { selectedIndex: 1 }, TWO)?.state.selectedIndex).toBe(1);
  });

  it("K / ArrowUp retreat the selection, clamped at the start", () => {
    expect(reduceRelationKey("k", { selectedIndex: 1 }, TWO)?.state.selectedIndex).toBe(0);
    expect(reduceRelationKey("ArrowUp", { selectedIndex: 1 }, TWO)?.state.selectedIndex).toBe(0);
    // already first → stays
    expect(reduceRelationKey("k", START, TWO)?.state.selectedIndex).toBe(0);
  });

  it("navigation carries no decision intent", () => {
    expect(reduceRelationKey("j", START, TWO)?.intent).toBeUndefined();
    expect(reduceRelationKey("k", { selectedIndex: 1 }, TWO)?.intent).toBeUndefined();
  });
});

describe("reduceRelationKey — decisions", () => {
  it("A commits the selected relation's edge", () => {
    const result = reduceRelationKey("a", START, TWO);
    expect(result?.intent).toBe("commit");
    expect(result?.state.selectedIndex).toBe(0);
  });

  it("R rejects the selected relation", () => {
    const result = reduceRelationKey("r", START, TWO);
    expect(result?.intent).toBe("reject");
    expect(result?.state.selectedIndex).toBe(0);
  });

  it("decision keys are case-insensitive", () => {
    expect(reduceRelationKey("A", START, TWO)?.intent).toBe("commit");
    expect(reduceRelationKey("R", START, TWO)?.intent).toBe("reject");
  });
});

describe("reduceRelationKey — out-of-scheme keys", () => {
  it("returns null so the component leaves the keypress alone", () => {
    expect(reduceRelationKey("x", START, TWO)).toBeNull();
    expect(reduceRelationKey("Enter", START, TWO)).toBeNull();
    expect(reduceRelationKey("m", START, TWO)).toBeNull();
  });
});
