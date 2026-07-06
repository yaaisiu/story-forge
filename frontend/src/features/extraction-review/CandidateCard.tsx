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
import { alternativesOf, exactNameDuplicates, type ReviewIntent } from "./reviewQueue";

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

  // DM-EE-5: if the reviewer clicks "New" for a name that already exists among the
  // loaded alternatives, warn and offer the merge before creating a duplicate — never a
  // hard block (INV-1). The warning is opened by the New button; "Create anyway" and
  // "Merge instead" resolve it. A one-click "Merge instead" only appears when there is a
  // *single* same-named entity: two distinct entities can share a name (DM-EE-4's "two
  // crews" trap), so an ambiguous match defers to a manual pick from the list above rather
  // than silently merging into an arbitrary one. (The keyboard `N` path in reduceReviewKey
  // stays a direct create — the guard rides the discoverable button; the rare power-user
  // bypass is a documented limitation, not a block.)
  const duplicates = exactNameDuplicates(candidate);
  const soleDuplicate = duplicates.length === 1 ? duplicates[0] : null;
  const [dupWarnOpen, setDupWarnOpen] = useState(false);

  function handleNewClick() {
    if (duplicates.length > 0) {
      setDupWarnOpen(true);
      return;
    }
    onAct({ decision: "accept", accept: { action: "create" } });
  }

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
            ? // The backend resolves the target's name (DM-EE-3); a Stage-2/3 merge can
              // target an entity outside the fuzzy top-3, so fall back to a top-3 match's
              // name, then a generic label (never a raw UUID). `target_canonical_name` is
              // null-tolerant — a graph-DB outage degrades enrichment to null.
              `Merge → ${
                candidate.target_canonical_name ??
                proposalTarget?.canonical_name ??
                "an existing entity"
              }`
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
                    className={`flex w-full flex-col gap-0.5 rounded border px-2 py-1 text-left text-xs ${
                      active
                        ? "border-amber-400 bg-amber-50 text-amber-900"
                        : "border-gray-200 text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="font-medium">{alt.canonical_name}</span>
                      {/* Label the RapidFuzz score honestly as a *name* match, never an
                          identity verdict — a 100 can still be two different things
                          (DM-EE-4). The context below is how the author disambiguates. */}
                      <span className="shrink-0 text-gray-400">name match {alt.score}</span>
                    </span>
                    {(alt.type || alt.aliases.length > 0) && (
                      <span data-testid="alternative-identity" className="text-gray-500">
                        {alt.type ?? "unknown type"}
                        {alt.aliases.length > 0 && ` · aka ${alt.aliases.join(", ")}`}
                      </span>
                    )}
                    {alt.context_quote && (
                      <span data-testid="alternative-quote" className="italic text-gray-500">
                        “{alt.context_quote}”
                      </span>
                    )}
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

      {dupWarnOpen && duplicates.length > 0 && (
        <div
          data-testid="dup-warning"
          role="alert"
          className="flex flex-col gap-2 rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900"
        >
          {soleDuplicate ? (
            <p>
              An entity named <span className="font-medium">{soleDuplicate.canonical_name}</span>{" "}
              already exists. Merge into it instead of creating a duplicate?
            </p>
          ) : (
            // Several same-named entities exist — don't guess which the reviewer means;
            // point them at the list above to pick the intended target explicitly.
            <p>
              {duplicates.length} entities named{" "}
              <span className="font-medium">{candidate.candidate_name}</span> already exist. Pick
              the intended one under &ldquo;Merge with instead&rdquo; above, or create a duplicate.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {soleDuplicate && (
              <button
                type="button"
                data-testid="dup-warning-merge"
                onClick={() => {
                  setDupWarnOpen(false);
                  onAct({
                    decision: "accept",
                    accept: { action: "merge", target_entity_id: soleDuplicate.entity_id },
                  });
                }}
                disabled={pending}
                className="rounded border border-amber-400 px-2 py-1 font-medium text-amber-900 hover:bg-amber-100 disabled:opacity-50"
              >
                Merge instead
              </button>
            )}
            <button
              type="button"
              data-testid="dup-warning-create"
              onClick={() => {
                setDupWarnOpen(false);
                onAct({ decision: "accept", accept: { action: "create" } });
              }}
              disabled={pending}
              className="rounded border border-gray-300 px-2 py-1 text-gray-700 hover:bg-gray-100 disabled:opacity-50"
            >
              Create anyway
            </button>
          </div>
        </div>
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
          onClick={handleNewClick}
          disabled={pending}
          className="rounded border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          New (N)
        </button>
        <button
          type="button"
          data-testid="accept-merge"
          data-armed={String(Boolean(mergeTarget))}
          onClick={() =>
            mergeTarget &&
            onAct({
              decision: "accept",
              accept: { action: "merge", target_entity_id: mergeTarget.entity_id },
            })
          }
          disabled={pending || !mergeTarget}
          // Amber signals an *armed* merge (a target is picked), not that merging is
          // merely possible — so a New-proposal card no longer reads as "this will merge"
          // just because it has alternatives (DM-EE-6 amber fix). Neutral until a target
          // is chosen (when it is also disabled).
          className={`rounded border px-3 py-1 text-xs font-medium disabled:opacity-50 ${
            mergeTarget
              ? "border-amber-300 text-amber-800 hover:bg-amber-50"
              : "border-gray-300 text-gray-700"
          }`}
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
