// Onward navigation for an emptied review queue (Graph-quality S7).
//
// Clearing a curation queue used to dead-end on a line of grey text, leaving the author to
// remember which surface to visit next. Each queue now names its successor in the curation
// flow — review → relations → duplicates → normalise-names → graph — so working the graph reads
// as one guided pass rather than five screens you have to know about.
//
// Presentation only: the caller supplies the message and where "next" points, because only the
// caller knows its own place in the chain.

import { Link } from "react-router-dom";

interface EmptyQueueNextProps {
  /** Why the queue is empty, in the feature's own words. */
  message: string;
  /** The story whose flow we're in; absent (an unmatched route) degrades to message-only. */
  storyId: string | undefined;
  /** The next surface's route segment, e.g. "duplicates". */
  next: string;
  /** The call to action, e.g. "Review possible duplicates". */
  label: string;
  /** Distinguishes the queues' empty states in tests (the pre-S7 test ids are kept). */
  testId: string;
}

export function EmptyQueueNext({ message, storyId, next, label, testId }: EmptyQueueNextProps) {
  return (
    <div className="flex flex-col items-start gap-2">
      <p data-testid={testId} className="text-sm text-gray-500">
        {message}
      </p>
      {/* The URL is built here so the one `storyId` guard covers every call site — matching how
          each queue already gates its own header link on `{storyId && …}`. */}
      {storyId && (
        <Link
          to={`/stories/${storyId}/${next}`}
          data-testid={`${testId}-next`}
          className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          {label} →
        </Link>
      )}
    </div>
  );
}
