// The shared entity-edit form's pure logic (Graph-quality S5a — extracted from
// ReaderEntityPanel so the reader and the graph canvas compose the same edit core,
// DM-S5-1(B)). No React, no I/O — unit-tested like `propertiesEditor.ts`.
//
// The panel edits an accepted entity's name/type/aliases/`properties` and PATCHes the
// diff. This module owns: seeding the form from the fetched detail (`initialFormState`),
// building the PATCH body (`buildEntityEditPatch`, incl. the single-project-language name
// rule), gating the save (`canSaveForm`), and — new for the canvas — a `isFormDirty`
// predicate that powers the panel-vanish guard (DM-S5-6): a dirty edit holds the selection
// so a background refetch/filter can't yank the panel mid-edit.

import type { EntityDetailResponse } from "../../lib/api/useEntityDetail";
import type { EntityEditPatch } from "../../lib/api/useEntityEdit";
import {
  isRowValueValid,
  rowsToProperties,
  toPropertyRows,
  type PropertyRow,
} from "./propertiesEditor";

export interface EditFormState {
  nameDraft: string;
  typeDraft: string;
  aliasDrafts: string[];
  propRows: PropertyRow[];
}

/** Seed the editable drafts from the fetched detail bundle. */
export function initialFormState(detail: EntityDetailResponse): EditFormState {
  return {
    nameDraft: detail.canonical_name,
    typeDraft: detail.type,
    aliasDrafts: [...detail.aliases],
    propRows: toPropertyRows(detail.properties),
  };
}

/** Build the name half of a patch: write the single field to the project-language slot
 * (one language per project at PoC — spec §10 q8). */
function namePatch(language: string, name: string): EntityEditPatch {
  return language === "pl" ? { canonical_name_pl: name } : { canonical_name_en: name };
}

/** Build the PATCH body from the current drafts (trimming name/type, dropping blank
 * aliases, coercing property rows back to their JSON kinds). */
export function buildEntityEditPatch(state: EditFormState, language: string): EntityEditPatch {
  return {
    ...namePatch(language, state.nameDraft.trim()),
    type: state.typeDraft.trim(),
    aliases: state.aliasDrafts.map((a) => a.trim()).filter(Boolean),
    properties: rowsToProperties(state.propRows),
  };
}

/** Whether the form is saveable: a story is known, name and type are non-empty, and every
 * property row is valid for its kind. */
export function canSaveForm(state: EditFormState, hasStory: boolean): boolean {
  return (
    hasStory &&
    state.nameDraft.trim() !== "" &&
    state.typeDraft.trim() !== "" &&
    state.propRows.every(isRowValueValid)
  );
}

/**
 * Whether the drafts differ from the fetched detail *after normalization* — the guard's
 * signal. Both sides are reduced to the same normalized `{name, type, aliases, properties}`
 * shape `buildEntityEditPatch` produces, so cosmetic-only edits (trailing whitespace, a
 * blank alias/property row, re-ordered property keys) do not read as dirty. A freshly-seeded
 * form is never dirty; reverting a change clears it. Guarded on `isRowValueValid` because an
 * in-progress invalid number/JSON row can't be normalized — treat it as dirty (there's an
 * unsaved edit in flight) rather than throw.
 */
export function isFormDirty(state: EditFormState, detail: EntityDetailResponse): boolean {
  if (!state.propRows.every(isRowValueValid)) return true;
  return !deepEqual(normalize(state), normalize(initialFormState(detail)));
}

interface NormalizedForm {
  name: string;
  type: string;
  aliases: string[];
  properties: Record<string, unknown>;
}

function normalize(state: EditFormState): NormalizedForm {
  return {
    name: state.nameDraft.trim(),
    type: state.typeDraft.trim(),
    aliases: state.aliasDrafts.map((a) => a.trim()).filter(Boolean),
    properties: rowsToProperties(state.propRows),
  };
}

/** Structural deep equality (primitives, arrays, plain objects) — order-independent for
 * object keys, order-sensitive for arrays. Enough for normalized property values. */
function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((item, i) => deepEqual(item, b[i]));
  }
  if (a && b && typeof a === "object") {
    const ao = a as Record<string, unknown>;
    const bo = b as Record<string, unknown>;
    const keys = Object.keys(ao);
    if (keys.length !== Object.keys(bo).length) return false;
    return keys.every(
      (k) => Object.prototype.hasOwnProperty.call(bo, k) && deepEqual(ao[k], bo[k]),
    );
  }
  return false;
}
