// Position indicator for the review queues (Graph-quality S7).
//
// The three curation queues (extraction review, relation review, duplicate suggestions) all run
// on the shared `useReviewQueue` hook, which owns a clamped `selectedIndex` over a list that
// *shrinks* as decisions land. Without a count, an author working a long queue has no sense of
// how much is left — so each queue renders this: where the cursor is, and how many remain.
//
// Both numbers already exist at every call site (the hook's clamped index + the feature's own
// item list), so this is presentation only — no hook change, no extra state.

interface QueueProgressProps {
  /** The clamped cursor position from `useReviewQueue` (0-based). */
  selectedIndex: number;
  /** How many items are still undecided. */
  total: number;
}

export function QueueProgress({ selectedIndex, total }: QueueProgressProps) {
  // An empty queue renders its own onward-navigation state instead (`EmptyQueueNext`), so there
  // is nothing to count here — and "1 of 0" would be nonsense.
  if (total === 0) return null;

  return (
    <p data-testid="queue-progress" className="text-sm text-gray-500">
      {selectedIndex + 1} of {total} remaining
    </p>
  );
}
