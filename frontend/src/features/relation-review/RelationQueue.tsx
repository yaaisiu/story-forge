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

import { useEffect, useState } from "react";

import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api/client";
import { useDecideRelation } from "../../lib/api/useDecideRelation";
import { useRelations } from "../../lib/api/useRelations";
import { RelationCard } from "./RelationCard";
import { reduceRelationKey, type DecideAction, type NavState } from "./relationQueue";

/** True when a keystroke is destined for an editable field, so the window-bound
 * keyboard scheme should leave it alone. */
function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT" ||
    target.isContentEditable
  );
}

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

  const [nav, setNav] = useState<NavState>({ selectedIndex: 0 });

  const relations = queue.data?.relations ?? [];
  // The list shrinks as decisions land; keep the selection in range.
  const selectedIndex = Math.min(nav.selectedIndex, Math.max(0, relations.length - 1));

  function commit(index: number, action: DecideAction) {
    const target = relations[index];
    if (!target) return;
    decide.mutate({ relationId: target.id, action });
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      // The scheme is bound at the window, so skip it when the user is typing into a
      // field — else J/K/A/R would hijack their input.
      if (isEditableTarget(event.target)) return;
      const result = reduceRelationKey(event.key, { selectedIndex }, relations);
      if (!result) return;
      event.preventDefault();
      setNav(result.state);
      if (result.action) commit(result.state.selectedIndex, result.action);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // No deps array is intentional: `relations`/`selectedIndex` are read inside, so
    // re-binding each render keeps the closure fresh (cost is negligible at this scale).
  });

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
        <p data-testid="relations-empty" className="text-sm text-gray-500">
          No relations to decide — every committable relation has been resolved.
        </p>
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
