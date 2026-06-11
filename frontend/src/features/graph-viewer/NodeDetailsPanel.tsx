// Node-details side panel (Session 17 — M2.S5 graph viewer).
//
// Renders the clicked entity's details (spec §3.4: canonical_name, aliases, type,
// occurrences). Read-only this milestone — editing properties/relations is M3's
// review UI. The "first seen" paragraph is shown as a value, not a link: the text
// reader that occurrences drill into (`features/text-reader/`) isn't built yet, so
// a link would dead-end — surface the reference now, wire the drill-down when the
// reader lands (spec §3.4 "drill-down to text").

import type { GraphNode } from "../../lib/api/useStoryGraph";

interface NodeDetailsPanelProps {
  node: GraphNode | null;
  onClose: () => void;
}

export function NodeDetailsPanel({ node, onClose }: NodeDetailsPanelProps) {
  if (!node) {
    return (
      <aside
        data-testid="node-details-empty"
        className="w-72 shrink-0 border-l border-gray-200 p-4 text-sm text-gray-500"
      >
        Click a node to see its details.
      </aside>
    );
  }

  const name = node.canonical_name_pl ?? node.canonical_name_en ?? node.aliases[0] ?? "(unnamed)";

  return (
    <aside
      data-testid="node-details"
      className="flex w-72 shrink-0 flex-col gap-3 border-l border-gray-200 p-4 text-sm"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-base font-semibold text-gray-900">{name}</h2>
        <button
          type="button"
          data-testid="node-details-close"
          onClick={onClose}
          aria-label="Close details"
          className="rounded px-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        >
          ✕
        </button>
      </div>

      <dl className="flex flex-col gap-2">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Type</dt>
          <dd data-testid="node-details-type" className="text-gray-800">
            {node.type}
          </dd>
        </div>

        {node.canonical_name_en && node.canonical_name_pl && (
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Canonical (EN)
            </dt>
            <dd className="text-gray-800">{node.canonical_name_en}</dd>
          </div>
        )}

        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Aliases</dt>
          <dd data-testid="node-details-aliases" className="text-gray-800">
            {node.aliases.length > 0 ? (
              node.aliases.join(", ")
            ) : (
              <span className="text-gray-400">none</span>
            )}
          </dd>
        </div>

        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
            First seen in paragraph
          </dt>
          <dd
            data-testid="node-details-first-seen"
            className="break-all font-mono text-xs text-gray-700"
          >
            {node.first_seen_paragraph_id ?? <span className="text-gray-400">unknown</span>}
          </dd>
        </div>
      </dl>
    </aside>
  );
}
