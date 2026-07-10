// Shared display formatter for an entity's open-world `properties` values (Session 43 — M4.S3b-fe).
//
// A property value is free-form JSON (string / number / boolean / object / array, INV-4). Render it
// defensively: strings as-is, null/undefined as empty, objects/arrays stringified, anything else
// String()-coerced. Used by the read-only properties list (ReaderEntityPanel) and the merge
// conflict resolver (MergeControls) so both show a value identically. Pure, no React.

export function formatPropertyValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
