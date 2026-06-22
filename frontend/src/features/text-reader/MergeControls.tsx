// The reader panel's merge affordance (Session 43 — M4.S3b-fe, spec §3.4 merge in the detail
// panel; DM-S3b-2 by-hand conflict resolution).
//
// From the open entity's panel (the *survivor*, kept), the author picks another entity to absorb
// into it (reusing the M3.S4d EntityPicker). Where both set a property key differently, a by-hand
// resolver shows both values and the author picks which to keep (DM-S3b-2) — conflicts are detected
// client-side from both entities' `properties` (the merge route's 400 names only the keys, no
// values — see mergeConflicts.ts). On confirm it POSTs the merge and reports the outcome counts
// (MergeSummaryResponse): edges re-pointed, MERGE-folded (multiplicity lost — surfaced, DM-S3b-3),
// self-loops dropped, and mentions moved onto the survivor.
//
// Components render and dispatch: the conflict logic lives in the pure `mergeConflicts` module and
// the write in `useMergeEntities`. A self-merge is blocked client-side (the backend 409s anyway).

import { useMemo, useState } from "react";

import { EntityPicker } from "../extraction-review/EntityPicker";
import type { EntitySearchResult } from "../../lib/api/useEntitySearch";
import { useEntityDetail } from "../../lib/api/useEntityDetail";
import { useMergeEntities } from "../../lib/api/useMergeEntities";
import { formatPropertyValue } from "./formatPropertyValue";
import { buildConflictRows, resolvedPropertiesFrom, type ConflictChoice } from "./mergeConflicts";

interface MergeControlsProps {
  storyId: string;
  /** The open panel entity — the survivor that is kept. */
  survivorId: string;
  survivorName: string;
  survivorProperties: Record<string, unknown>;
}

export function MergeControls({
  storyId,
  survivorId,
  survivorName,
  survivorProperties,
}: MergeControlsProps) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<EntitySearchResult | null>(null);
  const [picks, setPicks] = useState<Record<string, ConflictChoice>>({});

  const merge = useMergeEntities(storyId);
  const isSelf = picked?.entity_id === survivorId;
  const absorbed = useEntityDetail(storyId, isSelf ? undefined : (picked?.entity_id ?? undefined));

  const conflicts = useMemo(
    () => (absorbed.data ? buildConflictRows(survivorProperties, absorbed.data.properties) : []),
    [survivorProperties, absorbed.data],
  );

  function reset() {
    setPicked(null);
    setPicks({});
    merge.reset();
  }

  function submit() {
    if (!picked || isSelf) return;
    merge.mutate(
      {
        absorbedId: picked.entity_id,
        targetEntityId: survivorId,
        resolvedProperties: resolvedPropertiesFrom(conflicts, picks),
      },
      {
        // Keep the summary (merge.data) visible; just clear the picker so the section is ready
        // for another merge. Cache invalidation refetches the survivor's refreshed panel.
        onSuccess: () => {
          setPicked(null);
          setPicks({});
        },
      },
    );
  }

  // Picking (or clearing) an entity drops a prior merge's lingering summary, so the
  // success line never hangs over the setup for the next merge.
  function pickEntity(result: EntitySearchResult) {
    merge.reset();
    setPicks({});
    setPicked(result);
  }

  function clearPick() {
    merge.reset();
    setPicks({});
    setPicked(null);
  }

  if (!open) {
    return (
      <button
        type="button"
        data-testid="reader-entity-merge"
        onClick={() => setOpen(true)}
        className="self-start rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
      >
        Merge another entity in
      </button>
    );
  }

  const canMerge = Boolean(picked) && !isSelf && absorbed.isSuccess && !merge.isPending;

  return (
    <section
      data-testid="merge-controls"
      className="flex w-full flex-col gap-2 rounded border border-gray-100 p-2"
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
          Merge into {survivorName}
        </p>
        <button
          type="button"
          data-testid="merge-close"
          aria-label="Cancel merge"
          onClick={() => {
            reset();
            setOpen(false);
          }}
          className="rounded px-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
        >
          ✕
        </button>
      </div>

      {merge.data && (
        <p data-testid="merge-summary" role="status" className="text-xs text-green-700">
          Merged. {merge.data.repointed_count} relation(s) re-pointed, {merge.data.folded_count}{" "}
          folded, {merge.data.self_loops_dropped} self-loop(s) dropped,{" "}
          {merge.data.mentions_repointed} mention(s) moved.
        </p>
      )}

      {picked ? (
        <p className="text-xs text-gray-700">
          Absorb{" "}
          <span data-testid="merge-absorbed-name" className="font-medium">
            {picked.canonical_name}
          </span>{" "}
          <button
            type="button"
            data-testid="merge-clear-pick"
            onClick={clearPick}
            className="text-gray-400 hover:underline"
          >
            change
          </button>
        </p>
      ) : (
        <EntityPicker storyId={storyId} onPick={pickEntity} disabled={merge.isPending} />
      )}

      {isSelf && (
        <p data-testid="merge-self-warning" role="alert" className="text-xs text-amber-700">
          That is this same entity — pick a different one to merge in.
        </p>
      )}

      {picked && !isSelf && absorbed.isError && (
        <p data-testid="merge-absorbed-error" role="alert" className="text-xs text-red-700">
          Couldn&rsquo;t load the entity to merge.
        </p>
      )}

      {conflicts.length > 0 && (
        <fieldset data-testid="merge-conflicts" className="flex flex-col gap-2">
          <legend className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Resolve conflicting properties
          </legend>
          {conflicts.map((row) => {
            const choice = picks[row.key] ?? "survivor";
            const setChoice = (c: ConflictChoice) =>
              setPicks((prev) => ({ ...prev, [row.key]: c }));
            return (
              <div
                key={row.key}
                data-testid="merge-conflict"
                className="flex flex-col gap-1 border-b border-gray-100 pb-1"
              >
                <span className="text-xs font-medium text-gray-600">{row.key}</span>
                <div className="flex gap-1">
                  <button
                    type="button"
                    data-testid="merge-keep-survivor"
                    aria-pressed={choice === "survivor"}
                    onClick={() => setChoice("survivor")}
                    className={`flex-1 truncate rounded border px-2 py-1 text-left text-xs ${
                      choice === "survivor"
                        ? "border-gray-800 bg-gray-800 text-white"
                        : "border-gray-300 text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    keep: {formatPropertyValue(row.survivorValue)}
                  </button>
                  <button
                    type="button"
                    data-testid="merge-keep-absorbed"
                    aria-pressed={choice === "absorbed"}
                    onClick={() => setChoice("absorbed")}
                    className={`flex-1 truncate rounded border px-2 py-1 text-left text-xs ${
                      choice === "absorbed"
                        ? "border-gray-800 bg-gray-800 text-white"
                        : "border-gray-300 text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    use: {formatPropertyValue(row.absorbedValue)}
                  </button>
                </div>
              </div>
            );
          })}
        </fieldset>
      )}

      {merge.isError && (
        <p data-testid="merge-error" role="alert" className="text-xs text-red-700">
          {merge.error.detail}
        </p>
      )}

      <button
        type="button"
        data-testid="merge-confirm"
        disabled={!canMerge}
        onClick={submit}
        className="self-start rounded bg-gray-800 px-3 py-1 text-xs text-white hover:bg-gray-700 disabled:opacity-50"
      >
        Merge
      </button>
    </section>
  );
}
