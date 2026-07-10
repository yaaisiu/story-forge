// The reader's entity side panel (Session 35 — M4.S2b read-only; Session 38 — M4.S3a-fe edit;
// Graph-quality S5a — recomposed over the shared EntityEditPanel core).
//
// Opens when the author clicks a highlight in the prose. The edit/merge/delete core now lives
// in the shared `EntityEditPanel` (DM-S5-1(B) — the reader and the graph canvas compose the same
// core). This wrapper supplies the reader-only context via `renderReadExtras`: the editable
// relations list, a 1-hop ego-graph mini-view (DM-SP-4), and a timeline of the entity's
// occurrences in *this* story's prose (DM-SP-3). Tapping a neighbour re-targets the panel;
// clicking an occurrence drills back to the paragraph.
//
// React escapes all text by default, so rendering the author's own input is safe.

import { useMemo, useState } from "react";

import { EntityPicker } from "../extraction-review/EntityPicker";
import { EntityEditPanel } from "../entity-panel/EntityEditPanel";
import type { EntitySearchResult } from "../../lib/api/useEntitySearch";
import type { ReaderParagraph } from "../../lib/api/useReader";
import { useAddRelation } from "../../lib/api/useAddRelation";
import { type EntityDetailResponse } from "../../lib/api/useEntityDetail";
import { useRemoveRelation } from "../../lib/api/useRemoveRelation";
import { EgoGraphCanvas } from "./EgoGraphCanvas";
import { egoNeighbourLabel } from "./egoElements";
import { entityOccurrences } from "./occurrences";

interface ReaderEntityPanelProps {
  storyId: string | undefined;
  entityId: string;
  paragraphs: readonly ReaderParagraph[];
  onClose: () => void;
  /** The entity was deleted — close the panel (it no longer exists). */
  onDeleted: () => void;
  /** Inspect a neighbour entity (tapped in the mini-graph) — re-targets the panel. */
  onSelectEntity: (entityId: string) => void;
  /** Drill an occurrence back to its paragraph in the reader (scroll + flash). */
  onNavigateToOccurrence: (paragraphId: string) => void;
}

export function ReaderEntityPanel({
  storyId,
  entityId,
  paragraphs,
  onClose,
  onDeleted,
  onSelectEntity,
  onNavigateToOccurrence,
}: ReaderEntityPanelProps) {
  const sid = storyId ?? "";

  return (
    <EntityEditPanel
      storyId={sid}
      entityId={entityId}
      testIdPrefix="reader-entity"
      widthClass="w-80"
      onClose={onClose}
      onDeleted={onDeleted}
      renderReadExtras={(detail) => (
        <ReaderExtras
          storyId={sid}
          entityId={entityId}
          detail={detail}
          paragraphs={paragraphs}
          onSelectEntity={onSelectEntity}
          onNavigateToOccurrence={onNavigateToOccurrence}
        />
      )}
    />
  );
}

interface ReaderExtrasProps {
  storyId: string;
  entityId: string;
  detail: EntityDetailResponse;
  paragraphs: readonly ReaderParagraph[];
  onSelectEntity: (entityId: string) => void;
  onNavigateToOccurrence: (paragraphId: string) => void;
}

/** The reader-only sections below the shared edit core: relations, the ego mini-graph, and
 * the occurrence timeline. Rendered only in read mode (the shared core hides extras while editing). */
function ReaderExtras({
  storyId,
  entityId,
  detail,
  paragraphs,
  onSelectEntity,
  onNavigateToOccurrence,
}: ReaderExtrasProps) {
  // DM-SP-3: occurrences are the entity's *rendered highlights* across the reader's
  // paragraphs, so the timeline always agrees with the visible prose. Derived from data
  // already on the page — no extra fetch.
  const occurrences = useMemo(
    () => entityOccurrences(paragraphs, entityId),
    [paragraphs, entityId],
  );

  return (
    <>
      <RelationsSection
        storyId={storyId}
        entityId={entityId}
        detail={detail}
        onSelectEntity={onSelectEntity}
      />

      <section className="flex flex-col gap-1">
        <h3 className="text-xs font-medium uppercase tracking-wide text-gray-500">Local graph</h3>
        <EgoGraphCanvas detail={detail} onSelectNeighbour={onSelectEntity} />
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
  );
}

/** Build a neighbour-id → display-name lookup from the ego-graph (reusing the ego-graph's
 * own label rule, so the relations list and the mini-graph name a neighbour identically). */
function neighbourNames(detail: EntityDetailResponse): Map<string, string> {
  const names = new Map<string, string>();
  for (const n of detail.ego_graph.neighbours ?? []) {
    names.set(n.entity_id, egoNeighbourLabel(n));
  }
  return names;
}

interface RelationsSectionProps {
  storyId: string;
  entityId: string;
  detail: EntityDetailResponse;
  onSelectEntity: (entityId: string) => void;
}

/** The editable relations list: each ego-graph edge with a remove button, plus an add form. */
function RelationsSection({ storyId, entityId, detail, onSelectEntity }: RelationsSectionProps) {
  const addRelation = useAddRelation(storyId);
  const removeRelation = useRemoveRelation(storyId);
  const names = useMemo(() => neighbourNames(detail), [detail]);

  const [picked, setPicked] = useState<EntitySearchResult | null>(null);
  const [predicate, setPredicate] = useState("");
  const [focalIsSubject, setFocalIsSubject] = useState(true);

  const edges = detail.ego_graph.edges ?? [];
  const busy = addRelation.isPending || removeRelation.isPending;

  function submitAdd() {
    if (!picked || predicate.trim() === "") return;
    const body = focalIsSubject
      ? { subject_id: entityId, predicate: predicate.trim(), object_id: picked.entity_id }
      : { subject_id: picked.entity_id, predicate: predicate.trim(), object_id: entityId };
    addRelation.mutate(body, {
      onSuccess: () => {
        setPicked(null);
        setPredicate("");
      },
    });
  }

  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-medium uppercase tracking-wide text-gray-500">Relations</h3>

      {edges.length > 0 ? (
        <ul data-testid="reader-relations" className="flex flex-col gap-1">
          {edges.map((edge) => (
            <li key={edge.id} data-testid="reader-relation" className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onSelectEntity(edge.neighbour_id)}
                className="flex-1 truncate text-left text-xs text-gray-700 hover:underline"
              >
                {edge.direction === "out" ? "→ " : "← "}
                <span className="font-medium">{edge.type}</span>{" "}
                {names.get(edge.neighbour_id) ?? edge.neighbour_id}
              </button>
              <button
                type="button"
                data-testid="reader-relation-remove"
                aria-label="Remove relation"
                disabled={busy}
                onClick={() => removeRelation.mutate(edge.id)}
                className="rounded border border-gray-300 px-2 text-gray-500 hover:bg-gray-50 disabled:opacity-50"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p data-testid="reader-relations-empty" className="text-xs text-gray-400">
          No relations yet.
        </p>
      )}

      <div className="flex flex-col gap-1 rounded border border-gray-100 p-2">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Add relation</p>
        <div className="flex items-center gap-1 text-xs text-gray-600">
          <button
            type="button"
            data-testid="reader-relation-orientation"
            onClick={() => setFocalIsSubject((prev) => !prev)}
            title="Click to flip the relationship direction"
            className="rounded border border-gray-300 px-2 py-0.5 hover:bg-gray-50"
          >
            {/* "this" and "other" stay put; only the arrow flips, so the direction is the
                thing that changes on click (not the labels swapping places). */}
            this {focalIsSubject ? "→" : "←"} other
          </button>
        </div>
        <input
          data-testid="reader-relation-predicate"
          value={predicate}
          placeholder="predicate (e.g. loves)"
          onChange={(event) => setPredicate(event.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-xs"
        />
        {picked ? (
          <p className="text-xs text-gray-700">
            other: <span className="font-medium">{picked.canonical_name}</span>{" "}
            <button
              type="button"
              data-testid="reader-relation-clear-pick"
              onClick={() => setPicked(null)}
              className="text-gray-400 hover:underline"
            >
              change
            </button>
          </p>
        ) : (
          <EntityPicker storyId={storyId} onPick={setPicked} disabled={busy} />
        )}
        <button
          type="button"
          data-testid="reader-relation-add"
          disabled={busy || !picked || predicate.trim() === ""}
          onClick={submitAdd}
          className="self-start rounded bg-gray-800 px-3 py-1 text-xs text-white hover:bg-gray-700 disabled:opacity-50"
        >
          Add
        </button>
        {addRelation.isError && (
          <p data-testid="reader-relation-error" role="alert" className="text-xs text-red-700">
            {addRelation.error.detail}
          </p>
        )}
        {addRelation.data?.merged_into_existing && (
          <p
            data-testid="reader-relation-merged-warning"
            role="alert"
            className="text-xs text-amber-700"
          >
            Folded onto an existing relation between these entities.
          </p>
        )}
      </div>
    </section>
  );
}
