// Per-relation review card (Session 30 — M3.S4f, spec §3.3's 5th human action / §8.3).
//
// Presentational: renders one committable relation as its surface triple
// (subject — predicate → object, the strings the extractor produced and the endpoint
// returns) plus the cascade's confidence, and dispatches the author's decision up via
// `onAct`. No business logic: selection and keyboard live in RelationQueue +
// relationQueue.ts.
//
// Surface strings only (v1, firmed with the owner S30): the endpoint resolves each
// endpoint to a committed entity id but not its canonical name, so the card shows the
// extracted surface forms. Resolving the canonical names is a deferred follow-up.

import type { RelationView } from "../../lib/api/useRelations";
import type { DecideAction } from "./relationQueue";

interface RelationCardProps {
  relation: RelationView;
  isSelected: boolean;
  /** Commit or reject this relation. */
  onAct: (action: DecideAction) => void;
  /** A decision for this relation is in flight — disable the actions. */
  pending?: boolean;
}

export function RelationCard({ relation, isSelected, onAct, pending = false }: RelationCardProps) {
  return (
    <article
      data-testid="relation-card"
      data-selected={String(isSelected)}
      className={`flex flex-col gap-3 rounded-lg border p-4 text-sm ${
        isSelected ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white"
      }`}
    >
      <p data-testid="relation-triple" className="flex flex-wrap items-baseline gap-2">
        <span className="font-semibold text-gray-900">{relation.subject}</span>
        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600">
          {relation.predicate}
        </span>
        <span className="font-semibold text-gray-900">{relation.object}</span>
        {relation.confidence !== null && (
          <span className="ml-auto text-xs text-gray-400">
            confidence {relation.confidence.toFixed(2)}
          </span>
        )}
      </p>

      <footer className="flex flex-wrap gap-2">
        <button
          type="button"
          data-testid="commit-relation"
          onClick={() => onAct("commit")}
          disabled={pending}
          className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:bg-gray-300"
        >
          Commit (A)
        </button>
        <button
          type="button"
          data-testid="reject-relation"
          onClick={() => onAct("reject")}
          disabled={pending}
          className="rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
          Reject (R)
        </button>
      </footer>
    </article>
  );
}
