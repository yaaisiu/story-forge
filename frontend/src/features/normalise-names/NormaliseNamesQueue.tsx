// Name-normalisation review list (Session 96 — Graph-quality S6b, DM-NN-6).
//
// The dedicated "work down the synonym suggestions" surface: reads a story's ranked likely-synonym
// label pairs across both vocabularies and lets the author rename one form into the other graph-wide
// (→ the existing rename endpoint) or dismiss each pair. Suggests only — the human commits every
// rename (INV-1/INV-9). The two surfaces render as separate sections (a predicate is never a synonym
// of a type — DM-NN-1) but share one J/K cursor over the flat list. Dismiss + un-dismiss (DM-NN-3)
// and the post-rename status live here rather than in the card so their transient banners survive the
// card unmounting when the list refetches.
//
// Components render and dispatch: the keyboard scheme is the pure reduceNormaliseKey via the shared
// useReviewQueue hook; the card owns the rename mini-form.

import { useState } from "react";

import { Link, useParams } from "react-router-dom";

import { useLabelVocabulary } from "../../lib/api/useLabelVocabulary";
import { useDismissLabel, useUndismissLabel } from "../../lib/api/useDismissLabel";
import { useReviewQueue } from "../../hooks/useReviewQueue";
import { EmptyQueueNext } from "../../components/ui/EmptyQueueNext";
import { QueueProgress } from "../../components/ui/QueueProgress";
import { LabelPairCard, type RenameOutcome } from "./LabelPairCard";
import {
  flattenVocabulary,
  pairKey,
  reduceNormaliseKey,
  renameSummaryMessage,
  vocabularyErrorMessage,
  type LabelPairItem,
  type NavState,
  type NormaliseIntent,
} from "./normaliseNames";

function pairLabels(item: LabelPairItem): string {
  return `${item.pair.label_lo} & ${item.pair.label_hi}`;
}

/** One vocabulary's pairs, rendered under a heading; the flat cursor index is preserved so J/K and
 * click-select address the same continuous list across both sections. */
function LabelSection({
  title,
  storyId,
  entries,
  selectedIndex,
  onSelect,
  onRenamed,
  onDismiss,
  dismiss,
  testid,
}: {
  title: string;
  storyId: string;
  entries: { item: LabelPairItem; index: number }[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onRenamed: (outcome: RenameOutcome) => void;
  onDismiss: (index: number) => void;
  dismiss: ReturnType<typeof useDismissLabel>;
  testid: string;
}) {
  if (entries.length === 0) return null;
  return (
    <section data-testid={testid} className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
        {title}
        <span className="ml-2 font-normal text-gray-400">{entries.length}</span>
      </h2>
      <ul className="flex flex-col gap-3">
        {entries.map(({ item, index }) => (
          <li key={pairKey(item.surface, item.pair.label_lo, item.pair.label_hi)}>
            <LabelPairCard
              storyId={storyId}
              item={item}
              isSelected={index === selectedIndex}
              onSelect={() => onSelect(index)}
              onRenamed={onRenamed}
              onDismiss={() => onDismiss(index)}
              dismissPending={
                dismiss.isPending &&
                dismiss.variables?.surface === item.surface &&
                dismiss.variables?.labelA === item.pair.label_lo &&
                dismiss.variables?.labelB === item.pair.label_hi
              }
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

export function NormaliseNamesQueue() {
  const { storyId } = useParams<{ storyId: string }>();
  const vocabulary = useLabelVocabulary(storyId);
  const dismiss = useDismissLabel(storyId ?? "");
  const undismiss = useUndismissLabel(storyId ?? "");

  // The most recently dismissed pair (kept so the author can undo the "no" after the list refetches
  // without it) and the most recent rename result (informational — reversal is via the graph undo).
  const [lastDismissed, setLastDismissed] = useState<LabelPairItem | null>(null);
  const [lastRename, setLastRename] = useState<RenameOutcome | null>(null);

  const items = vocabulary.data ? flattenVocabulary(vocabulary.data) : [];

  function dismissAt(index: number) {
    const target = items[index];
    if (!target) return;
    dismiss.mutate(
      { surface: target.surface, labelA: target.pair.label_lo, labelB: target.pair.label_hi },
      {
        onSuccess: () => {
          // Only the most recent action's banner should show — clear a lingering rename status.
          setLastRename(null);
          setLastDismissed(target);
        },
      },
    );
  }

  function handleRenamed(outcome: RenameOutcome) {
    setLastDismissed(null);
    setLastRename(outcome);
  }

  const { state: nav, setState: setNav } = useReviewQueue<LabelPairItem, NavState, NormaliseIntent>(
    {
      items,
      initialState: { selectedIndex: 0 },
      reduceKey: reduceNormaliseKey,
      onCommit: (state) => dismissAt(state.selectedIndex),
    },
  );
  const selectedIndex = nav.selectedIndex;

  function undoDismiss() {
    if (!lastDismissed) return;
    undismiss.mutate(
      {
        surface: lastDismissed.surface,
        labelA: lastDismissed.pair.label_lo,
        labelB: lastDismissed.pair.label_hi,
      },
      { onSuccess: () => setLastDismissed(null) },
    );
  }

  if (vocabulary.isPending) {
    return (
      <main className="p-6">
        <p data-testid="normalise-loading" className="text-sm text-gray-500">
          Finding synonym suggestions…
        </p>
      </main>
    );
  }

  if (vocabulary.isError) {
    return (
      <main className="p-6">
        <p data-testid="normalise-error" role="alert" className="text-sm text-red-700">
          Couldn&rsquo;t load synonym suggestions. {vocabularyErrorMessage(vocabulary.error)}
        </p>
      </main>
    );
  }

  const indexed = items.map((item, index) => ({ item, index }));
  const predicates = indexed.filter((x) => x.item.surface === "predicate");
  const types = indexed.filter((x) => x.item.surface === "type");

  return (
    <main
      data-testid="normalise-list"
      tabIndex={-1}
      className="mx-auto flex max-w-2xl flex-col gap-4 p-6 outline-none"
    >
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">
            Normalise names
            <span data-testid="normalise-count" className="ml-2 text-lg font-normal text-gray-500">
              {items.length}
            </span>
          </h1>
          <p className="text-sm text-gray-600">
            Labels that look like the same thing — keep one form and rename the other into it
            graph-wide, or dismiss the pair. Nothing changes until you press Rename. Keys: J/K move
            · D dismiss.
          </p>
          <QueueProgress selectedIndex={selectedIndex} total={items.length} />
        </div>
        {storyId && (
          <Link
            to={`/stories/${storyId}/graph`}
            data-testid="graph-link"
            className="shrink-0 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Graph
          </Link>
        )}
      </header>

      {lastRename && (
        <p data-testid="normalise-renamed" role="status" className="text-sm text-gray-600">
          {renameSummaryMessage(lastRename.summary, lastRename.fromLabel, lastRename.toLabel)}
        </p>
      )}

      {lastDismissed && (
        <p
          data-testid="normalise-undo"
          role="status"
          className="flex items-center gap-2 text-sm text-gray-600"
        >
          Dismissed {pairLabels(lastDismissed)}.
          <button
            type="button"
            data-testid="normalise-undo-button"
            onClick={undoDismiss}
            disabled={undismiss.isPending}
            className="rounded border border-gray-300 px-2 py-0.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Undo
          </button>
        </p>
      )}

      {dismiss.isError && (
        <p data-testid="normalise-dismiss-error" role="alert" className="text-sm text-red-700">
          {vocabularyErrorMessage(dismiss.error)}
        </p>
      )}

      {undismiss.isError && (
        <p data-testid="normalise-undismiss-error" role="alert" className="text-sm text-red-700">
          Couldn&rsquo;t undo the dismissal. {vocabularyErrorMessage(undismiss.error)}
        </p>
      )}

      {items.length === 0 ? (
        <EmptyQueueNext
          testId="normalise-empty"
          message="No synonym suggestions — the predicate and type names all look distinct."
          storyId={storyId}
          next="graph"
          label="See the knowledge graph"
        />
      ) : (
        <div className="flex flex-col gap-6">
          <LabelSection
            title="Predicates"
            testid="normalise-section-predicate"
            storyId={storyId ?? ""}
            entries={predicates}
            selectedIndex={selectedIndex}
            onSelect={(index) => setNav({ selectedIndex: index })}
            onRenamed={handleRenamed}
            onDismiss={dismissAt}
            dismiss={dismiss}
          />
          <LabelSection
            title="Types"
            testid="normalise-section-type"
            storyId={storyId ?? ""}
            entries={types}
            selectedIndex={selectedIndex}
            onSelect={(index) => setNav({ selectedIndex: index })}
            onRenamed={handleRenamed}
            onDismiss={dismissAt}
            dismiss={dismiss}
          />
        </div>
      )}
    </main>
  );
}
