// Edge-evidence side panel (Session 76 — Graph-quality S3b, spec §3.4, DM-EE-1/2).
//
// Renders the tapped edge's provenance: its predicate + every source paragraph that
// asserts the fact, each with the model's supporting quote. Presentational and pure
// (mirrors NodeDetailsPanel) — the container (GraphViewer) owns the useEdgeEvidence
// fetch and hands the panel its state, so the panel stays render-only and unit-testable
// without a hook mock. Read-only this slice — S3 verifies, it never writes (INV-1/9).
//
// The evidence quote + paragraph text are the author's own story text, rendered through
// React's default escaping (never dangerouslySetInnerHTML) — the standing stored-XSS
// guard the M4 reader held. A zero-provenance edge (added by hand — the write path
// creates no staged row) resolves as a 200 with an empty list: show "no recorded source
// (added manually)", never an empty or broken panel.

import type { EdgeEvidence } from "../../lib/api/useEdgeEvidence";

interface EdgeEvidencePanelProps {
  /** The tapped edge id, or null when nothing is selected. */
  edgeId: string | null;
  /** The last-known evidence bundle (kept across a background refetch, undefined until first load). */
  evidence: EdgeEvidence | undefined;
  isPending: boolean;
  /** Retry the evidence read — re-tapping the already-selected edge is a no-op, so the
   * error state needs an explicit refetch rather than a "select again" instruction. */
  onRetry: () => void;
  onClose: () => void;
}

const PANEL_CLASS = "flex w-72 shrink-0 flex-col gap-3 border-l border-gray-200 p-4 text-sm";

export function EdgeEvidencePanel({
  edgeId,
  evidence,
  isPending,
  onRetry,
  onClose,
}: EdgeEvidencePanelProps) {
  if (!edgeId) {
    return (
      <aside
        data-testid="edge-evidence-empty"
        className="w-72 shrink-0 border-l border-gray-200 p-4 text-sm text-gray-500"
      >
        Click an edge to see its evidence.
      </aside>
    );
  }

  const header = (
    <div className="flex items-start justify-between gap-2">
      <h2 className="text-base font-semibold text-gray-900">Edge evidence</h2>
      <button
        type="button"
        data-testid="edge-evidence-close"
        onClick={onClose}
        aria-label="Close evidence"
        className="rounded px-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
      >
        ✕
      </button>
    </div>
  );

  // `isPending` is only true before the first successful load (TanStack keeps `data`
  // across a background refetch), so a refetch failure with data in hand falls through
  // to render the last-good evidence rather than blanking it with the error state.
  if (isPending) {
    return (
      <aside data-testid="edge-evidence-loading" className={PANEL_CLASS}>
        {header}
        <p className="text-gray-500">Loading evidence…</p>
      </aside>
    );
  }

  if (!evidence) {
    return (
      <aside data-testid="edge-evidence-error" className={PANEL_CLASS}>
        {header}
        <p role="alert" className="text-red-700">
          Couldn&rsquo;t load this edge&rsquo;s evidence.
        </p>
        <button
          type="button"
          data-testid="edge-evidence-retry"
          onClick={onRetry}
          className="self-start rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
        >
          Try again
        </button>
      </aside>
    );
  }

  const sources = evidence.source_provenance;

  return (
    <aside data-testid="edge-evidence" className={PANEL_CLASS}>
      {header}

      <dl>
        <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Relationship</dt>
        <dd data-testid="edge-evidence-predicate" className="text-gray-800">
          {evidence.predicate ?? <span className="text-gray-400">unknown</span>}
        </dd>
      </dl>

      {sources.length === 0 ? (
        <p data-testid="edge-evidence-none" className="text-gray-400">
          No recorded source (added manually).
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Source {sources.length === 1 ? "paragraph" : "paragraphs"}
          </p>
          {sources.map((source, index) => (
            <div
              key={`${source.paragraph_id}-${index}`}
              data-testid="edge-evidence-source"
              className="flex flex-col gap-1"
            >
              {source.evidence_quote && (
                <blockquote className="border-l-2 border-amber-300 pl-2 text-gray-800">
                  “{source.evidence_quote}”
                </blockquote>
              )}
              <p className="text-xs text-gray-600">{source.paragraph_text}</p>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
