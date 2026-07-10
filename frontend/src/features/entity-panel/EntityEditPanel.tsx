// The shared entity edit/inspect panel (Graph-quality S5a, DM-S5-1(B)).
//
// Extracted from ReaderEntityPanel so the reader *and* the graph canvas compose the same
// edit core: an entity's details (type/aliases/`properties`), an Edit mode over
// name/type/aliases/properties, Merge (via the graph-generic MergeControls), and a
// reversible Delete. Each is a human-reached graph write (INV-9); the mutations invalidate
// the reader/story-graph/entity-detail triad, so a corrected name re-highlights and a new
// type recolours the canvas for free.
//
// The panel owns its own `useEntityDetail` fetch (keyed on entityId) — `GraphNode` carries
// no `properties`, so the canvas can't hand them in; and the reader's query key is shared,
// so mounting this in the reader is a cache hit, not a second request. Each consumer wraps
// it: the reader adds occurrences/relations/ego via `renderReadExtras`; the canvas passes
// the DM-S5-6 guard signals (`onDirtyChange`/`onEdited`). `testIdPrefix` keeps the reader's
// existing `reader-entity-*` test contract intact while the canvas uses `node-panel-*`.
//
// React escapes all text by default, so rendering the author's own input is safe.

import { useEffect, useState, type ReactNode } from "react";

import type { EntityDetailResponse } from "../../lib/api/useEntityDetail";
import { useEntityDetail } from "../../lib/api/useEntityDetail";
import { useDeleteEntity } from "../../lib/api/useDeleteEntity";
import { useEntityEdit } from "../../lib/api/useEntityEdit";
import { formatPropertyValue } from "./formatPropertyValue";
import { MergeControls } from "./MergeControls";
import { useEntityEditForm } from "./useEntityEditForm";
import { isRowValueValid, type PropertyKind, type PropertyRow } from "./propertiesEditor";

interface EntityEditPanelProps {
  /** Empty string means "no story known" — the write affordances hide (mirrors the reader). */
  storyId: string;
  entityId: string;
  /** Namespaces every `data-testid` (e.g. "reader-entity" | "node-panel"). */
  testIdPrefix: string;
  /** Panel width utility class (reader "w-80", canvas "w-72"). */
  widthClass?: string;
  onClose: () => void;
  /** The entity was deleted — the host closes the panel (it no longer exists). */
  onDeleted: () => void;
  /** The edit form's dirty state changed — the canvas guard holds the selection while true. */
  onDirtyChange?: (dirty: boolean) => void;
  /** An edit just succeeded — the canvas keeps the just-edited node selected through refetch. */
  onEdited?: () => void;
  /** Read-mode-only extra sections a host composes below the core (reader: occurrences etc). */
  renderReadExtras?: (detail: EntityDetailResponse) => ReactNode;
}

export function EntityEditPanel({
  storyId,
  entityId,
  testIdPrefix: p,
  widthClass = "w-72",
  onClose,
  onDeleted,
  onDirtyChange,
  onEdited,
  renderReadExtras,
}: EntityEditPanelProps) {
  const detail = useEntityDetail(storyId, entityId);
  const entityEdit = useEntityEdit(storyId, entityId);
  const form = useEntityEditForm(detail.data, Boolean(storyId));

  // Report dirty transitions to the host (canvas guard); reset the signal on unmount so a
  // panel torn down mid-edit doesn't leave the guard stuck holding a stale selection.
  useEffect(() => {
    onDirtyChange?.(form.dirty);
  }, [form.dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);

  function startEditing() {
    entityEdit.reset();
    form.startEditing();
  }

  function saveEdit(language: string) {
    entityEdit.mutate(form.buildPatch(language), {
      onSuccess: () => {
        form.cancel();
        onEdited?.();
      },
    });
  }

  return (
    <aside
      data-testid={`${p}-panel`}
      className={`flex min-h-0 ${widthClass} shrink-0 flex-col gap-3 overflow-y-auto border-l border-gray-200 p-4 text-sm`}
    >
      <div className="flex items-start justify-between gap-2">
        <h2 data-testid={`${p}-name`} className="text-base font-semibold text-gray-900">
          {detail.data?.canonical_name ?? "Entity"}
        </h2>
        <button
          type="button"
          data-testid={`${p}-close`}
          onClick={onClose}
          aria-label="Close entity panel"
          className="rounded px-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        >
          ✕
        </button>
      </div>

      {detail.isPending && (
        <p data-testid={`${p}-loading`} className="text-gray-500">
          Loading entity…
        </p>
      )}
      {detail.isError && (
        <p data-testid={`${p}-error`} role="alert" className="text-red-700">
          Couldn&rsquo;t load this entity.
        </p>
      )}

      {detail.isSuccess && !form.editing && (
        <>
          <dl className="flex flex-col gap-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Type</dt>
              <dd data-testid={`${p}-type`} className="text-gray-800">
                {detail.data.type}
              </dd>
            </div>

            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Aliases</dt>
              <dd data-testid={`${p}-aliases`} className="text-gray-800">
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
              <dd data-testid={`${p}-properties`} className="text-gray-800">
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
                data-testid={`${p}-edit`}
                onClick={startEditing}
                className="self-start rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
              >
                Edit
              </button>
              <MergeControls
                storyId={storyId}
                survivorId={entityId}
                survivorName={detail.data.canonical_name}
                survivorProperties={detail.data.properties}
              />
              <DeleteControl
                storyId={storyId}
                entityId={entityId}
                name={detail.data.canonical_name}
                testIdPrefix={p}
                onDeleted={onDeleted}
              />
            </div>
          )}

          {renderReadExtras?.(detail.data)}
        </>
      )}

      {detail.isSuccess && form.editing && (
        <form
          data-testid={`${p}-edit-form`}
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (form.canSave) saveEdit(detail.data.language);
          }}
        >
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Name</span>
            <input
              data-testid={`${p}-name-input`}
              value={form.state.nameDraft}
              onChange={(event) => form.setName(event.target.value)}
              className="rounded border border-gray-300 px-2 py-1"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Type</span>
            <input
              data-testid={`${p}-type-input`}
              value={form.state.typeDraft}
              onChange={(event) => form.setType(event.target.value)}
              className="rounded border border-gray-300 px-2 py-1"
            />
          </label>

          <fieldset className="flex flex-col gap-1">
            <legend className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Aliases
            </legend>
            {form.state.aliasDrafts.map((alias, index) => (
              <div key={index} className="flex gap-1">
                <input
                  data-testid={`${p}-alias-input`}
                  value={alias}
                  onChange={(event) =>
                    form.setAliases((prev) =>
                      prev.map((a, i) => (i === index ? event.target.value : a)),
                    )
                  }
                  className="flex-1 rounded border border-gray-300 px-2 py-1"
                />
                <button
                  type="button"
                  data-testid={`${p}-alias-remove`}
                  aria-label="Remove alias"
                  onClick={() => form.setAliases((prev) => prev.filter((_, i) => i !== index))}
                  className="rounded border border-gray-300 px-2 text-gray-500 hover:bg-gray-50"
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              type="button"
              data-testid={`${p}-alias-add`}
              onClick={() => form.setAliases((prev) => [...prev, ""])}
              className="self-start rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
            >
              + alias
            </button>
          </fieldset>

          <fieldset className="flex flex-col gap-1">
            <legend className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Properties
            </legend>
            {form.state.propRows.map((rowItem, index) => {
              const invalid = !isRowValueValid(rowItem);
              const setRow = (next: Partial<PropertyRow>) =>
                form.setPropRows((prev) =>
                  prev.map((r, i) => (i === index ? { ...r, ...next } : r)),
                );
              return (
                <div key={index} className="flex flex-col gap-1 border-b border-gray-100 pb-1">
                  <div className="flex gap-1">
                    <input
                      data-testid={`${p}-prop-key`}
                      value={rowItem.key}
                      placeholder="key"
                      onChange={(event) => setRow({ key: event.target.value })}
                      className="w-1/3 rounded border border-gray-300 px-2 py-1"
                    />
                    <select
                      data-testid={`${p}-prop-kind`}
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
                      data-testid={`${p}-prop-remove`}
                      aria-label="Remove property"
                      onClick={() => form.setPropRows((prev) => prev.filter((_, i) => i !== index))}
                      className="rounded border border-gray-300 px-2 text-gray-500 hover:bg-gray-50"
                    >
                      ✕
                    </button>
                  </div>
                  {rowItem.kind === "boolean" ? (
                    <select
                      data-testid={`${p}-prop-value`}
                      value={rowItem.value === "true" ? "true" : "false"}
                      onChange={(event) => setRow({ value: event.target.value })}
                      className="rounded border border-gray-300 px-2 py-1"
                    >
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : (
                    <input
                      data-testid={`${p}-prop-value`}
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
              data-testid={`${p}-prop-add`}
              onClick={() =>
                form.setPropRows((prev) => [...prev, { key: "", value: "", kind: "string" }])
              }
              className="self-start rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
            >
              + property
            </button>
          </fieldset>

          {entityEdit.isError && (
            <p data-testid={`${p}-edit-error`} role="alert" className="text-xs text-red-700">
              {entityEdit.error.detail}
            </p>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              data-testid={`${p}-save`}
              disabled={!form.canSave || entityEdit.isPending}
              className="rounded bg-gray-800 px-3 py-1 text-xs text-white hover:bg-gray-700 disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              data-testid={`${p}-cancel`}
              onClick={form.cancel}
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

interface DeleteControlProps {
  storyId: string;
  entityId: string;
  name: string;
  testIdPrefix: string;
  onDeleted: () => void;
}

/** Delete-with-confirm: destructive but reversible (undo restores the full entity, DM-S3b-1). */
function DeleteControl({
  storyId,
  entityId,
  name,
  testIdPrefix: p,
  onDeleted,
}: DeleteControlProps) {
  const [confirming, setConfirming] = useState(false);
  const deleteEntity = useDeleteEntity(storyId);

  if (!confirming) {
    return (
      <button
        type="button"
        data-testid={`${p}-delete`}
        onClick={() => setConfirming(true)}
        className="self-start rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
      >
        Delete
      </button>
    );
  }

  return (
    <div data-testid={`${p}-delete-confirm`} className="flex flex-col gap-1">
      <p className="text-xs text-gray-700">Delete {name}? You can undo this.</p>
      <div className="flex gap-2">
        <button
          type="button"
          data-testid={`${p}-delete-confirm-btn`}
          disabled={deleteEntity.isPending}
          onClick={() => deleteEntity.mutate(entityId, { onSuccess: onDeleted })}
          className="rounded bg-red-700 px-2 py-1 text-xs text-white hover:bg-red-600 disabled:opacity-50"
        >
          Delete
        </button>
        <button
          type="button"
          data-testid={`${p}-delete-cancel`}
          onClick={() => setConfirming(false)}
          className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
      {deleteEntity.isError && (
        <p data-testid={`${p}-delete-error`} role="alert" className="text-xs text-red-700">
          {deleteEntity.error.detail}
        </p>
      )}
    </div>
  );
}
