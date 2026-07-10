// Edge side panel (Session 76 — Graph-quality S3b read; extended Session 83 — S5b-fe edit).
//
// Read mode renders the tapped edge's provenance: its predicate + every source paragraph
// that asserts the fact, each with the model's supporting quote (S3b). Edit mode (S5b-fe)
// surfaces the three edge affordances on the same panel — re-predicate, re-target either
// endpoint, and delete — driving the atomic `PATCH …/relations/{edge_id}` (which preserves
// the §4 handle, INV-10) and the existing `DELETE …/relations/{edge_id}`, with the human
// gate + undo intact (INV-1/3/9). Panel-only — no right-click (DM-S5-4).
//
// The read state (evidence bundle) is still owned by the container (GraphViewer's
// useEdgeEvidence) and handed in; the edit form seeds from the tapped `GraphEdge` (predicate
// + endpoints, from the graph payload) so it never waits on the evidence fetch. A re-key
// changes the content-addressed edge id, so a saved edit re-points the selection via
// `onEdited(newEdgeId, merged)` (GraphViewer) and the panel re-resolves for the new edge.
//
// The evidence quote + paragraph text + edited predicate are the author's own story text,
// rendered through React's default escaping (never dangerouslySetInnerHTML) — the standing
// stored-XSS guard the M4 reader held. A zero-provenance edge (added by hand — the write path
// creates no staged row) resolves as a 200 with an empty list: show "added manually".

import { useEffect, useState } from "react";

import { EntityPicker } from "../extraction-review/EntityPicker";
import type { EdgeEvidence } from "../../lib/api/useEdgeEvidence";
import { useRemoveRelation } from "../../lib/api/useRemoveRelation";
import { useRetargetRelation } from "../../lib/api/useRetargetRelation";
import type { GraphEdge } from "../../lib/api/useStoryGraph";
import type { EndpointDraft } from "./edgeEditForm";
import { useEdgeEditForm } from "./useEdgeEditForm";

interface EdgeEvidencePanelProps {
  /** The tapped edge id, or null when nothing is selected. */
  edgeId: string | null;
  /** The tapped edge from the graph payload (predicate + endpoints) — undefined in the brief
   * window after a re-key re-points to a new id before the graph refetch lands. */
  edge: GraphEdge | undefined;
  /** id → display name, resolved the same way the canvas labels a node (graphElements.nodeLabel). */
  nameOf: (id: string) => string;
  storyId: string;
  /** The last-known evidence bundle (kept across a background refetch, undefined until first load). */
  evidence: EdgeEvidence | undefined;
  isPending: boolean;
  /** Retry the evidence read — re-tapping the already-selected edge is a no-op, so the
   * error state needs an explicit refetch rather than a "select again" instruction. */
  onRetry: () => void;
  onClose: () => void;
  /** The edge was deleted — the host closes the panel (it no longer exists). */
  onDeleted: () => void;
  /** The edit form's dirty state changed — the canvas guard holds the selection while true. */
  onDirtyChange?: (dirty: boolean) => void;
  /** A re-key succeeded — the host re-points the selection to the new edge id (and notes a fold). */
  onEdited?: (newEdgeId: string, merged: boolean) => void;
  /** The last edit folded onto an existing edge between the pair — show the note on the re-pointed panel. */
  justMerged?: boolean;
}

const PANEL_CLASS =
  "flex min-h-0 w-72 shrink-0 flex-col gap-3 border-l border-gray-200 p-4 text-sm";

export function EdgeEvidencePanel({
  edgeId,
  edge,
  nameOf,
  storyId,
  evidence,
  isPending,
  onRetry,
  onClose,
  onDeleted,
  onDirtyChange,
  onEdited,
  justMerged = false,
}: EdgeEvidencePanelProps) {
  const retarget = useRetargetRelation(storyId, edgeId ?? "");
  const form = useEdgeEditForm(edge, nameOf);

  // Report dirty transitions to the host (canvas guard); reset on unmount so a panel torn
  // down mid-edit doesn't leave the guard stuck holding a stale selection.
  useEffect(() => {
    onDirtyChange?.(form.dirty);
  }, [form.dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);

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

  // The fold outcome is a data-changing result of the *edit*, not of the evidence read — so it
  // must surface on the re-pointed panel regardless of whether the survivor's evidence is still
  // loading or errored (an evidence-read failure must not silently hide that two edges merged).
  const mergedNote = justMerged ? (
    <p data-testid="edge-panel-merged-warning" role="alert" className="text-xs text-amber-700">
      Folded onto an existing relation between these entities.
    </p>
  ) : null;

  function startEditing() {
    retarget.reset();
    form.startEditing();
  }

  function saveEdit() {
    retarget.mutate(form.buildPatch(), {
      onSuccess: (res) => {
        form.cancel();
        onEdited?.(res.edge_id, res.merged_into_existing);
      },
    });
  }

  // Edit mode seeds from `edge`, not the evidence read, so it renders regardless of the
  // evidence fetch state (it's only ever entered from the loaded read view).
  if (form.editing) {
    return (
      <aside data-testid="edge-panel-edit" className={PANEL_CLASS}>
        {header}
        <form
          data-testid="edge-panel-edit-form"
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (form.canSave) saveEdit();
          }}
        >
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Relationship
            </span>
            <input
              data-testid="edge-panel-predicate"
              value={form.state.predicateDraft}
              onChange={(event) => form.setPredicate(event.target.value)}
              className="rounded border border-gray-300 px-2 py-1"
            />
          </label>

          <EndpointField
            label="From (subject)"
            slot="subject"
            current={form.state.subject}
            storyId={storyId}
            disabled={retarget.isPending}
            onPick={form.setSubject}
          />
          <EndpointField
            label="To (object)"
            slot="object"
            current={form.state.object}
            storyId={storyId}
            disabled={retarget.isPending}
            onPick={form.setObject}
          />

          {retarget.isError && (
            <p data-testid="edge-panel-edit-error" role="alert" className="text-xs text-red-700">
              {retarget.error.detail}
            </p>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              data-testid="edge-panel-save"
              disabled={!form.canSave || retarget.isPending}
              className="rounded bg-gray-800 px-3 py-1 text-xs text-white hover:bg-gray-700 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              data-testid="edge-panel-cancel"
              onClick={form.cancel}
              className="rounded border border-gray-300 px-3 py-1 text-xs text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </form>
      </aside>
    );
  }

  // `isPending` is only true before the first successful load (TanStack keeps `data` across a
  // background refetch), so a refetch failure with data in hand falls through to the last-good
  // evidence rather than blanking it with the error state.
  if (isPending) {
    return (
      <aside data-testid="edge-evidence-loading" className={PANEL_CLASS}>
        {header}
        {mergedNote}
        <p className="text-gray-500">Loading evidence…</p>
      </aside>
    );
  }

  if (!evidence) {
    return (
      <aside data-testid="edge-evidence-error" className={PANEL_CLASS}>
        {header}
        {mergedNote}
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
      {mergedNote}

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
        // The source paragraphs can be long — let them scroll inside this region so the header,
        // relationship, and the curation actions below stay on-screen at any panel height.
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
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

      {/* Curation affordances — only once the edge resolved in the payload (INV-1: human-gated). */}
      {storyId && edge && (
        <div className="flex flex-wrap items-center gap-2 border-t border-gray-100 pt-2">
          <button
            type="button"
            data-testid="edge-panel-edit"
            onClick={startEditing}
            className="self-start rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
          >
            Edit
          </button>
          <EdgeDeleteControl storyId={storyId} edgeId={edgeId} onDeleted={onDeleted} />
        </div>
      )}
    </aside>
  );
}

interface EndpointFieldProps {
  label: string;
  /** Namespaces the field's testids ("subject" | "object"). */
  slot: string;
  current: EndpointDraft;
  storyId: string;
  disabled: boolean;
  onPick: (endpoint: EndpointDraft) => void;
}

/** One re-target endpoint row: the current entity name + a "change" affordance opening the
 * shared EntityPicker (the reader's add-relation pick/change pattern). */
function EndpointField({ label, slot, current, storyId, disabled, onPick }: EndpointFieldProps) {
  const [picking, setPicking] = useState(false);

  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</span>
      {picking ? (
        <div className="flex flex-col gap-1">
          <EntityPicker
            storyId={storyId}
            disabled={disabled}
            onPick={(result) => {
              onPick({ entity_id: result.entity_id, canonical_name: result.canonical_name });
              setPicking(false);
            }}
          />
          <button
            type="button"
            data-testid={`edge-panel-retarget-${slot}-cancel`}
            onClick={() => setPicking(false)}
            className="self-start text-xs text-gray-400 hover:underline"
          >
            keep current
          </button>
        </div>
      ) : (
        <p className="text-xs text-gray-700">
          <span data-testid={`edge-panel-endpoint-${slot}`} className="font-medium">
            {current.canonical_name}
          </span>{" "}
          <button
            type="button"
            data-testid={`edge-panel-retarget-${slot}`}
            onClick={() => setPicking(true)}
            disabled={disabled}
            className="text-gray-400 hover:underline disabled:opacity-50"
          >
            change
          </button>
        </p>
      )}
    </div>
  );
}

interface EdgeDeleteControlProps {
  storyId: string;
  edgeId: string;
  onDeleted: () => void;
}

/** Delete-with-confirm: destructive but reversible (undo restores the edge, INV-3). */
function EdgeDeleteControl({ storyId, edgeId, onDeleted }: EdgeDeleteControlProps) {
  const [confirming, setConfirming] = useState(false);
  const removeRelation = useRemoveRelation(storyId);

  if (!confirming) {
    return (
      <button
        type="button"
        data-testid="edge-panel-delete"
        onClick={() => setConfirming(true)}
        className="self-start rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
      >
        Delete
      </button>
    );
  }

  return (
    <div data-testid="edge-panel-delete-confirm" className="flex flex-col gap-1">
      <p className="text-xs text-gray-700">Delete this relation? You can undo this.</p>
      <div className="flex gap-2">
        <button
          type="button"
          data-testid="edge-panel-delete-confirm-btn"
          disabled={removeRelation.isPending}
          onClick={() => removeRelation.mutate(edgeId, { onSuccess: onDeleted })}
          className="rounded bg-red-700 px-2 py-1 text-xs text-white hover:bg-red-600 disabled:opacity-50"
        >
          Delete
        </button>
        <button
          type="button"
          data-testid="edge-panel-delete-cancel"
          onClick={() => setConfirming(false)}
          className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
      {removeRelation.isError && (
        <p data-testid="edge-panel-delete-error" role="alert" className="text-xs text-red-700">
          {removeRelation.error.detail}
        </p>
      )}
    </div>
  );
}
