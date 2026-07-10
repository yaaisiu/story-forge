// The merge property-conflict mapper's pure logic (Session 43 — M4.S3b-fe, DM-S3b-2).
//
// A merge folds entity B (absorbed) into A (survivor). Non-conflicting properties union on the
// server; where BOTH set a key to *different* values the author must pick which to keep by hand
// (DM-S3b-2) — nothing is silently overwritten. The merge route's 400 only names the conflicting
// keys (a plain string, no values), so we detect conflicts CLIENT-SIDE from both entities'
// `properties`, mirroring the backend's pure `detect_property_conflicts`
// (backend/src/story_forge/domain/entity_merge.py), and feed the resolver both values to choose
// between. The 400 stays a safety net for a value that changed under us mid-resolve.
//
// Pure module (no React, no I/O), unit-tested like `propertiesEditor.ts` / `occurrences.ts`.

/** One property key the two entities set to different values — the author picks which to keep. */
export interface ConflictRow {
  key: string;
  survivorValue: unknown;
  absorbedValue: unknown;
}

/** Which side's value to keep for a conflict key (default: the survivor's). */
export type ConflictChoice = "survivor" | "absorbed";

/**
 * Detect property conflicts between the survivor (A, kept) and the absorbed (B) entity, mirroring
 * the backend: a conflict is a key present in BOTH whose values differ. A key only one side sets,
 * or both set equally (deep-equal, key-order-independent for objects), is not a conflict — the
 * server unions it, so we omit it.
 */
export function buildConflictRows(
  survivorProps: Record<string, unknown>,
  absorbedProps: Record<string, unknown>,
): ConflictRow[] {
  const rows: ConflictRow[] = [];
  for (const [key, absorbedValue] of Object.entries(absorbedProps)) {
    if (key in survivorProps && !valuesEqual(survivorProps[key], absorbedValue)) {
      rows.push({ key, survivorValue: survivorProps[key], absorbedValue });
    }
  }
  return rows;
}

/**
 * Build the `resolved_properties` dict the merge route requires: the chosen value for every
 * conflict key (and *only* the conflict keys — non-conflicting keys union server-side). An
 * unpicked key defaults to keeping the survivor's value.
 */
export function resolvedPropertiesFrom(
  rows: readonly ConflictRow[],
  picks: Readonly<Record<string, ConflictChoice>>,
): Record<string, unknown> {
  const resolved: Record<string, unknown> = {};
  for (const row of rows) {
    resolved[row.key] = picks[row.key] === "absorbed" ? row.absorbedValue : row.survivorValue;
  }
  return resolved;
}

/**
 * Value equality matching Python's `!=` on parsed JSON: scalars compare directly; objects/arrays
 * compare deep and order-independently (Python dict equality ignores key order, which a plain
 * `JSON.stringify` would not). Properties are JSON scalars or small objects/arrays.
 */
function valuesEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== "object" || typeof b !== "object" || a === null || b === null) return false;
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((item, i) => valuesEqual(item, b[i]));
  }
  const aObj = a as Record<string, unknown>;
  const bObj = b as Record<string, unknown>;
  const aKeys = Object.keys(aObj);
  if (aKeys.length !== Object.keys(bObj).length) return false;
  return aKeys.every((k) => k in bObj && valuesEqual(aObj[k], bObj[k]));
}
