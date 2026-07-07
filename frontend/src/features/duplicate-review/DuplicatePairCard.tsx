// One suggested duplicate pair (Session 79 — Graph-quality S4b, DM-CD-4).
//
// Renders both entities with the S3 (DM-EE-3) verification context — name, type, aliases, a
// mention quote — and the honest pair scores (DM-EE-4: a score is never an identity verdict).
// The author explicitly picks which side survives (no default direction), which arms the merge:
// both entities' properties are loaded on demand, conflicts are resolved by hand (reusing the
// reader's MergeConflictFields + the pure mergeConflicts module), and confirm commits through the
// *existing* merge endpoint (INV-1/INV-9 — suggests only, the human commits). Dismiss is handled
// by the queue (so the transient Undo survives this card unmounting on refetch).
//
// Components render and dispatch: the pure logic lives in duplicateReview.ts / mergeConflicts.ts.

import { useMemo, useState } from "react";

import { useQueryClient } from "@tanstack/react-query";

import { useEntityDetail } from "../../lib/api/useEntityDetail";
import { useMergeEntities } from "../../lib/api/useMergeEntities";
import {
  duplicateSuggestionsQueryKey,
  type DuplicateEntityView,
  type DuplicateSuggestionView,
} from "../../lib/api/useDuplicateSuggestions";
import { MergeConflictFields } from "../text-reader/MergeConflictFields";
import {
  buildConflictRows,
  resolvedPropertiesFrom,
  type ConflictChoice,
} from "../text-reader/mergeConflicts";
import { markMentions, mergeVarsFor, scoreLabels, type SurvivorSide } from "./duplicateReview";

interface DuplicatePairCardProps {
  storyId: string;
  suggestion: DuplicateSuggestionView;
  isSelected: boolean;
  onSelect: () => void;
  onDismiss: () => void;
  dismissPending?: boolean;
}

/** One side of the pair — the identity context the author judges the merge on. The survivor
 * side is highlighted amber once picked (the S3b armed-merge convention, DM-EE-6). */
function EntitySide({ entity, active }: { entity: DuplicateEntityView; active: boolean }) {
  return (
    <div
      data-testid="duplicate-side"
      data-active={String(active)}
      className={`flex-1 rounded border p-2 ${
        active ? "border-amber-400 bg-amber-50 text-amber-900" : "border-gray-200"
      }`}
    >
      <p data-testid="duplicate-side-name" className="font-medium">
        {entity.canonical_name}
      </p>
      <p data-testid="duplicate-side-identity" className="text-xs text-gray-500">
        {entity.type}
        {entity.aliases.length > 0 && ` · aka ${entity.aliases.join(", ")}`}
      </p>
      {entity.context_quote && (
        <p data-testid="duplicate-side-quote" className="text-xs italic text-gray-500">
          &ldquo;
          {markMentions(entity.context_quote, [entity.canonical_name, ...entity.aliases]).map(
            (seg, i) =>
              seg.match ? (
                <mark
                  key={i}
                  data-testid="quote-mention"
                  className="rounded bg-yellow-200 px-0.5 font-medium not-italic text-gray-900"
                >
                  {seg.text}
                </mark>
              ) : (
                <span key={i}>{seg.text}</span>
              ),
          )}
          &rdquo;
        </p>
      )}
    </div>
  );
}

export function DuplicatePairCard({
  storyId,
  suggestion,
  isSelected,
  onSelect,
  onDismiss,
  dismissPending,
}: DuplicatePairCardProps) {
  const [survivor, setSurvivor] = useState<SurvivorSide | null>(null);
  const [picks, setPicks] = useState<Record<string, ConflictChoice>>({});

  const vars = survivor ? mergeVarsFor(survivor, suggestion) : null;
  // Detail is fetched only once a survivor is picked (the hooks stay disabled while the id is
  // undefined) — so opening a 200-pair list doesn't fan out 400 entity reads.
  const survivorDetail = useEntityDetail(storyId, vars?.targetEntityId);
  const absorbedDetail = useEntityDetail(storyId, vars?.absorbedId);

  const conflicts = useMemo(
    () =>
      survivorDetail.data && absorbedDetail.data
        ? buildConflictRows(survivorDetail.data.properties, absorbedDetail.data.properties)
        : [],
    [survivorDetail.data, absorbedDetail.data],
  );

  const merge = useMergeEntities(storyId);
  const queryClient = useQueryClient();
  const { nameLabel, similarityLabel } = scoreLabels(suggestion);

  function pickSurvivor(side: SurvivorSide) {
    merge.reset();
    setPicks({});
    setSurvivor(side);
  }

  function confirmMerge() {
    if (!vars) return;
    merge.mutate(
      { ...vars, resolvedProperties: resolvedPropertiesFrom(conflicts, picks) },
      {
        // useMergeEntities already invalidates the reader/graph/entity-detail caches; the
        // duplicate list is this feature's own, so drop the merged pair off it here.
        onSuccess: () => {
          void queryClient.invalidateQueries({
            queryKey: duplicateSuggestionsQueryKey(storyId),
          });
        },
      },
    );
  }

  // Once the merge has committed, this card is transient — the list refetch will drop it. But
  // the merge invalidates the entity-detail cache, so the absorbed (now-deleted) entity refetches
  // and 404s in the gap before the card unmounts; suppress the detail loading/error so that race
  // can't flash a spurious "couldn't load" on the happy path.
  const detailsLoading =
    Boolean(survivor) && !merge.isSuccess && (survivorDetail.isPending || absorbedDetail.isPending);
  const detailsError =
    Boolean(survivor) && !merge.isSuccess && (survivorDetail.isError || absorbedDetail.isError);
  const canMerge =
    Boolean(vars) && survivorDetail.isSuccess && absorbedDetail.isSuccess && !merge.isPending;

  return (
    <div
      data-testid="duplicate-pair"
      data-selected={String(isSelected)}
      onClick={onSelect}
      className={`flex flex-col gap-3 rounded border p-3 ${
        isSelected ? "border-gray-800" : "border-gray-200"
      }`}
    >
      <div className="flex gap-3">
        <EntitySide entity={suggestion.entity_a} active={survivor === "a"} />
        <EntitySide entity={suggestion.entity_b} active={survivor === "b"} />
      </div>

      <p data-testid="duplicate-scores" className="text-xs text-gray-400">
        {nameLabel} · {similarityLabel}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs uppercase tracking-wide text-gray-500">Keep</span>
        <button
          type="button"
          data-testid="duplicate-keep-a"
          aria-pressed={survivor === "a"}
          onClick={() => pickSurvivor("a")}
          className={`rounded border px-2 py-1 text-xs ${
            survivor === "a"
              ? "border-amber-400 bg-amber-50 text-amber-900"
              : "border-gray-300 text-gray-700 hover:bg-gray-50"
          }`}
        >
          {suggestion.entity_a.canonical_name}
        </button>
        <button
          type="button"
          data-testid="duplicate-keep-b"
          aria-pressed={survivor === "b"}
          onClick={() => pickSurvivor("b")}
          className={`rounded border px-2 py-1 text-xs ${
            survivor === "b"
              ? "border-amber-400 bg-amber-50 text-amber-900"
              : "border-gray-300 text-gray-700 hover:bg-gray-50"
          }`}
        >
          {suggestion.entity_b.canonical_name}
        </button>
      </div>

      <p data-testid="keep-hint" className="text-xs text-gray-500">
        {survivor
          ? "Press Merge to fold the other entity into the amber one — its relations and mentions move over. Nothing happens until you press Merge."
          : "“Keep” chooses which entity survives; the other is merged into it. Or dismiss if they aren’t the same."}
      </p>

      {detailsLoading && (
        <p data-testid="duplicate-details-loading" className="text-xs text-gray-500">
          Loading entity details…
        </p>
      )}
      {detailsError && (
        <p data-testid="duplicate-details-error" role="alert" className="text-xs text-red-700">
          Couldn&rsquo;t load the entities to merge.
        </p>
      )}

      {survivor && (
        <MergeConflictFields
          conflicts={conflicts}
          picks={picks}
          onChange={(key, choice) => setPicks((prev) => ({ ...prev, [key]: choice }))}
        />
      )}

      {merge.isError && (
        <p data-testid="duplicate-merge-error" role="alert" className="text-xs text-red-700">
          {merge.error.detail}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          data-testid="duplicate-merge-confirm"
          disabled={!canMerge}
          onClick={confirmMerge}
          className="rounded bg-gray-800 px-3 py-1 text-xs text-white hover:bg-gray-700 disabled:opacity-50"
        >
          Merge
        </button>
        <button
          type="button"
          data-testid="duplicate-dismiss"
          disabled={dismissPending}
          onClick={onDismiss}
          className="rounded border border-gray-300 px-3 py-1 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Not duplicates
        </button>
      </div>
    </div>
  );
}
