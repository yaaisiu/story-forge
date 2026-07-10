import { describe, expect, it } from "vitest";

import type { GraphEdge } from "../../lib/api/useStoryGraph";
import {
  buildRetargetPatch,
  canSaveEdgeForm,
  initialEdgeFormState,
  isEdgeFormDirty,
} from "./edgeEditForm";

/** A minimal edge; `confidence` is irrelevant to the edit form. */
function edgeFixture(over: Partial<GraphEdge> = {}): GraphEdge {
  return {
    id: "edge-1",
    type: "loves",
    subject_id: "s1",
    object_id: "o1",
    confidence: 1,
    ...over,
  };
}

/** A tiny id → display-name lookup for seeding endpoint drafts. */
const NAMES: Record<string, string> = { s1: "Mira", o1: "Aldric", x9: "Bram" };
const nameOf = (id: string): string => NAMES[id] ?? id;

describe("edgeEditForm", () => {
  describe("initialEdgeFormState", () => {
    it("seeds the drafts from the edge and the name lookup", () => {
      const state = initialEdgeFormState(edgeFixture(), nameOf);
      expect(state.predicateDraft).toBe("loves");
      expect(state.subject).toEqual({ entity_id: "s1", canonical_name: "Mira" });
      expect(state.object).toEqual({ entity_id: "o1", canonical_name: "Aldric" });
    });

    it("falls back to the id when the name lookup misses", () => {
      const state = initialEdgeFormState(edgeFixture({ subject_id: "unknown" }), nameOf);
      expect(state.subject).toEqual({ entity_id: "unknown", canonical_name: "unknown" });
    });
  });

  describe("buildRetargetPatch", () => {
    it("includes only the changed predicate (trimmed)", () => {
      const edge = edgeFixture();
      const state = initialEdgeFormState(edge, nameOf);
      expect(buildRetargetPatch({ ...state, predicateDraft: "  adores  " }, edge)).toEqual({
        predicate: "adores",
      });
    });

    it("includes only a changed subject endpoint", () => {
      const edge = edgeFixture();
      const state = initialEdgeFormState(edge, nameOf);
      expect(
        buildRetargetPatch(
          { ...state, subject: { entity_id: "x9", canonical_name: "Bram" } },
          edge,
        ),
      ).toEqual({ subject_id: "x9" });
    });

    it("includes only a changed object endpoint", () => {
      const edge = edgeFixture();
      const state = initialEdgeFormState(edge, nameOf);
      expect(
        buildRetargetPatch({ ...state, object: { entity_id: "x9", canonical_name: "Bram" } }, edge),
      ).toEqual({ object_id: "x9" });
    });

    it("combines multiple changes into one body", () => {
      const edge = edgeFixture();
      expect(
        buildRetargetPatch(
          {
            predicateDraft: "adores",
            subject: { entity_id: "x9", canonical_name: "Bram" },
            object: { entity_id: "o1", canonical_name: "Aldric" },
          },
          edge,
        ),
      ).toEqual({ predicate: "adores", subject_id: "x9" });
    });

    it("is an empty body when nothing changed", () => {
      const edge = edgeFixture();
      const state = initialEdgeFormState(edge, nameOf);
      expect(buildRetargetPatch(state, edge)).toEqual({});
    });
  });

  describe("isEdgeFormDirty", () => {
    it("is false for a freshly-seeded form (the guard-critical case)", () => {
      const edge = edgeFixture();
      expect(isEdgeFormDirty(initialEdgeFormState(edge, nameOf), edge)).toBe(false);
    });

    it("is true after a real change and false again after reverting it", () => {
      const edge = edgeFixture();
      const base = initialEdgeFormState(edge, nameOf);
      expect(isEdgeFormDirty({ ...base, predicateDraft: "adores" }, edge)).toBe(true);
      expect(isEdgeFormDirty({ ...base, predicateDraft: "loves" }, edge)).toBe(false);
      expect(
        isEdgeFormDirty({ ...base, object: { entity_id: "x9", canonical_name: "Bram" } }, edge),
      ).toBe(true);
    });

    it("ignores insignificant predicate whitespace", () => {
      const edge = edgeFixture();
      const base = initialEdgeFormState(edge, nameOf);
      expect(isEdgeFormDirty({ ...base, predicateDraft: "loves  " }, edge)).toBe(false);
    });

    it("treats a blanked predicate as dirty (an unsaved change is in flight)", () => {
      const edge = edgeFixture();
      const base = initialEdgeFormState(edge, nameOf);
      expect(isEdgeFormDirty({ ...base, predicateDraft: "  " }, edge)).toBe(true);
    });
  });

  describe("canSaveEdgeForm", () => {
    it("is true when at least one field changed and the predicate is non-blank", () => {
      const edge = edgeFixture();
      const base = initialEdgeFormState(edge, nameOf);
      expect(canSaveEdgeForm({ ...base, predicateDraft: "adores" }, edge)).toBe(true);
      expect(
        canSaveEdgeForm({ ...base, subject: { entity_id: "x9", canonical_name: "Bram" } }, edge),
      ).toBe(true);
    });

    it("is false when nothing changed", () => {
      const edge = edgeFixture();
      expect(canSaveEdgeForm(initialEdgeFormState(edge, nameOf), edge)).toBe(false);
    });

    it("is false when the predicate is blanked (backend rejects a blank predicate)", () => {
      const edge = edgeFixture();
      const base = initialEdgeFormState(edge, nameOf);
      expect(canSaveEdgeForm({ ...base, predicateDraft: "   " }, edge)).toBe(false);
    });

    it("allows a self-loop (subject === object is intentional)", () => {
      const edge = edgeFixture();
      const base = initialEdgeFormState(edge, nameOf);
      expect(
        canSaveEdgeForm({ ...base, object: { entity_id: "s1", canonical_name: "Mira" } }, edge),
      ).toBe(true);
    });
  });
});
