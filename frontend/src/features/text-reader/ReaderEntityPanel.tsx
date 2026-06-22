// The reader's entity side panel (Session 35 — M4.S2b read-only; Session 38 — M4.S3a-fe edit).
//
// Opens when the author clicks a highlight in the prose: an inspection of that accepted
// entity — its details (canonical_name, type, aliases), free-form `properties` (DM-SP-5),
// a 1-hop ego-graph mini-view (DM-SP-4), and a timeline of its occurrences in *this* story's
// prose (DM-SP-3). Tapping a neighbour re-targets the panel; clicking an occurrence drills
// back to the paragraph.
//
// M4.S3a-fe adds the *write* affordances (spec §3.4/§3.5 manual correction — the first
// reader→graph mutation): an Edit mode over name/type/aliases/`properties`, and a relations
// section that adds (via the reused EntityPicker) and removes edges. Each is a human-reached
// graph write (INV-9 as reworded — ADR 0006); the mutations invalidate the reader/graph/detail
// so a corrected name re-highlights and a new type recolours for free (DM-S3a-4). Name editing
// is a single field writing the project-language slot (one language per project at PoC —
// spec §10 q8, owner 2026-06-19).
//
// React escapes all text by default, so rendering the author's own input is safe — no
// dangerouslySetInnerHTML (the proposal's Layer 7). Components render and dispatch: the
// properties row logic lives in the pure `propertiesEditor`, the bundle in `useEntityDetail`.

import { useMemo, useState } from "react";

import { EntityPicker } from "../extraction-review/EntityPicker";
import type { EntitySearchResult } from "../../lib/api/useEntitySearch";
import type { ReaderParagraph } from "../../lib/api/useReader";
import { useAddRelation } from "../../lib/api/useAddRelation";
import { useDeleteEntity } from "../../lib/api/useDeleteEntity";
import { useEntityDetail, type EntityDetailResponse } from "../../lib/api/useEntityDetail";
import { useEntityEdit, type EntityEditPatch } from "../../lib/api/useEntityEdit";
import { useRemoveRelation } from "../../lib/api/useRemoveRelation";
import { EgoGraphCanvas } from "./EgoGraphCanvas";
import { MergeControls } from "./MergeControls";
import { egoNeighbourLabel } from "./egoElements";
import { entityOccurrences } from "./occurrences";
import {
  isRowValueValid,
  rowsToProperties,
  toPropertyRows,
  type PropertyKind,
  type PropertyRow,
} from "./propertiesEditor";

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

/** Render an open-world property value defensively: strings as-is, anything else stringified. */
function formatPropertyValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** Build the name half of an edit patch: write the single field to the project-language slot. */
function namePatch(language: string, name: string): EntityEditPatch {
  return language === "pl" ? { canonical_name_pl: name } : { canonical_name_en: name };
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
  const detail = useEntityDetail(storyId, entityId);
  const sid = storyId ?? "";
  const entityEdit = useEntityEdit(sid, entityId);

  const [editing, setEditing] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [typeDraft, setTypeDraft] = useState("");
  const [aliasDrafts, setAliasDrafts] = useState<string[]>([]);
  const [propRows, setPropRows] = useState<PropertyRow[]>([]);

  // DM-SP-3: occurrences are the entity's *rendered highlights* across the reader's
  // paragraphs, so the timeline always agrees with the visible prose. Derived from data
  // already on the page — no extra fetch.
  const occurrences = useMemo(
    () => entityOccurrences(paragraphs, entityId),
    [paragraphs, entityId],
  );

  function startEditing(data: EntityDetailResponse) {
    setNameDraft(data.canonical_name);
    setTypeDraft(data.type);
    setAliasDrafts([...data.aliases]);
    setPropRows(toPropertyRows(data.properties));
    entityEdit.reset();
    setEditing(true);
  }

  function saveEdit(language: string) {
    const patch: EntityEditPatch = {
      ...namePatch(language, nameDraft.trim()),
      type: typeDraft.trim(),
      aliases: aliasDrafts.map((a) => a.trim()).filter(Boolean),
      properties: rowsToProperties(propRows),
    };
    entityEdit.mutate(patch, { onSuccess: () => setEditing(false) });
  }

  const canSave =
    Boolean(storyId) &&
    nameDraft.trim() !== "" &&
    typeDraft.trim() !== "" &&
    propRows.every(isRowValueValid);

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

      {detail.isSuccess && !editing && (
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

          {storyId && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                data-testid="reader-entity-edit"
                onClick={() => startEditing(detail.data)}
                className="self-start rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
              >
                Edit
              </button>
              <MergeControls
                storyId={sid}
                survivorId={entityId}
                survivorName={detail.data.canonical_name}
                survivorProperties={detail.data.properties}
              />
              <DeleteControl
                storyId={sid}
                entityId={entityId}
                name={detail.data.canonical_name}
                onDeleted={onDeleted}
              />
            </div>
          )}

          <RelationsSection
            storyId={sid}
            entityId={entityId}
            detail={detail.data}
            onSelectEntity={onSelectEntity}
          />

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

      {detail.isSuccess && editing && (
        <form
          data-testid="reader-entity-edit-form"
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (canSave) saveEdit(detail.data.language);
          }}
        >
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Name</span>
            <input
              data-testid="reader-entity-name-input"
              value={nameDraft}
              onChange={(event) => setNameDraft(event.target.value)}
              className="rounded border border-gray-300 px-2 py-1"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Type</span>
            <input
              data-testid="reader-entity-type-input"
              value={typeDraft}
              onChange={(event) => setTypeDraft(event.target.value)}
              className="rounded border border-gray-300 px-2 py-1"
            />
          </label>

          <fieldset className="flex flex-col gap-1">
            <legend className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Aliases
            </legend>
            {aliasDrafts.map((alias, index) => (
              <div key={index} className="flex gap-1">
                <input
                  data-testid="reader-entity-alias-input"
                  value={alias}
                  onChange={(event) =>
                    setAliasDrafts((prev) =>
                      prev.map((a, i) => (i === index ? event.target.value : a)),
                    )
                  }
                  className="flex-1 rounded border border-gray-300 px-2 py-1"
                />
                <button
                  type="button"
                  data-testid="reader-entity-alias-remove"
                  aria-label="Remove alias"
                  onClick={() => setAliasDrafts((prev) => prev.filter((_, i) => i !== index))}
                  className="rounded border border-gray-300 px-2 text-gray-500 hover:bg-gray-50"
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              type="button"
              data-testid="reader-entity-alias-add"
              onClick={() => setAliasDrafts((prev) => [...prev, ""])}
              className="self-start rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
            >
              + alias
            </button>
          </fieldset>

          <fieldset className="flex flex-col gap-1">
            <legend className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Properties
            </legend>
            {propRows.map((rowItem, index) => {
              const invalid = !isRowValueValid(rowItem);
              const setRow = (next: Partial<PropertyRow>) =>
                setPropRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...next } : r)));
              return (
                <div key={index} className="flex flex-col gap-1 border-b border-gray-100 pb-1">
                  <div className="flex gap-1">
                    <input
                      data-testid="reader-entity-prop-key"
                      value={rowItem.key}
                      placeholder="key"
                      onChange={(event) => setRow({ key: event.target.value })}
                      className="w-1/3 rounded border border-gray-300 px-2 py-1"
                    />
                    <select
                      data-testid="reader-entity-prop-kind"
                      value={rowItem.kind}
                      onChange={(event) => setRow({ kind: event.target.value as PropertyKind })}
                      className="rounded border border-gray-300 px-1 py-1"
                    >
                      <option value="string">text</option>
                      <option value="number">number</option>
                      <option value="boolean">bool</option>
                      <option value="json">json</option>
                    </select>
                    <button
                      type="button"
                      data-testid="reader-entity-prop-remove"
                      aria-label="Remove property"
                      onClick={() => setPropRows((prev) => prev.filter((_, i) => i !== index))}
                      className="rounded border border-gray-300 px-2 text-gray-500 hover:bg-gray-50"
                    >
                      ✕
                    </button>
                  </div>
                  {rowItem.kind === "boolean" ? (
                    <select
                      data-testid="reader-entity-prop-value"
                      value={rowItem.value === "true" ? "true" : "false"}
                      onChange={(event) => setRow({ value: event.target.value })}
                      className="rounded border border-gray-300 px-2 py-1"
                    >
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : (
                    <input
                      data-testid="reader-entity-prop-value"
                      value={rowItem.value}
                      readOnly={rowItem.kind === "json"}
                      onChange={(event) => setRow({ value: event.target.value })}
                      className={`rounded border px-2 py-1 ${
                        invalid ? "border-red-400" : "border-gray-300"
                      } ${rowItem.kind === "json" ? "bg-gray-50 text-gray-500" : ""}`}
                    />
                  )}
                </div>
              );
            })}
            <button
              type="button"
              data-testid="reader-entity-prop-add"
              onClick={() =>
                setPropRows((prev) => [...prev, { key: "", value: "", kind: "string" }])
              }
              className="self-start rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
            >
              + property
            </button>
          </fieldset>

          {entityEdit.isError && (
            <p data-testid="reader-entity-edit-error" role="alert" className="text-xs text-red-700">
              {entityEdit.error.detail}
            </p>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              data-testid="reader-entity-save"
              disabled={!canSave || entityEdit.isPending}
              className="rounded bg-gray-800 px-3 py-1 text-xs text-white hover:bg-gray-700 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              data-testid="reader-entity-cancel"
              onClick={() => setEditing(false)}
              className="rounded border border-gray-300 px-3 py-1 text-xs text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </aside>
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

interface DeleteControlProps {
  storyId: string;
  entityId: string;
  name: string;
  onDeleted: () => void;
}

/** Delete-with-confirm: destructive but reversible (undo restores the full entity, DM-S3b-1). */
function DeleteControl({ storyId, entityId, name, onDeleted }: DeleteControlProps) {
  const [confirming, setConfirming] = useState(false);
  const deleteEntity = useDeleteEntity(storyId);

  if (!confirming) {
    return (
      <button
        type="button"
        data-testid="reader-entity-delete"
        onClick={() => setConfirming(true)}
        className="self-start rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
      >
        Delete
      </button>
    );
  }

  return (
    <div data-testid="reader-entity-delete-confirm" className="flex flex-col gap-1">
      <p className="text-xs text-gray-700">Delete {name}? You can undo this.</p>
      <div className="flex gap-2">
        <button
          type="button"
          data-testid="reader-entity-delete-confirm-btn"
          disabled={deleteEntity.isPending}
          onClick={() => deleteEntity.mutate(entityId, { onSuccess: onDeleted })}
          className="rounded bg-red-700 px-2 py-1 text-xs text-white hover:bg-red-600 disabled:opacity-50"
        >
          Delete
        </button>
        <button
          type="button"
          data-testid="reader-entity-delete-cancel"
          onClick={() => setConfirming(false)}
          className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
      {deleteEntity.isError && (
        <p data-testid="reader-entity-delete-error" role="alert" className="text-xs text-red-700">
          {deleteEntity.error.detail}
        </p>
      )}
    </div>
  );
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
