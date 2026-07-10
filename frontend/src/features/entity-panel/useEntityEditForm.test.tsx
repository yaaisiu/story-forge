import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { EntityDetailResponse } from "../../lib/api/useEntityDetail";
import { useEntityEditForm } from "./useEntityEditForm";

function detailFixture(over: Partial<EntityDetailResponse> = {}): EntityDetailResponse {
  return {
    entity_id: "e1",
    canonical_name: "Mira",
    language: "en",
    type: "person",
    aliases: ["the priestess"],
    properties: { age: 23 },
    ego_graph: { neighbours: [], edges: [] },
    ...over,
  };
}

describe("useEntityEditForm", () => {
  it("starts not editing and not dirty", () => {
    const { result } = renderHook(() => useEntityEditForm(detailFixture(), true));
    expect(result.current.editing).toBe(false);
    expect(result.current.dirty).toBe(false);
  });

  it("startEditing seeds the drafts from detail and enters edit mode", () => {
    const detail = detailFixture();
    const { result } = renderHook(() => useEntityEditForm(detail, true));

    act(() => result.current.startEditing());

    expect(result.current.editing).toBe(true);
    expect(result.current.state.nameDraft).toBe("Mira");
    expect(result.current.state.typeDraft).toBe("person");
    expect(result.current.dirty).toBe(false);
    expect(result.current.canSave).toBe(true);
  });

  it("dirty toggles on a change and clears on revert", () => {
    const { result } = renderHook(() => useEntityEditForm(detailFixture(), true));
    act(() => result.current.startEditing());

    act(() => result.current.setName("Mirabel"));
    expect(result.current.dirty).toBe(true);

    act(() => result.current.setName("Mira"));
    expect(result.current.dirty).toBe(false);
  });

  it("buildPatch maps the name to the project-language slot", () => {
    const { result } = renderHook(() => useEntityEditForm(detailFixture({ language: "pl" }), true));
    act(() => result.current.startEditing());
    act(() => result.current.setName("Mira"));

    const patch = result.current.buildPatch("pl");
    expect(patch.canonical_name_pl).toBe("Mira");
    expect(patch.canonical_name_en).toBeUndefined();
  });

  it("canSave is false without a story", () => {
    const { result } = renderHook(() => useEntityEditForm(detailFixture(), false));
    act(() => result.current.startEditing());
    expect(result.current.canSave).toBe(false);
  });

  it("cancel leaves edit mode", () => {
    const { result } = renderHook(() => useEntityEditForm(detailFixture(), true));
    act(() => result.current.startEditing());
    act(() => result.current.cancel());
    expect(result.current.editing).toBe(false);
  });

  it("is a no-op start when detail is undefined (not yet loaded)", () => {
    const { result } = renderHook(() => useEntityEditForm(undefined, true));
    act(() => result.current.startEditing());
    expect(result.current.editing).toBe(false);
    expect(result.current.dirty).toBe(false);
  });
});
