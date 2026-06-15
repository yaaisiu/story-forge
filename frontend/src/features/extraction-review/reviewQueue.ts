// Review-queue keyboard logic (Session 25 — M3.S4b Stage 4, spec §3.3 / §8.3).
//
// The §8.3 keyboard scheme as a pure reducer, so the ReviewQueue component stays
// render-and-dispatch (frontend/src/CLAUDE.md). One keypress maps to a NavState
// transition and, when it commits a decision, a ReviewIntent the component feeds
// straight to `useReviewCandidate`.
//
// Scheme: J/K (or ↓/↑) navigate; A accepts the cascade's proposal as-is; N forces
// accept-as-create; R rejects; M cycles a *merge target* through the candidate's
// top-3 alternatives (a pick, not a commit — arbitrary-entity search is a deferred
// follow-up, see docs/PLAN_SHORT.md cross-cutting); Enter commits the picked merge,
// or the cascade proposal when nothing is picked.

import type { CandidateView } from "../../lib/api/useCandidates";
import type { ReviewInput } from "../../lib/api/useReviewCandidate";

/** One §3.3 alternative existing-entity the reviewer can retarget a merge to. Backend
 * stages these as `{entity_id, canonical_name, score}` (matching_agent.top_alternatives),
 * but the generated schema types the array as untyped dicts — `alternativesOf` narrows. */
export interface CandidateAlternative {
  entity_id: string;
  canonical_name: string;
  score: number;
}

/** Navigation state of the queue: which card is active, and (while the reviewer is
 * using `M` to retarget a merge) which alternative is the pending target. */
export interface NavState {
  selectedIndex: number;
  /** Index into the selected candidate's alternatives, or null when not retargeting. */
  mergeTargetIndex: number | null;
}

/** What a committing keypress (A/N/R/Enter) tells the component to send. Omits the
 * candidate id — the component pairs it with the currently-selected candidate. */
export type ReviewIntent = Pick<ReviewInput, "decision" | "accept">;

/** Result of handling a keypress: the next nav state, plus a commit intent when the
 * key was a decision. `null` means the key isn't part of the scheme (ignore it). */
export interface KeyResult {
  state: NavState;
  intent?: ReviewIntent;
}

/** Narrow the schema's untyped `alternatives` dicts into typed entries for rendering
 * and retargeting. Unknown/missing fields fall back to empty/zero rather than throw. */
export function alternativesOf(candidate: CandidateView): CandidateAlternative[] {
  return candidate.alternatives.map((raw) => {
    const alt = raw as Record<string, unknown>;
    return {
      entity_id: String(alt.entity_id ?? ""),
      canonical_name: String(alt.canonical_name ?? ""),
      score: typeof alt.score === "number" ? alt.score : 0,
    };
  });
}

function clamp(index: number, length: number): number {
  if (length === 0) return 0;
  return Math.min(Math.max(index, 0), length - 1);
}

/**
 * Map a keypress to the next queue state (+ an optional commit intent). Pure — the
 * component owns the side effect (the mutation) and the post-commit refetch.
 */
export function reduceReviewKey(
  key: string,
  state: NavState,
  candidates: CandidateView[],
): KeyResult | null {
  const selected = candidates[state.selectedIndex];

  switch (key) {
    case "j":
    case "J":
    case "ArrowDown":
      return {
        state: {
          selectedIndex: clamp(state.selectedIndex + 1, candidates.length),
          mergeTargetIndex: null,
        },
      };
    case "k":
    case "K":
    case "ArrowUp":
      return {
        state: {
          selectedIndex: clamp(state.selectedIndex - 1, candidates.length),
          mergeTargetIndex: null,
        },
      };
    case "a":
    case "A":
      return { state: { ...state, mergeTargetIndex: null }, intent: { decision: "accept" } };
    case "n":
    case "N":
      return {
        state: { ...state, mergeTargetIndex: null },
        intent: { decision: "accept", accept: { action: "create" } },
      };
    case "r":
    case "R":
      return { state: { ...state, mergeTargetIndex: null }, intent: { decision: "reject" } };
    case "m":
    case "M": {
      const alts = selected ? alternativesOf(selected) : [];
      if (alts.length === 0) return { state }; // nothing to pick — no-op
      const next = state.mergeTargetIndex === null ? 0 : (state.mergeTargetIndex + 1) % alts.length;
      return { state: { ...state, mergeTargetIndex: next } };
    }
    case "Enter": {
      if (state.mergeTargetIndex === null) {
        return { state, intent: { decision: "accept" } };
      }
      const alts = selected ? alternativesOf(selected) : [];
      const target = alts[state.mergeTargetIndex];
      if (!target) return { state: { ...state, mergeTargetIndex: null } };
      return {
        state: { ...state, mergeTargetIndex: null },
        intent: {
          decision: "accept",
          accept: { action: "merge", target_entity_id: target.entity_id },
        },
      };
    }
    default:
      return null;
  }
}
