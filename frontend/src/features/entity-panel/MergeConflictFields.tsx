// The by-hand merge property-conflict resolver (extracted Session 79 — Graph-quality S4b,
// originally inline in MergeControls, Session 43 — M4.S3b-fe, DM-S3b-2).
//
// A merge folds entity B (absorbed) into A (survivor). Where both set a property key to
// *different* values the author picks which to keep by hand — nothing is silently overwritten.
// This is the presentational fieldset only (render and dispatch): conflict detection is the pure
// `mergeConflicts` module, the write is `useMergeEntities`. Reused by both the reader's
// MergeControls and the duplicate-review card, so the resolution UX is identical on both surfaces.

import { formatPropertyValue } from "./formatPropertyValue";
import type { ConflictChoice, ConflictRow } from "./mergeConflicts";

interface MergeConflictFieldsProps {
  conflicts: ConflictRow[];
  /** The author's current choice per conflict key (absent → the survivor's value is kept). */
  picks: Record<string, ConflictChoice>;
  onChange: (key: string, choice: ConflictChoice) => void;
}

export function MergeConflictFields({ conflicts, picks, onChange }: MergeConflictFieldsProps) {
  if (conflicts.length === 0) return null;

  return (
    <fieldset data-testid="merge-conflicts" className="flex flex-col gap-2">
      <legend className="text-xs font-medium uppercase tracking-wide text-gray-500">
        Resolve conflicting properties
      </legend>
      {conflicts.map((row) => {
        const choice = picks[row.key] ?? "survivor";
        return (
          <div
            key={row.key}
            data-testid="merge-conflict"
            className="flex flex-col gap-1 border-b border-gray-100 pb-1"
          >
            <span className="text-xs font-medium text-gray-600">{row.key}</span>
            <div className="flex gap-1">
              <button
                type="button"
                data-testid="merge-keep-survivor"
                aria-pressed={choice === "survivor"}
                onClick={() => onChange(row.key, "survivor")}
                className={`flex-1 truncate rounded border px-2 py-1 text-left text-xs ${
                  choice === "survivor"
                    ? "border-gray-800 bg-gray-800 text-white"
                    : "border-gray-300 text-gray-700 hover:bg-gray-50"
                }`}
              >
                keep: {formatPropertyValue(row.survivorValue)}
              </button>
              <button
                type="button"
                data-testid="merge-keep-absorbed"
                aria-pressed={choice === "absorbed"}
                onClick={() => onChange(row.key, "absorbed")}
                className={`flex-1 truncate rounded border px-2 py-1 text-left text-xs ${
                  choice === "absorbed"
                    ? "border-gray-800 bg-gray-800 text-white"
                    : "border-gray-300 text-gray-700 hover:bg-gray-50"
                }`}
              >
                use: {formatPropertyValue(row.absorbedValue)}
              </button>
            </div>
          </div>
        );
      })}
    </fieldset>
  );
}
