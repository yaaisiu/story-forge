// The reader's story-scoped undo affordance (Session 43 — M4.S3b-fe, DM-S3b-1 see-what-I-undo;
// spec §11/§4.3 reversible deterministic undo).
//
// Undo reverses the LAST graph edit anywhere in the story — an edit, merge, or delete — so it lives
// in the reader header, not in a per-entity panel. It *previews before it reverses* (DM-S3b-1):
// click → ask the backend what would be undone (preview, graph untouched) → show the human-readable
// description → confirm → apply. Nothing left to undo shows a quiet "nothing to undo"; the graph
// drifting since (a concurrent edit) shows a reload-and-retry message (409).
//
// Two `useUndo` instances keep the preview and apply error states cleanly separate. Components
// render and dispatch: the request + cache invalidation live in `useUndo`.

import { useUndo } from "../../lib/api/useUndo";
import { ApiError } from "../../lib/api/client";

interface UndoButtonProps {
  storyId: string;
}

/** Map an undo failure to an author-facing message; statuses read off api/stories.py. */
function undoErrorMessage(error: ApiError): string {
  if (error.status === 409) return "The graph changed since — reload and try again.";
  if (error.status === 404) return "Nothing to undo.";
  return "Undo failed. Please try again.";
}

export function UndoButton({ storyId }: UndoButtonProps) {
  const preview = useUndo(storyId);
  const apply = useUndo(storyId);

  const confirming = preview.isSuccess && !apply.isSuccess;

  function startPreview() {
    apply.reset();
    preview.mutate(true);
  }

  function confirmUndo() {
    apply.mutate(false, { onSuccess: () => preview.reset() });
  }

  if (confirming) {
    return (
      <div data-testid="undo-affordance" className="flex flex-col items-end gap-1">
        <p data-testid="undo-preview" className="text-sm text-gray-700">
          Undo: {preview.data?.description}?
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            data-testid="undo-confirm"
            disabled={apply.isPending}
            onClick={confirmUndo}
            className="rounded bg-gray-800 px-3 py-1 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
          >
            Confirm undo
          </button>
          <button
            type="button"
            data-testid="undo-cancel"
            onClick={() => preview.reset()}
            className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
        {apply.isError && (
          <p data-testid="undo-error" role="alert" className="text-xs text-red-700">
            {undoErrorMessage(apply.error)}
          </p>
        )}
      </div>
    );
  }

  const nothingToUndo = preview.isError && preview.error.status === 404;

  return (
    <div data-testid="undo-affordance" className="flex flex-col items-end gap-1">
      <button
        type="button"
        data-testid="undo-button"
        disabled={preview.isPending}
        onClick={startPreview}
        className="shrink-0 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
      >
        Undo last change
      </button>
      {apply.isSuccess && (
        <p data-testid="undo-applied" role="status" className="text-xs text-green-700">
          Undid: {apply.data.description}
        </p>
      )}
      {nothingToUndo && (
        <p data-testid="undo-empty" className="text-xs text-gray-400">
          Nothing to undo.
        </p>
      )}
      {preview.isError && !nothingToUndo && (
        <p data-testid="undo-error" role="alert" className="text-xs text-red-700">
          {undoErrorMessage(preview.error)}
        </p>
      )}
    </div>
  );
}
