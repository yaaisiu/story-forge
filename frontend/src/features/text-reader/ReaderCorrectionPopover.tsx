// The reader's correction input popover (M4.S3c-fe2, spec §3.5).
//
// The follow-up surface after a menu action that needs input:
//   - mode "tag"      (a free selection → "this is an entity of type X"): attach to an existing
//                     entity (reuse EntityPicker) OR create a new one (name pre-filled from the
//                     selection, free-text open-world `type` — no enum, INV-4).
//   - mode "reassign" ("not this entity" → the right one): pick the correct existing entity.
//
// Pure input collection — it gathers the author's choice and calls back; the container
// (`TextReader`) owns the mutation hooks, builds the request body, fires it, and closes on
// success (mirroring the panel's edit-mode → `useEntityEdit` split). It surfaces the container's
// pending/error state inline. `EntityPicker` is reused exactly as the panel's relation-add does.

import { useState } from "react";

import type { ApiError } from "../../lib/api/client";
import { EntityPicker } from "../extraction-review/EntityPicker";
import type { ContextMenuRequest } from "./correction";

interface ReaderCorrectionPopoverProps {
  storyId: string | undefined;
  mode: "tag" | "reassign";
  request: ContextMenuRequest;
  pending: boolean;
  error: ApiError | null;
  /** Attach to / re-assign to an existing accepted entity. */
  onSubmitExisting: (entityId: string) => void;
  /** Create a new entity of type X (mode "tag" only). */
  onSubmitNew: (name: string, type: string) => void;
  onCancel: () => void;
}

export function ReaderCorrectionPopover({
  storyId,
  mode,
  request,
  pending,
  error,
  onSubmitExisting,
  onSubmitNew,
  onCancel,
}: ReaderCorrectionPopoverProps) {
  // Tag mode toggles between attaching to an existing entity and creating a new one; re-assign
  // only ever targets an existing entity.
  const [creatingNew, setCreatingNew] = useState(false);
  const [nameDraft, setNameDraft] = useState(request.selectedText);
  const [typeDraft, setTypeDraft] = useState("");

  const title = mode === "tag" ? "Tag as entity" : "Re-assign to…";
  const newEntityValid = nameDraft.trim().length > 0 && typeDraft.trim().length > 0;

  return (
    <div
      role="dialog"
      aria-label={title}
      data-testid="reader-correction-popover"
      className="fixed z-50 w-72 rounded-md border border-gray-200 bg-white p-3 shadow-lg"
      style={{ top: request.anchor.y, left: request.anchor.x }}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-800">{title}</span>
        <button
          type="button"
          data-testid="correction-cancel"
          className="text-xs text-gray-500 hover:text-gray-700"
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>

      {mode === "tag" && (
        <div className="mb-2 flex gap-2 text-xs">
          <button
            type="button"
            data-testid="tag-mode-existing"
            className={creatingNew ? "text-gray-500" : "font-semibold text-gray-900"}
            onClick={() => setCreatingNew(false)}
          >
            Existing entity
          </button>
          <span className="text-gray-300">|</span>
          <button
            type="button"
            data-testid="tag-mode-new"
            className={creatingNew ? "font-semibold text-gray-900" : "text-gray-500"}
            onClick={() => setCreatingNew(true)}
          >
            New entity
          </button>
        </div>
      )}

      {mode === "tag" && creatingNew ? (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-xs text-gray-600">
            Name
            <input
              data-testid="new-entity-name"
              className="rounded border border-gray-300 px-2 py-1 text-sm"
              value={nameDraft}
              onChange={(event) => setNameDraft(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray-600">
            Type
            <input
              data-testid="new-entity-type"
              className="rounded border border-gray-300 px-2 py-1 text-sm"
              placeholder="e.g. character, place, artifact"
              value={typeDraft}
              onChange={(event) => setTypeDraft(event.target.value)}
            />
          </label>
          <button
            type="button"
            data-testid="new-entity-submit"
            className="rounded bg-gray-900 px-3 py-1.5 text-sm text-white disabled:opacity-40"
            disabled={!newEntityValid || pending}
            onClick={() => onSubmitNew(nameDraft.trim(), typeDraft.trim())}
          >
            Create &amp; tag
          </button>
        </div>
      ) : (
        <EntityPicker
          storyId={storyId}
          onPick={(r) => onSubmitExisting(r.entity_id)}
          disabled={pending}
        />
      )}

      {error && (
        <p data-testid="correction-error" role="alert" className="mt-2 text-xs text-red-700">
          {error.detail}
        </p>
      )}
    </div>
  );
}
