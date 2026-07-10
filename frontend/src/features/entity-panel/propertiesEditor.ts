// The typed `properties` editor's pure logic (Session 38 — M4.S3a-fe, DM-S3a-5).
//
// An entity's `properties` is free-form JSON (`{"age": 23, "role": "priestess"}`, §3.2,
// open-world — INV-4 forbids a fixed key schema). To edit it in a form, we turn the dict into
// a list of {key, value, kind} rows the panel renders as inputs, and turn the rows back into a
// JSON dict for the PATCH — coercing each value by its kind so a number stays a number (not
// stringified). Scalar kinds (string/number/boolean) are editable; an object/array/null value
// is kind "json" — *preserved* unchanged through an edit (shown read-only at PoC, no recursive
// editor — the simplicity call recorded in the plan). Keys stay free.
//
// Pure module (no React, no I/O), unit-tested like `occurrences.ts` / `egoElements.ts`.

export type PropertyKind = "string" | "number" | "boolean" | "json";

export interface PropertyRow {
  key: string;
  /** The value as edited in a text/select input; coerced back to its JSON type on save. */
  value: string;
  kind: PropertyKind;
}

/** Turn an entity's `properties` dict into editable rows (preserving insertion order). */
export function toPropertyRows(properties: Record<string, unknown>): PropertyRow[] {
  return Object.entries(properties).map(([key, value]) => {
    if (typeof value === "string") return { key, value, kind: "string" };
    if (typeof value === "number") return { key, value: String(value), kind: "number" };
    if (typeof value === "boolean")
      return { key, value: value ? "true" : "false", kind: "boolean" };
    // object, array, null — preserve as JSON text (round-trips via JSON.parse on save).
    return { key, value: JSON.stringify(value), kind: "json" };
  });
}

/**
 * Turn edited rows back into a `properties` dict for the PATCH. Assumes scalar values are
 * already valid (the panel gates the save on `isRowValueValid`); a "number"/"json" value
 * that slips through invalid coerces conservatively (NaN→0-safe via the validity gate, a
 * bad JSON would throw — so callers must validate first). Rows with a blank key are dropped;
 * a later row overwrites an earlier duplicate key (object semantics).
 */
export function rowsToProperties(rows: readonly PropertyRow[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const row of rows) {
    const key = row.key.trim();
    if (key === "") continue;
    out[key] = coerce(row);
  }
  return out;
}

function coerce(row: PropertyRow): unknown {
  switch (row.kind) {
    case "string":
      return row.value;
    case "number":
      return Number(row.value);
    case "boolean":
      return row.value === "true";
    case "json":
      return JSON.parse(row.value);
  }
}

/** Whether a row's value is valid for its kind — the panel disables save while any row fails. */
export function isRowValueValid(row: PropertyRow): boolean {
  switch (row.kind) {
    case "string":
    case "boolean":
      return true;
    case "number":
      return row.value.trim() !== "" && Number.isFinite(Number(row.value));
    case "json":
      try {
        JSON.parse(row.value);
        return true;
      } catch {
        return false;
      }
  }
}
