import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { GraphEdge } from "../../lib/api/useStoryGraph";
import { useEdgeEditForm } from "./useEdgeEditForm";

function edgeFixture(over: Partial<GraphEdge> = {}): GraphEdge {
  return { id: "edge-1", type: "loves", subject_id: "s1", object_id: "o1", confidence: 1, ...over };
}

const NAMES: Record<string, string> = { s1: "Mira", o1: "Aldric", x9: "Bram" };
const nameOf = (id: string): string => NAMES[id] ?? id;

describe("useEdgeEditForm", () => {
  it("starts not editing and not dirty", () => {
    const { result } = renderHook(() => useEdgeEditForm(edgeFixture(), nameOf));
    expect(result.current.editing).toBe(false);
    expect(result.current.dirty).toBe(false);
    expect(result.current.canSave).toBe(false);
  });

  it("startEditing seeds the drafts from the edge and enters edit mode", () => {
    const { result } = renderHook(() => useEdgeEditForm(edgeFixture(), nameOf));

    act(() => result.current.startEditing());

    expect(result.current.editing).toBe(true);
    expect(result.current.state.predicateDraft).toBe("loves");
    expect(result.current.state.subject).toEqual({ entity_id: "s1", canonical_name: "Mira" });
    expect(result.current.dirty).toBe(false);
    expect(result.current.canSave).toBe(false);
  });

  it("dirty/canSave toggle on a predicate change and clear on revert", () => {
    const { result } = renderHook(() => useEdgeEditForm(edgeFixture(), nameOf));
    act(() => result.current.startEditing());

    act(() => result.current.setPredicate("adores"));
    expect(result.current.dirty).toBe(true);
    expect(result.current.canSave).toBe(true);

    act(() => result.current.setPredicate("loves"));
    expect(result.current.dirty).toBe(false);
    expect(result.current.canSave).toBe(false);
  });

  it("setSubject/setObject re-target endpoints and build the patch", () => {
    const { result } = renderHook(() => useEdgeEditForm(edgeFixture(), nameOf));
    act(() => result.current.startEditing());

    act(() => result.current.setObject({ entity_id: "x9", canonical_name: "Bram" }));
    expect(result.current.canSave).toBe(true);
    expect(result.current.buildPatch()).toEqual({ object_id: "x9" });
  });

  it("canSave is false when the predicate is blanked", () => {
    const { result } = renderHook(() => useEdgeEditForm(edgeFixture(), nameOf));
    act(() => result.current.startEditing());
    act(() => result.current.setPredicate("   "));
    expect(result.current.dirty).toBe(true);
    expect(result.current.canSave).toBe(false);
  });

  it("cancel leaves edit mode", () => {
    const { result } = renderHook(() => useEdgeEditForm(edgeFixture(), nameOf));
    act(() => result.current.startEditing());
    act(() => result.current.cancel());
    expect(result.current.editing).toBe(false);
  });

  it("is a no-op start when the edge is undefined", () => {
    const { result } = renderHook(() => useEdgeEditForm(undefined, nameOf));
    act(() => result.current.startEditing());
    expect(result.current.editing).toBe(false);
    expect(result.current.buildPatch()).toEqual({});
  });
});
