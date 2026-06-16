// Per-candidate review card (Session 25 — M3.S4b Stage 4, spec §3.3 / §8.3).
//
// Presentational: renders one staged candidate's review set — the quote/context
// (±200 chars, staged by the backend), the cascade's NEW-vs-MERGE proposal, the
// judge's reasoning, and the top-3 alternative entities — and dispatches the
// reviewer's action up via `onAct` / `onPickTarget`. No business logic: selection,
// keyboard, and merge-target cycling live in ReviewQueue + reviewQueue.ts.
//
// Stale alternatives: these are staged at extraction time and not re-validated here
// (see reviewQueue.ts). The container handles the 409 a vanished merge target returns.

import { useState } from "react";

import type { CandidateView } from "../../lib/api/useCandidates";
import type { EntitySearchResult } from "../../lib/api/useEntitySearch";
import { EntityPicker } from "./EntityPicker";
import { alternativesOf, type ReviewIntent } from "./reviewQueue";

interface CandidateCardProps {
  candidate: CandidateView;
  isSelected: boolean;
  /** The story whose project the handpick search is scoped to (M3.S4d). */
  storyId?: string;
  /** Index of the alternative currently picked as the merge target, or null. */
  mergeTargetIndex: number | null;
  /** Commit a decision for this candidate. */
  onAct: (intent: ReviewIntent) => void;
  /** Pick an alternative (by index) as the pending merge target. */
  onPickTarget: (index: number) => void;
  /** A decision for this candidate is in flight — disable the actions. */
  pending?: boolean;
}

export function CandidateCard({
  candidate,
  isSelected,
  storyId,
  mergeTargetIndex,
  onAct,
  onPickTarget,
  pending = false,
}: CandidateCardProps) {
  const alternatives = alternativesOf(candidate);
  const proposalTarget = alternatives.find((a) => a.entity_id === candidate.target_entity_id);
  const pickedAlternative = mergeTargetIndex !== null ? alternatives[mergeTargetIndex] : undefined;
  // A handpicked entity (searched from the whole project, M3.S4d) overrides a top-3
  // alternative: it is the more deliberate choice, and is the only way to reach a target
  // the cascade never surfaced. Both share {entity_id, canonical_name}.
  const [handpicked, setHandpicked] = useState<EntitySearchResult | null>(null);
  const mergeTarget = handpicked ?? pickedAlternative;

  return (
    <article
      data-testid="candidate-card"
      data-selected={String(isSelected)}
      className={`flex flex-col gap-3 rounded-lg border p-4 text-sm ${
        isSelected ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white"
      }`}
    >
      <header className="flex items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <h3 className="text-base font-semibold text-gray-900">{candidate.candidate_name}</h3>
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
            {candidate.type}
          </span>
        </div>
        <span
          data-testid="proposal-badge"
          className={`rounded px-2 py-0.5 text-xs font-medium ${
            candidate.proposal === "merge"
              ? "bg-amber-100 text-amber-800"
              : "bg-green-100 text-green-800"
          }`}
        >
          {candidate.proposal === "merge"
            ? // A Stage-2/3 merge targets the best embedding/judge match, which need not be
              // in the fuzzy top-3 alternatives — and CandidateView carries no target name —
              // so fall back to a generic label rather than surfacing a raw UUID. (The real
              // name lands when the backend adds target_canonical_name — see PLAN_SHORT.md.)
              `Merge → ${proposalTarget?.canonical_name ?? "an existing entity"}`
            : "New entity"}
        </span>
      </header>

      <blockquote
        data-testid="candidate-context"
        className="border-l-2 border-gray-200 pl-3 text-gray-700"
      >
        {candidate.context}
      </blockquote>

      {candidate.reasoning && (
        <p data-testid="candidate-reasoning" className="text-xs text-gray-500">
          <span className="font-medium text-gray-600">Why: </span>
          {candidate.reasoning}
          {candidate.confidence !== null && (
            <span className="ml-1 text-gray-400">
              (confidence {candidate.confidence.toFixed(2)}, stage {candidate.stage_reached})
            </span>
          )}
        </p>
      )}

      {alternatives.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Merge with instead
          </p>
          <ul className="flex flex-col gap-1">
            {alternatives.map((alt, index) => {
              // A live handpick overrides the alternatives, so none reads as the active
              // target while one is set — and picking an alternative clears the handpick,
              // so the most recent choice always wins (no stale handpick silently winning).
              const active = index === mergeTargetIndex && !handpicked;
              return (
                <li key={alt.entity_id}>
                  <button
                    type="button"
                    data-testid="candidate-alternative"
                    data-active={String(active)}
                    onClick={() => {
                      setHandpicked(null);
                      onPickTarget(index);
                    }}
                    className={`w-full rounded border px-2 py-1 text-left text-xs ${
                      active
                        ? "border-amber-400 bg-amber-50 text-amber-900"
                        : "border-gray-200 text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    {alt.canonical_name}
                    <span className="ml-1 text-gray-400">({alt.score})</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <EntityPicker storyId={storyId} onPick={setHandpicked} disabled={pending} />

      {handpicked && (
        <p data-testid="handpick-target" className="text-xs text-amber-800">
          Will merge into <span className="font-medium">{handpicked.canonical_name}</span>
        </p>
      )}

      <footer className="flex flex-wrap gap-2">
        <button
          type="button"
          data-testid="accept-proposal"
          onClick={() => onAct({ decision: "accept" })}
          disabled={pending}
          className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:bg-gray-300"
        >
          Accept (A)
        </button>
        <button
          type="button"
          data-testid="accept-create"
          onClick={() => onAct({ decision: "accept", accept: { action: "create" } })}
          disabled={pending}
          className="rounded border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          New (N)
        </button>
        <button
          type="button"
          data-testid="accept-merge"
          onClick={() =>
            mergeTarget &&
            onAct({
              decision: "accept",
              accept: { action: "merge", target_entity_id: mergeTarget.entity_id },
            })
          }
          disabled={pending || !mergeTarget}
          className="rounded border border-amber-300 px-3 py-1 text-xs font-medium text-amber-800 hover:bg-amber-50 disabled:opacity-50"
        >
          Merge (M)
        </button>
        <button
          type="button"
          data-testid="reject"
          onClick={() => onAct({ decision: "reject" })}
          disabled={pending}
          className="rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
          Reject (R)
        </button>
      </footer>
    </article>
  );
}
