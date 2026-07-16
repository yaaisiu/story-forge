// One suggested label-synonym pair (Session 96 — Graph-quality S6b, DM-NN-4/5).
//
// Renders both labels with their counts + the honest pair scores (DM-EE-4: a score is never an
// identity verdict), and arms a graph-wide rename: the author picks which form to keep (amber
// highlight, the S3b armed convention), the card shows what the rename will do, and a confirm button
// commits through the *existing* rename endpoint (INV-1/INV-9 — the human commits; reversible via the
// graph-edit undo log). Simpler than the duplicate card: a rename needs no entity detail or conflict
// resolution. Dismiss is handled by the queue (so the transient status survives this card unmounting
// on refetch); on a successful rename the card reports the summary up to the queue for the same reason.
//
// Components render and dispatch: the pure logic lives in normaliseNames.ts.

import { useState } from "react";

import { useRenameLabel, type RenameSummaryResponse } from "../../lib/api/useRenameLabel";
import {
  armRename,
  armedRenameHint,
  scoreLabels,
  vocabularyErrorMessage,
  type LabelPairItem,
} from "./normaliseNames";

/** What a committed rename tells the queue to surface after this card unmounts on refetch. */
export interface RenameOutcome {
  summary: RenameSummaryResponse;
  fromLabel: string;
  toLabel: string;
}

interface LabelPairCardProps {
  storyId: string;
  item: LabelPairItem;
  isSelected: boolean;
  onSelect: () => void;
  onRenamed: (outcome: RenameOutcome) => void;
  onDismiss: () => void;
  dismissPending?: boolean;
}

/** One label of the pair — the form + its edge/node count. The kept side is highlighted amber once
 * picked (the armed-rename convention). */
function LabelSide({
  label,
  count,
  active,
  onPick,
}: {
  label: string;
  count: number;
  active: boolean;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      data-testid="label-keep"
      data-active={String(active)}
      aria-pressed={active}
      onClick={onPick}
      className={`flex-1 rounded border p-2 text-left ${
        active
          ? "border-amber-400 bg-amber-50 text-amber-900"
          : "border-gray-200 text-gray-700 hover:bg-gray-50"
      }`}
    >
      <span data-testid="label-name" className="font-medium">
        {label}
      </span>
      <span data-testid="label-count" className="ml-2 text-xs text-gray-500">
        {count} use{count === 1 ? "" : "s"}
      </span>
    </button>
  );
}

export function LabelPairCard({
  storyId,
  item,
  isSelected,
  onSelect,
  onRenamed,
  onDismiss,
  dismissPending,
}: LabelPairCardProps) {
  // The label the author chose to keep — the other is renamed into it. Null until a side is picked.
  const [keep, setKeep] = useState<string | null>(null);
  const rename = useRenameLabel(storyId);
  const { nameLabel, similarityLabel } = scoreLabels(item.pair);
  const { label_lo, label_hi, count_lo, count_hi } = item.pair;

  const armed = keep ? armRename(item, keep) : null;

  function pickKeep(label: string) {
    rename.reset();
    setKeep(label);
  }

  function confirmRename() {
    if (!armed) return;
    rename.mutate(
      { surface: armed.surface, fromLabel: armed.fromLabel, toLabel: armed.toLabel },
      {
        onSuccess: (summary) =>
          onRenamed({ summary, fromLabel: armed.fromLabel, toLabel: armed.toLabel }),
      },
    );
  }

  return (
    <div
      data-testid="label-pair"
      data-surface={item.surface}
      data-selected={String(isSelected)}
      onClick={onSelect}
      className={`flex flex-col gap-3 rounded border p-3 ${
        isSelected ? "border-gray-800" : "border-gray-200"
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          data-testid="label-surface"
          className="rounded bg-gray-100 px-1.5 py-0.5 text-xs uppercase tracking-wide text-gray-500"
        >
          {item.surface}
        </span>
        <span className="text-xs uppercase tracking-wide text-gray-500">Keep one form</span>
      </div>

      <div className="flex gap-3">
        <LabelSide
          label={label_lo}
          count={count_lo}
          active={keep === label_lo}
          onPick={() => pickKeep(label_lo)}
        />
        <LabelSide
          label={label_hi}
          count={count_hi}
          active={keep === label_hi}
          onPick={() => pickKeep(label_hi)}
        />
      </div>

      <p data-testid="label-scores" className="text-xs text-gray-400">
        {nameLabel} · {similarityLabel}
      </p>

      <p data-testid="rename-hint" className="text-xs text-gray-500">
        {armed
          ? armedRenameHint(armed)
          : "Pick the form to keep; the other is renamed into it graph-wide. Or dismiss if they aren’t synonyms."}
      </p>

      {rename.isError && (
        <p data-testid="rename-error" role="alert" className="text-xs text-red-700">
          {vocabularyErrorMessage(rename.error)}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          data-testid="rename-confirm"
          disabled={!armed || rename.isPending}
          onClick={confirmRename}
          className="rounded bg-gray-800 px-3 py-1 text-xs text-white hover:bg-gray-700 disabled:opacity-50"
        >
          Rename
        </button>
        <button
          type="button"
          data-testid="label-dismiss"
          disabled={dismissPending}
          onClick={onDismiss}
          className="rounded border border-gray-300 px-3 py-1 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Not synonyms
        </button>
      </div>
    </div>
  );
}
