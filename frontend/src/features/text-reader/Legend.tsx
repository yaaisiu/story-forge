// Colour legend for the reader (M4.S1, spec §3.5 / DM-IH-5): a swatch + label per
// entity type present, so the colour-by-type highlighting is decodable. Pure props.

import type { LegendEntry } from "./palette";

export function Legend({ entries }: { entries: readonly LegendEntry[] }) {
  if (entries.length === 0) return null;

  return (
    <div
      data-testid="reader-legend"
      className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-gray-600"
    >
      {entries.map((entry) => (
        <span key={entry.type} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block h-3 w-3 shrink-0 rounded-sm"
            style={{ backgroundColor: entry.color }}
          />
          {entry.type}
        </span>
      ))}
    </div>
  );
}
