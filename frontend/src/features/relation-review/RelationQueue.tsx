// Relation-review queue page (Session 30 — M3.S4f, spec §3.3's 5th human action / §8.3).
//
// The human gate that turns staged relations into graph edges (INV-1 broadened to
// edges): reads a story's committable relations, renders a RelationCard per item, and
// commits the author's decision through the only edge-writing path (commit/reject). The
// keyboard scheme is the primary driver (logic in relationQueue.ts); the card buttons
// mirror it for the mouse.
//
// On a successful decision the mutation invalidates the relation queue (the decided item
// drops off) and, on a commit, the story graph (the new edge appears in the §3.4 viewer).
// A 409 means the relation was already decided — surfaced so the author moves on.
//
// Components render and dispatch; the only effect here is a keydown subscription, not a
// data fetch (frontend/src/CLAUDE.md — TanStack owns the server state).

import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api/client";
import { useDecideRelation } from "../../lib/api/useDecideRelation";
import { useRelations, type RelationView } from "../../lib/api/useRelations";
import { useReviewQueue } from "../../hooks/useReviewQueue";
import { EmptyQueueNext } from "../../components/ui/EmptyQueueNext";
import { QueueProgress } from "../../components/ui/QueueProgress";
import { RelationCard } from "./RelationCard";
import { reduceRelationKey, type DecideAction, type NavState } from "./relationQueue";

function decideMessage(error: unknown): string {
  // Neutral wording: this maps both the queue-load error and the commit/reject decision
  // error, so it must not assume one or the other (a thrown fetch — e.g. the backend
  // unreachable — is the non-ApiError case).
  if (!(error instanceof ApiError)) return "Please try again.";
  // 409 (decide): an endpoint this relation links to no longer resolves — an entity was
  // rejected or merged away after the queue loaded, so the relation stays in the queue.
  // (already-decided is NOT a 409 — the backend returns 200 with already_decided:true.)
  if (error.status === 409)
    return "An entity this relation links to is no longer available — it may have been rejected or merged.";
  if (error.status === 404) return "That relation no longer exists.";
  return error.detail || `Request failed (HTTP ${error.status}).`;
}

export function RelationQueue() {
  const { storyId } = useParams<{ storyId: string }>();
  const queue = useRelations(storyId);
  const decide = useDecideRelation(storyId ?? "");

  const relations = queue.data?.relations ?? [];

  function commit(index: number, action: DecideAction) {
    const target = relations[index];
    if (!target) return;
    decide.mutate({ relationId: target.id, action });
  }

  // Cursor + the §8.3 keyboard scheme. The key semantics live in the pure `reduceRelationKey`
  // (whose result already conforms to the hook's `intent` contract); the shared hook owns the
  // window keydown subscription and re-clamps the cursor as the queue shrinks.
  const { state: nav } = useReviewQueue<RelationView, NavState, DecideAction>({
    items: relations,
    initialState: { selectedIndex: 0 },
    reduceKey: reduceRelationKey,
    onCommit: (state, action) => commit(state.selectedIndex, action),
  });
  const selectedIndex = nav.selectedIndex;

  if (queue.isPending) {
    return (
      <main className="p-6">
        <p data-testid="relations-loading" className="text-sm text-gray-500">
          Loading relations…
        </p>
      </main>
    );
  }

  if (queue.isError) {
    return (
      <main className="p-6">
        <p data-testid="relations-error" role="alert" className="text-sm text-red-700">
          Couldn&rsquo;t load the relations. {decideMessage(queue.error)}
        </p>
      </main>
    );
  }

  return (
    <main
      data-testid="relation-queue"
      tabIndex={-1}
      className="mx-auto flex max-w-2xl flex-col gap-4 p-6 outline-none"
    >
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Decide on relations</h1>
          <p className="text-sm text-gray-600">
            Commit or reject each relation between accepted entities. Nothing is written to the
            graph until you decide. Keys: J/K move · A commit · R reject.
          </p>
          <QueueProgress selectedIndex={selectedIndex} total={relations.length} />
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

      {decide.isError && (
        <p data-testid="decide-error" role="alert" className="text-sm text-red-700">
          {decideMessage(decide.error)}
        </p>
      )}

      {relations.length === 0 ? (
        <EmptyQueueNext
          testId="relations-empty"
          message="No relations to decide — every committable relation has been resolved."
          storyId={storyId}
          next="duplicates"
          label="Review possible duplicates"
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {relations.map((relation, index) => (
            <li key={relation.id}>
              <RelationCard
                relation={relation}
                isSelected={index === selectedIndex}
                onAct={(action) => commit(index, action)}
                // Disable only the card whose decision is in flight — the author can keep
                // working the rest of the queue while one request is outstanding.
                pending={decide.isPending && decide.variables?.relationId === relation.id}
              />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
