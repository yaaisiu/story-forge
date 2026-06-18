// The reader's entity side panel (Session 35 — M4.S2b, spec §3.4/§3.5, DM-SP-6).
//
// Opens when the author clicks a highlight in the prose: a read-only inspection of that
// accepted entity — its details (canonical_name, type, aliases), its free-form
// `properties` (DM-SP-5, key→value), a 1-hop ego-graph mini-view (DM-SP-4), and a
// timeline of its occurrences in *this* story's prose (DM-SP-3). Tapping a neighbour in
// the mini-graph re-targets the panel to that entity ("inspect nodes"); clicking an
// occurrence drills back to the paragraph in the reader (the parent scrolls + flashes).
//
// A new panel rather than a shared one with graph-viewer/NodeDetailsPanel (DM-SP-6):
// the two have different inputs and the reader's gains *edit* affordances next slice;
// we mirror that panel's structure (aside/dl/data-testid/close button), not its code.
//
// Read-only this slice (INV-1/3/9 untouched). React escapes all text by default, so
// rendering the author's own `properties` + entity names is safe — no
// dangerouslySetInnerHTML (the proposal's Layer 7).
//
// Components render and dispatch: occurrences come from the pure `entityOccurrences`,
// the bundle from `useEntityDetail`, the mini-graph from EgoGraphCanvas + `toEgoElements`.

import { useMemo } from "react";

import type { ReaderParagraph } from "../../lib/api/useReader";
import { useEntityDetail } from "../../lib/api/useEntityDetail";
import { EgoGraphCanvas } from "./EgoGraphCanvas";
import { entityOccurrences } from "./occurrences";

interface ReaderEntityPanelProps {
  storyId: string | undefined;
  entityId: string;
  paragraphs: readonly ReaderParagraph[];
  onClose: () => void;
  /** Inspect a neighbour entity (tapped in the mini-graph) — re-targets the panel. */
  onSelectEntity: (entityId: string) => void;
  /** Drill an occurrence back to its paragraph in the reader (scroll + flash). */
  onNavigateToOccurrence: (paragraphId: string) => void;
}

/** Render an open-world property value defensively: strings as-is, anything else stringified. */
function formatPropertyValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function ReaderEntityPanel({
  storyId,
  entityId,
  paragraphs,
  onClose,
  onSelectEntity,
  onNavigateToOccurrence,
}: ReaderEntityPanelProps) {
  const detail = useEntityDetail(storyId, entityId);

  // DM-SP-3: occurrences are the entity's *rendered highlights* across the reader's
  // paragraphs, so the timeline always agrees with the visible prose. Derived from data
  // already on the page — no extra fetch.
  const occurrences = useMemo(
    () => entityOccurrences(paragraphs, entityId),
    [paragraphs, entityId],
  );

  return (
    <aside
      data-testid="reader-entity-panel"
      className="flex w-80 shrink-0 flex-col gap-3 border-l border-gray-200 p-4 text-sm"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 data-testid="reader-entity-name" className="text-base font-semibold text-gray-900">
          {detail.data?.canonical_name ?? "Entity"}
        </h2>
        <button
          type="button"
          data-testid="reader-entity-close"
          onClick={onClose}
          aria-label="Close entity panel"
          className="rounded px-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        >
          ✕
        </button>
      </div>

      {detail.isPending && (
        <p data-testid="reader-entity-loading" className="text-gray-500">
          Loading entity…
        </p>
      )}
      {detail.isError && (
        <p data-testid="reader-entity-error" role="alert" className="text-red-700">
          Couldn&rsquo;t load this entity.
        </p>
      )}

      {detail.isSuccess && (
        <>
          <dl className="flex flex-col gap-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Type</dt>
              <dd data-testid="reader-entity-type" className="text-gray-800">
                {detail.data.type}
              </dd>
            </div>

            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Aliases</dt>
              <dd data-testid="reader-entity-aliases" className="text-gray-800">
                {detail.data.aliases.length > 0 ? (
                  detail.data.aliases.join(", ")
                ) : (
                  <span className="text-gray-400">none</span>
                )}
              </dd>
            </div>

            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Properties
              </dt>
              <dd data-testid="reader-entity-properties" className="text-gray-800">
                {Object.keys(detail.data.properties).length > 0 ? (
                  <dl className="flex flex-col gap-1">
                    {Object.entries(detail.data.properties).map(([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <dt className="shrink-0 font-medium text-gray-600">{key}</dt>
                        <dd className="break-words text-gray-800">{formatPropertyValue(value)}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <span className="text-gray-400">none</span>
                )}
              </dd>
            </div>
          </dl>

          <section className="flex flex-col gap-1">
            <h3 className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Local graph
            </h3>
            <EgoGraphCanvas detail={detail.data} onSelectNeighbour={onSelectEntity} />
          </section>

          <section className="flex flex-col gap-1">
            <h3 className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Occurrences ({occurrences.length})
            </h3>
            {occurrences.length > 0 ? (
              <ol data-testid="reader-entity-occurrences" className="flex flex-col gap-1">
                {occurrences.map((occ) => (
                  <li key={occ.paragraphId}>
                    <button
                      type="button"
                      data-testid="occurrence"
                      data-paragraph-id={occ.paragraphId}
                      onClick={() => onNavigateToOccurrence(occ.paragraphId)}
                      className="w-full rounded border border-gray-200 px-2 py-1 text-left text-xs text-gray-700 hover:bg-gray-50"
                    >
                      <span className="line-clamp-3">{occ.snippet}</span>
                      {occ.count > 1 && <span className="ml-1 text-gray-400">×{occ.count}</span>}
                    </button>
                  </li>
                ))}
              </ol>
            ) : (
              <p data-testid="reader-entity-occurrences-empty" className="text-xs text-gray-400">
                Not highlighted in this story.
              </p>
            )}
          </section>
        </>
      )}
    </aside>
  );
}
