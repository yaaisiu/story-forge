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

/** One §3.3 alternative existing-entity the reviewer can retarget a merge to. The
 * backend enriches these for S3 verification (DM-EE-3): beyond the RapidFuzz name
 * `score`, it carries the target's `type`, `aliases`, and a sample `context_quote` so
 * two same-named entities can be told apart before merging. The enrichment fields are
 * nullable — a graph-DB outage degrades them to null and the queue still renders. */
export interface CandidateAlternative {
  entity_id: string;
  canonical_name: string;
  score: number;
  type: string | null;
  aliases: string[];
  context_quote: string | null;
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

/** Project the schema's `AlternativeView[]` into the rendering/retargeting shape,
 * carrying the S3 verification context (type/aliases/quote) through null-tolerantly. */
export function alternativesOf(candidate: CandidateView): CandidateAlternative[] {
  return candidate.alternatives.map((alt) => ({
    entity_id: alt.entity_id,
    canonical_name: alt.canonical_name,
    score: alt.score,
    type: alt.type,
    // The contract types `aliases` as a non-null list (a graph-DB outage degrades it to
    // `[]`, not null), but coerce defensively so a rendering `.length` can never throw.
    aliases: alt.aliases ?? [],
    context_quote: alt.context_quote,
  }));
}

/** DM-EE-5 guard: the alternative (if any) whose canonical name matches the candidate's
 * name, compared case- and surrounding-space-insensitively. Used to warn-and-offer the
 * merge before the reviewer creates a same-named duplicate — never a hard block (INV-1;
 * the author may legitimately keep two same-named entities). Checks the loaded top-3
 * alternatives only; a 100-scoring exact name almost always ranks there (the rare
 * outside-top-3 false negative is a documented, deferred backend-lookup escape hatch). */
export function exactNameDuplicate(candidate: CandidateView): CandidateAlternative | null {
  const target = candidate.candidate_name.trim().toLowerCase();
  return (
    alternativesOf(candidate).find((alt) => alt.canonical_name.trim().toLowerCase() === target) ??
    null
  );
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
