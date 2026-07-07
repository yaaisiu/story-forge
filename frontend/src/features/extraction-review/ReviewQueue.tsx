// Review-queue page (Session 25 — M3.S4b Stage 4, spec §3.3 / §8.3).
//
// The human gate that turns staged candidates into graph entities (INV-1): reads the
// pending queue, renders a CandidateCard per item, and commits the reviewer's decision
// through the only graph-writing path (accept/reject). The §8.3 keyboard scheme is the
// primary driver (logic in reviewQueue.ts); the card buttons mirror it for the mouse.
//
// On a successful decision the mutation invalidates the queue (the decided item drops
// off) and the story graph (it fills as the author commits). A 409 means the staged
// merge target went stale between extraction and review — surfaced so the reviewer
// picks another alternative.
//
// Components render and dispatch; the only effect here is a keydown subscription, not a
// data fetch (frontend/src/CLAUDE.md — TanStack owns the server state).

import { useParams } from "react-router-dom";

import { ApiError } from "../../lib/api/client";
import { useCandidates, type CandidateView } from "../../lib/api/useCandidates";
import { useReviewCandidate } from "../../lib/api/useReviewCandidate";
import { useReviewQueue } from "../../hooks/useReviewQueue";
import { CandidateCard } from "./CandidateCard";
import { reduceReviewKey, type NavState, type ReviewIntent } from "./reviewQueue";

function reviewMessage(error: unknown): string {
  // Neutral wording: this maps both the queue-load error and the accept/reject decision
  // error, so it must not assume one or the other (a thrown fetch — e.g. the backend
  // unreachable — is the non-ApiError case).
  if (!(error instanceof ApiError)) return "Please try again.";
  if (error.status === 409) return "That merge target no longer exists — pick another alternative.";
  if (error.status === 404) return "That candidate was already decided.";
  return error.detail || `Request failed (HTTP ${error.status}).`;
}

export function ReviewQueue() {
  const { storyId } = useParams<{ storyId: string }>();
  const queue = useCandidates(storyId);
  const review = useReviewCandidate(storyId ?? "");

  const candidates = queue.data?.candidates ?? [];

  function commit(index: number, intent: ReviewIntent) {
    const target = candidates[index];
    if (!target) return;
    review.mutate({ candidateId: target.id, ...intent });
  }

  // Cursor + the §8.3 keyboard scheme. The key semantics live in the pure `reduceReviewKey`;
  // the shared hook owns the window keydown subscription and re-clamps the cursor as the
  // queue shrinks under committed decisions. The handpick search box (EntityPicker) is left
  // alone (isEditableTarget) so typing never triggers J/K/A/N/M/R.
  const { state: nav, setState: setNav } = useReviewQueue<CandidateView, NavState, ReviewIntent>({
    items: candidates,
    initialState: { selectedIndex: 0, mergeTargetIndex: null },
    reduceKey: reduceReviewKey,
    onCommit: (state, intent) => commit(state.selectedIndex, intent),
  });
  const selectedIndex = nav.selectedIndex;

  if (queue.isPending) {
    return (
      <main className="p-6">
        <p data-testid="queue-loading" className="text-sm text-gray-500">
          Loading review queue…
        </p>
      </main>
    );
  }

  if (queue.isError) {
    return (
      <main className="p-6">
        <p data-testid="queue-error" role="alert" className="text-sm text-red-700">
          Couldn&rsquo;t load the review queue. {reviewMessage(queue.error)}
        </p>
      </main>
    );
  }

  return (
    <main
      data-testid="review-queue"
      tabIndex={-1}
      className="mx-auto flex max-w-2xl flex-col gap-4 p-6 outline-none"
    >
      <header>
        <h1 className="text-2xl font-semibold">Review queue</h1>
        <p className="text-sm text-gray-600">
          Accept, retarget, or reject each staged candidate. Nothing enters the graph until you
          decide. Keys: J/K move · A accept · N new · M merge · R reject.
        </p>
      </header>

      {review.isError && (
        <p data-testid="review-error" role="alert" className="text-sm text-red-700">
          {reviewMessage(review.error)}
        </p>
      )}

      {candidates.length === 0 ? (
        <p data-testid="queue-empty" className="text-sm text-gray-500">
          Nothing to review — every candidate has been decided.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {candidates.map((candidate, index) => (
            <li key={candidate.id}>
              <CandidateCard
                candidate={candidate}
                isSelected={index === selectedIndex}
                storyId={storyId}
                mergeTargetIndex={index === selectedIndex ? nav.mergeTargetIndex : null}
                onAct={(intent) => commit(index, intent)}
                onPickTarget={(altIndex) =>
                  setNav({ selectedIndex: index, mergeTargetIndex: altIndex })
                }
                // Disable only the card whose decision is in flight — the reviewer can
                // keep working the rest of the queue while one request is outstanding.
                pending={review.isPending && review.variables?.candidateId === candidate.id}
              />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
