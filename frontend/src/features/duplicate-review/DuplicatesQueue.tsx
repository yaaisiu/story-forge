// Possible-duplicates review list (Session 79 — Graph-quality S4b, DM-CD-4).
//
// The dedicated "work down the suggestions" surface: reads a story's ranked likely-duplicate
// pairs and lets the author accept (→ the existing merge) or dismiss each. Suggests only — the
// human commits every merge (INV-1/INV-9). Dismiss + un-dismiss (DM-CD-3) live here rather than
// in the card so the transient Undo survives the card unmounting when the list refetches.
//
// Components render and dispatch: the keyboard scheme is the pure reduceDuplicateKey via the
// shared useReviewQueue hook; the card owns the merge mini-form.

import { useState } from "react";

import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api/client";
import {
  useDuplicateSuggestions,
  type DuplicateSuggestionView,
} from "../../lib/api/useDuplicateSuggestions";
import { useDismissDuplicate, useUndismissDuplicate } from "../../lib/api/useDismissDuplicate";
import { useReviewQueue } from "../../hooks/useReviewQueue";
import { DuplicatePairCard } from "./DuplicatePairCard";
import {
  pairKey,
  reduceDuplicateKey,
  type DuplicateIntent,
  type NavState,
} from "./duplicateReview";

function duplicatesMessage(error: unknown): string {
  // Maps both the list-load error and the dismiss/un-dismiss error; a thrown fetch (backend
  // unreachable) is the non-ApiError case. Status meanings are read off api/stories.py: the
  // duplicate-suggestions routes raise 404 (story) and 503 (a data store), never 409/400.
  if (!(error instanceof ApiError)) return "Please try again.";
  if (error.status === 404) return "This story no longer exists.";
  if (error.status === 503)
    return "The duplicate-suggestion data is temporarily unavailable — try again shortly.";
  return error.detail || `Request failed (HTTP ${error.status}).`;
}

function pairName(suggestion: DuplicateSuggestionView): string {
  return `${suggestion.entity_a.canonical_name} & ${suggestion.entity_b.canonical_name}`;
}

export function DuplicatesQueue() {
  const { storyId } = useParams<{ storyId: string }>();
  const suggestions = useDuplicateSuggestions(storyId);
  const dismiss = useDismissDuplicate(storyId ?? "");
  const undismiss = useUndismissDuplicate(storyId ?? "");

  // The most recently dismissed pair, kept so the author can undo the "no" (DM-CD-3 reversal)
  // after the list has already refetched without it.
  const [lastDismissed, setLastDismissed] = useState<DuplicateSuggestionView | null>(null);

  const items = suggestions.data?.suggestions ?? [];

  function dismissAt(index: number) {
    const target = items[index];
    if (!target) return;
    dismiss.mutate(
      { entityIdA: target.entity_a.entity_id, entityIdB: target.entity_b.entity_id },
      { onSuccess: () => setLastDismissed(target) },
    );
  }

  const { state: nav, setState: setNav } = useReviewQueue<
    DuplicateSuggestionView,
    NavState,
    DuplicateIntent
  >({
    items,
    initialState: { selectedIndex: 0 },
    reduceKey: reduceDuplicateKey,
    onCommit: (state) => dismissAt(state.selectedIndex),
  });
  const selectedIndex = nav.selectedIndex;

  function undoDismiss() {
    if (!lastDismissed) return;
    undismiss.mutate(
      {
        entityIdA: lastDismissed.entity_a.entity_id,
        entityIdB: lastDismissed.entity_b.entity_id,
      },
      { onSuccess: () => setLastDismissed(null) },
    );
  }

  if (suggestions.isPending) {
    return (
      <main className="p-6">
        <p data-testid="duplicates-loading" className="text-sm text-gray-500">
          Finding possible duplicates…
        </p>
      </main>
    );
  }

  if (suggestions.isError) {
    return (
      <main className="p-6">
        <p data-testid="duplicates-error" role="alert" className="text-sm text-red-700">
          Couldn&rsquo;t load possible duplicates. {duplicatesMessage(suggestions.error)}
        </p>
      </main>
    );
  }

  return (
    <main
      data-testid="duplicates-list"
      tabIndex={-1}
      className="mx-auto flex max-w-2xl flex-col gap-4 p-6 outline-none"
    >
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">
            Possible duplicates
            <span data-testid="duplicates-count" className="ml-2 text-lg font-normal text-gray-500">
              {items.length}
            </span>
          </h1>
          <p className="text-sm text-gray-600">
            {items.length} pair{items.length === 1 ? "" : "s"} left to review. Entities that look
            like the same thing — pick which one to keep and merge, or dismiss the pair. Nothing is
            merged until you decide. Keys: J/K move · D dismiss.
          </p>
        </div>
        {storyId && (
          <Link
            to={`/stories/${storyId}/graph`}
            data-testid="graph-link"
            className="shrink-0 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Graph
          </Link>
        )}
      </header>

      {lastDismissed && (
        <p
          data-testid="duplicates-undo"
          role="status"
          className="flex items-center gap-2 text-sm text-gray-600"
        >
          Dismissed {pairName(lastDismissed)}.
          <button
            type="button"
            data-testid="duplicates-undo-button"
            onClick={undoDismiss}
            disabled={undismiss.isPending}
            className="rounded border border-gray-300 px-2 py-0.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Undo
          </button>
        </p>
      )}

      {dismiss.isError && (
        <p data-testid="duplicates-dismiss-error" role="alert" className="text-sm text-red-700">
          {duplicatesMessage(dismiss.error)}
        </p>
      )}

      {undismiss.isError && (
        <p data-testid="duplicates-undismiss-error" role="alert" className="text-sm text-red-700">
          Couldn&rsquo;t undo the dismissal. {duplicatesMessage(undismiss.error)}
        </p>
      )}

      {items.length === 0 ? (
        <p data-testid="duplicates-empty" className="text-sm text-gray-500">
          No possible duplicates — the accepted entities all look distinct.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((suggestion, index) => (
            <li key={pairKey(suggestion.entity_a.entity_id, suggestion.entity_b.entity_id)}>
              <DuplicatePairCard
                storyId={storyId ?? ""}
                suggestion={suggestion}
                isSelected={index === selectedIndex}
                onSelect={() => setNav({ selectedIndex: index })}
                onDismiss={() => dismissAt(index)}
                dismissPending={
                  dismiss.isPending &&
                  dismiss.variables?.entityIdA === suggestion.entity_a.entity_id &&
                  dismiss.variables?.entityIdB === suggestion.entity_b.entity_id
                }
              />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
