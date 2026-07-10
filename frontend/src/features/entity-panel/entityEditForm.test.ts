import { describe, expect, it } from "vitest";

import type { EntityDetailResponse } from "../../lib/api/useEntityDetail";
import { buildEntityEditPatch, canSaveForm, initialFormState, isFormDirty } from "./entityEditForm";

/** A minimal detail bundle; ego_graph is irrelevant to the edit form. */
function detailFixture(over: Partial<EntityDetailResponse> = {}): EntityDetailResponse {
  return {
    entity_id: "e1",
    canonical_name: "Mira",
    language: "en",
    type: "person",
    aliases: ["the priestess"],
    properties: { age: 23, role: "priestess" },
    ego_graph: { neighbours: [], edges: [] },
    ...over,
  };
}

describe("entityEditForm", () => {
  describe("initialFormState", () => {
    it("seeds the drafts from the detail bundle", () => {
      const state = initialFormState(detailFixture());
      expect(state.nameDraft).toBe("Mira");
      expect(state.typeDraft).toBe("person");
      expect(state.aliasDrafts).toEqual(["the priestess"]);
      expect(state.propRows).toEqual([
        { key: "age", value: "23", kind: "number" },
        { key: "role", value: "priestess", kind: "string" },
      ]);
    });
  });

  describe("isFormDirty", () => {
    it("is false for a freshly-seeded form (the guard-critical case)", () => {
      const detail = detailFixture();
      expect(isFormDirty(initialFormState(detail), detail)).toBe(false);
    });

    it("is true after a real change and false again after reverting it", () => {
      const detail = detailFixture();
      const base = initialFormState(detail);

      expect(isFormDirty({ ...base, nameDraft: "Mirabel" }, detail)).toBe(true);
      expect(isFormDirty({ ...base, nameDraft: "Mira" }, detail)).toBe(false);

      expect(isFormDirty({ ...base, typeDraft: "deity" }, detail)).toBe(true);
      expect(isFormDirty({ ...base, aliasDrafts: ["the priestess", "seer"] }, detail)).toBe(true);
      expect(
        isFormDirty(
          {
            ...base,
            propRows: [...base.propRows, { key: "home", value: "Oakhaven", kind: "string" }],
          },
          detail,
        ),
      ).toBe(true);
    });

    it("ignores insignificant whitespace and blank alias/property rows", () => {
      const detail = detailFixture();
      const base = initialFormState(detail);
      // trailing whitespace on name, a blank alias, and a keyless property row are all
      // normalized away by buildEntityEditPatch, so they must not read as dirty.
      expect(
        isFormDirty(
          {
            ...base,
            nameDraft: "Mira  ",
            aliasDrafts: ["the priestess", "  "],
            propRows: [...base.propRows, { key: "", value: "junk", kind: "string" }],
          },
          detail,
        ),
      ).toBe(false);
    });

    it("is order-independent for properties (a re-keyed dict is not a change)", () => {
      const detail = detailFixture();
      const base = initialFormState(detail);
      expect(
        isFormDirty({ ...base, propRows: [base.propRows[1]!, base.propRows[0]!] }, detail),
      ).toBe(false);
    });
  });

  describe("buildEntityEditPatch", () => {
    it("writes the name to the project-language slot (en)", () => {
      const state = initialFormState(detailFixture({ language: "en" }));
      const patch = buildEntityEditPatch({ ...state, nameDraft: "Mirabel" }, "en");
      expect(patch.canonical_name_en).toBe("Mirabel");
      expect(patch.canonical_name_pl).toBeUndefined();
    });

    it("writes the name to the pl slot when the project language is pl", () => {
      const state = initialFormState(detailFixture({ language: "pl" }));
      const patch = buildEntityEditPatch({ ...state, nameDraft: "Mira" }, "pl");
      expect(patch.canonical_name_pl).toBe("Mira");
      expect(patch.canonical_name_en).toBeUndefined();
    });

    it("trims name/type, trims-and-drops blank aliases, and coerces property kinds", () => {
      const patch = buildEntityEditPatch(
        {
          nameDraft: "  Mira  ",
          typeDraft: "  deity  ",
          aliasDrafts: [" seer ", "", "  "],
          propRows: [
            { key: "age", value: "40", kind: "number" },
            { key: "", value: "dropped", kind: "string" },
          ],
        },
        "en",
      );
      expect(patch.canonical_name_en).toBe("Mira");
      expect(patch.type).toBe("deity");
      expect(patch.aliases).toEqual(["seer"]);
      expect(patch.properties).toEqual({ age: 40 });
    });
  });

  describe("canSaveForm", () => {
    const state = initialFormState(detailFixture());

    it("is true for a valid form with a story", () => {
      expect(canSaveForm(state, true)).toBe(true);
    });

    it("is false without a story", () => {
      expect(canSaveForm(state, false)).toBe(false);
    });

    it("is false when the name or type is blank", () => {
      expect(canSaveForm({ ...state, nameDraft: "   " }, true)).toBe(false);
      expect(canSaveForm({ ...state, typeDraft: "" }, true)).toBe(false);
    });

    it("is false when any property row is invalid", () => {
      expect(
        canSaveForm(
          { ...state, propRows: [{ key: "age", value: "not-a-number", kind: "number" }] },
          true,
        ),
      ).toBe(false);
    });
  });
});
