// Shared review-queue hook (Session 79 — Graph-quality S4b).
//
// The extraction- and relation-review queues (and now the duplicate-suggestion list) all
// share one skeleton: a `selectedIndex` cursor that re-clamps as the list shrinks under
// committed decisions, and a window-bound `keydown` that skips editable fields and
// delegates to a *pure per-feature reducer*. This hook owns exactly that shared mechanism;
// each feature keeps its own reducer (the key→intent semantics differ, and must be read
// off the feature's own contract — see frontend/src/lib/api/CLAUDE.md).
//
// Generic over the item type, the nav-state shape (the candidate queue carries an extra
// `mergeTargetIndex`), and the commit intent. Components render and dispatch: they read the
// returned clamped `state` and call `setState` for mouse-driven changes (selecting a card,
// cycling a merge target); committing keypresses arrive via `onCommit`.

import { useEffect, useState } from "react";

/** True when a keystroke is destined for an editable field, so the window-bound keyboard
 * scheme should leave it alone (a handpick search box, a textarea). */
export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT" ||
    target.isContentEditable === true
  );
}

/** The next queue state, plus — when the key committed a decision — the intent the caller
 * dispatches. A reducer returns `null` when the key isn't part of its scheme (ignore it). */
export interface QueueKeyResult<S, I> {
  state: S;
  intent?: I;
}

export interface UseReviewQueueParams<Item, S extends { selectedIndex: number }, I> {
  /** The current queue items (server state); its length bounds the cursor. */
  items: Item[];
  initialState: S;
  /** Pure map from a keypress to the next state (+ optional commit intent). */
  reduceKey: (key: string, state: S, items: Item[]) => QueueKeyResult<S, I> | null;
  /** Dispatch a committed decision — the component pairs the intent with the selected item. */
  onCommit: (state: S, intent: I) => void;
}

export interface UseReviewQueueResult<S> {
  /** The nav state with `selectedIndex` already clamped into `[0, len-1]`. */
  state: S;
  /** Set the nav state directly (mouse-driven selection / merge-target changes). */
  setState: (next: S) => void;
}

export function useReviewQueue<Item, S extends { selectedIndex: number }, I>({
  items,
  initialState,
  reduceKey,
  onCommit,
}: UseReviewQueueParams<Item, S, I>): UseReviewQueueResult<S> {
  const [raw, setRaw] = useState<S>(initialState);

  // The list shrinks as decisions land; keep the selection in range each render.
  const selectedIndex = Math.min(raw.selectedIndex, Math.max(0, items.length - 1));
  const state: S = { ...raw, selectedIndex };

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      // Skip when the user is typing into a field, else J/K/A/… would hijack their input.
      if (isEditableTarget(event.target)) return;
      const result = reduceKey(event.key, state, items);
      if (!result) return;
      event.preventDefault();
      setRaw(result.state);
      if (result.intent !== undefined) onCommit(result.state, result.intent);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // No deps array is intentional: `state`/`items` are read inside, so re-binding each
    // render keeps the closure fresh (the prior inline queues did the same; cost is
    // negligible at this scale).
  });

  return { state, setState: setRaw };
}
