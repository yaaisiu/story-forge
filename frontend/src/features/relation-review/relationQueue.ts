// Relation-review keyboard logic (Session 30 — M3.S4f, spec §3.3's 5th human action
// "decide on relations" / §8.3).
//
// The keyboard scheme as a pure reducer, so the RelationQueue component stays
// render-and-dispatch (frontend/src/CLAUDE.md). One keypress maps to a NavState
// transition and, when it commits a decision, a DecideAction the component feeds
// straight to `useDecideRelation`.
//
// Scheme (a subset of §8.3, firmed with the owner S30): J/K (or ↓/↑) navigate; A
// commits the staged edge; R rejects. Unlike the candidate queue there is no merge
// target to cycle — a relation has two already-resolved endpoints, so the only
// decisions are commit-the-edge or reject.

import type { RelationView } from "../../lib/api/useRelations";

/** Which relation card is active. Simpler than the candidate queue's NavState — a
 * relation has no merge target to pick, so the cursor is the whole state. */
export interface NavState {
  selectedIndex: number;
}

/** What a committing keypress (A/R) tells the component to send — mirrors the
 * `DecideRelationRequest.action` enum the decide endpoint accepts. */
export type DecideAction = "commit" | "reject";

/** Result of handling a keypress: the next nav state, plus a decision when the key
 * was A/R. `null` means the key isn't part of the scheme (ignore it). */
export interface KeyResult {
  state: NavState;
  action?: DecideAction;
}

function clamp(index: number, length: number): number {
  if (length === 0) return 0;
  return Math.min(Math.max(index, 0), length - 1);
}

/**
 * Map a keypress to the next queue state (+ an optional decision). Pure — the
 * component owns the side effect (the mutation) and the post-decision refetch.
 */
export function reduceRelationKey(
  key: string,
  state: NavState,
  relations: RelationView[],
): KeyResult | null {
  switch (key) {
    case "j":
    case "J":
    case "ArrowDown":
      return { state: { selectedIndex: clamp(state.selectedIndex + 1, relations.length) } };
    case "k":
    case "K":
    case "ArrowUp":
      return { state: { selectedIndex: clamp(state.selectedIndex - 1, relations.length) } };
    case "a":
    case "A":
      return { state, action: "commit" };
    case "r":
    case "R":
      return { state, action: "reject" };
    default:
      return null;
  }
}
