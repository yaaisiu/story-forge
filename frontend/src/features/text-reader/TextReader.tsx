// Text reader page (Session 33 — M4.S1 inline highlights, spec §3.5).
//
// A read-only projection of the accepted graph over the prose: the story's text in a
// single column with accepted entities highlighted inline (colour-by-type), hover →
// tooltip. M4.S2b adds the entity side panel: clicking a highlight opens it (details +
// properties + a 1-hop ego-graph + an occurrence timeline); a neighbour tap re-targets
// it; an occurrence click scrolls back to that paragraph and flashes the highlight.
//
// M4.S3c-fe1 swapped the per-paragraph `<mark>` renderer for a single read-only Tiptap
// editor (`ReaderEditor`) that draws the highlights as ProseMirror decorations (DM-S3c-7,
// owner's call so V2 editing inherits the engine). This container is unchanged in shape —
// it still owns the data + selection/flash state and dispatches into the editor + panel;
// only the renderer underneath changed. Manual tagging/correction (the selection menu, also
// §3.5) lands on top of this editor in M4.S3c-fe2.
//
// Components render and dispatch; logic lives in the hooks + pure modules
// (frontend/src/CLAUDE.md): the document + decoration mapping are `buildReaderDoc` /
// `decorations`, occurrences are `entityOccurrences`, the panel's data is `useEntityDetail`.
// Whole-story render for now (DM-IH-6: measure on a real draft, virtualise only if it stutters).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Link, useParams } from "react-router-dom";

import { useChangeBoundaries } from "../../lib/api/useChangeBoundaries";
import { useReader, type ReaderEntity } from "../../lib/api/useReader";
import { useSuppressOccurrence } from "../../lib/api/useSuppressOccurrence";
import { useTagOccurrence } from "../../lib/api/useTagOccurrence";
import { Legend } from "./Legend";
import { ReaderContextMenu } from "./ReaderContextMenu";
import { ReaderCorrectionPopover } from "./ReaderCorrectionPopover";
import { ReaderEditor, type ReaderFlash } from "./ReaderEditor";
import { ReaderEntityPanel } from "./ReaderEntityPanel";
import { UndoButton } from "./UndoButton";
import type { ContextMenuRequest, CorrectionAction, ParagraphSpan } from "./correction";
import { legendEntries } from "./palette";

// The correction UI walks through phases over one right-click target: the menu, then either the
// tag/re-assign picker popover or the change-boundaries re-select mode.
type CorrectionPhase =
  | { kind: "menu"; request: ContextMenuRequest }
  | { kind: "tag"; request: ContextMenuRequest }
  | { kind: "reassign"; request: ContextMenuRequest }
  | { kind: "boundary"; request: ContextMenuRequest };

// How long an occurrence drill-down keeps the target highlight pulsing.
const FLASH_MS = 1500;

export function TextReader() {
  const { storyId } = useParams<{ storyId: string }>();
  const reader = useReader(storyId);

  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [flash, setFlash] = useState<ReaderFlash | null>(null);
  const articleRef = useRef<HTMLDivElement>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Manual correction (M4.S3c-fe2). One phase at a time, scoped to a right-click target; the three
  // mutation hooks are scoped to that target's paragraph. `boundarySelection` is the re-selected
  // new span captured while in change-boundaries mode.
  const [phase, setPhase] = useState<CorrectionPhase | null>(null);
  const [boundarySelection, setBoundarySelection] = useState<ParagraphSpan | null>(null);
  const sid = storyId ?? "";
  const activeParagraphId = phase?.request.paragraphId ?? "";
  const tag = useTagOccurrence(sid, activeParagraphId);
  const suppress = useSuppressOccurrence(sid, activeParagraphId);
  const boundaries = useChangeBoundaries(sid, activeParagraphId);

  // Tooltip lookup: entity_id → entity. The backend returns a catalog of exactly the
  // entities that appear, so this is small (one entry per highlighted entity).
  const catalog = useMemo(() => {
    const map = new Map<string, ReaderEntity>();
    for (const entity of reader.data?.entities ?? []) map.set(entity.entity_id, entity);
    return map;
  }, [reader.data]);

  const legend = useMemo(
    () => legendEntries((reader.data?.entities ?? []).map((entity) => entity.type)),
    [reader.data],
  );

  const paragraphs = reader.data?.paragraphs ?? [];

  const handleSelectEntity = useCallback((entityId: string) => {
    setSelectedEntityId(entityId);
  }, []);

  // Drill an occurrence back to its paragraph: scroll it into view and flash the
  // selected entity's highlights there (DM-SP-3). scrollIntoView is a noop in jsdom, so
  // the optional call keeps the unit test from throwing while the browser does the scroll.
  const handleNavigateToOccurrence = useCallback(
    (paragraphId: string) => {
      if (!selectedEntityId) return;
      const target = articleRef.current?.querySelector(`[data-paragraph-id="${paragraphId}"]`);
      target?.scrollIntoView?.({ behavior: "smooth", block: "center" });

      if (flashTimer.current) clearTimeout(flashTimer.current);
      setFlash({ paragraphId, entityId: selectedEntityId });
      flashTimer.current = setTimeout(() => setFlash(null), FLASH_MS);
    },
    [selectedEntityId],
  );

  const handleClosePanel = useCallback(() => {
    if (flashTimer.current) clearTimeout(flashTimer.current);
    setSelectedEntityId(null);
    setFlash(null);
  }, []);

  // Cancel a pending flash timer on unmount so it never fires setFlash after the reader
  // is gone (e.g. navigating away within FLASH_MS of drilling an occurrence).
  useEffect(() => {
    return () => {
      if (flashTimer.current) clearTimeout(flashTimer.current);
    };
  }, []);

  // --- Manual correction (M4.S3c-fe2) --------------------------------------------------------
  const closeCorrection = useCallback(() => {
    setPhase(null);
    setBoundarySelection(null);
    tag.reset();
    suppress.reset();
    boundaries.reset();
  }, [tag, suppress, boundaries]);

  // A right-click opens the menu — unless a correction is already mid-flight (popover / boundary
  // mode), which we let the author finish.
  const handleContextMenuRequest = useCallback((request: ContextMenuRequest) => {
    setPhase((current) =>
      current && current.kind !== "menu" ? current : { kind: "menu", request },
    );
  }, []);

  // Drag selections only matter while re-selecting a new span for change-boundaries.
  const handleSelectionChange = useCallback(
    (selection: ParagraphSpan | null) => {
      if (phase?.kind === "boundary") setBoundarySelection(selection);
    },
    [phase],
  );

  const handleAction = useCallback(
    (action: CorrectionAction) => {
      if (!phase) return;
      const req = phase.request;
      switch (action) {
        case "tag":
          setPhase({ kind: "tag", request: req });
          break;
        case "reassign":
          setPhase({ kind: "reassign", request: req });
          break;
        case "not-this":
          // ADR 0008 §4 — a rejection is a suppression, never a delete; entity_id set clears one.
          suppress.mutate(
            { span_start: req.span_start, span_end: req.span_end, entity_id: req.entityId },
            { onSuccess: closeCorrection },
          );
          break;
        case "not-an-entity":
          // entity_id omitted → suppress all claimants at the span ("this is prose").
          suppress.mutate(
            { span_start: req.span_start, span_end: req.span_end },
            { onSuccess: closeCorrection },
          );
          break;
        case "change-boundaries":
          setBoundarySelection(null);
          setPhase({ kind: "boundary", request: req });
          break;
      }
    },
    [phase, suppress, closeCorrection],
  );

  const handleTagExisting = useCallback(
    (entityId: string) => {
      if (phase?.kind !== "tag") return;
      const { span_start, span_end } = phase.request;
      tag.mutate({ span_start, span_end, entity_id: entityId }, { onSuccess: closeCorrection });
    },
    [phase, tag, closeCorrection],
  );

  const handleTagNew = useCallback(
    (name: string, type: string) => {
      if (phase?.kind !== "tag") return;
      const { span_start, span_end } = phase.request;
      tag.mutate(
        { span_start, span_end, new_entity: { name, type } },
        { onSuccess: closeCorrection },
      );
    },
    [phase, tag, closeCorrection],
  );

  const handleReassign = useCallback(
    (entityId: string) => {
      if (phase?.kind !== "reassign") return;
      const req = phase.request;
      suppress.mutate(
        {
          span_start: req.span_start,
          span_end: req.span_end,
          entity_id: req.entityId,
          retag_to: entityId,
        },
        { onSuccess: closeCorrection },
      );
    },
    [phase, suppress, closeCorrection],
  );

  const handleConfirmBoundary = useCallback(() => {
    if (phase?.kind !== "boundary" || !boundarySelection) return;
    const origin = phase.request;
    if (!origin.entityId) return;
    boundaries.mutate(
      {
        entity_id: origin.entityId,
        // A search hit has no mention_id → materialize; a manual span edits in place.
        mention_id: origin.mentionId ?? undefined,
        old_start: origin.span_start,
        old_end: origin.span_end,
        new_start: boundarySelection.span_start,
        new_end: boundarySelection.span_end,
      },
      { onSuccess: closeCorrection },
    );
  }, [phase, boundarySelection, boundaries, closeCorrection]);

  const isEmpty = reader.isSuccess && reader.data.paragraphs.length === 0;
  const showPanel = reader.isSuccess && reader.data.paragraphs.length > 0 && selectedEntityId;

  return (
    <main className="mx-auto flex max-w-6xl gap-4 p-6">
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <header className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">Reader</h1>
            <p className="text-sm text-gray-600">
              Your story with accepted entities highlighted inline. Click a highlight to inspect the
              entity; hover for its name, type, and aliases.
            </p>
          </div>
          {storyId && (
            <div className="flex shrink-0 items-start gap-2">
              <UndoButton storyId={storyId} />
              <Link
                to={`/stories/${storyId}/graph`}
                data-testid="graph-link"
                className="shrink-0 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Knowledge graph
              </Link>
            </div>
          )}
        </header>

        {reader.isPending && (
          <p data-testid="reader-loading" className="text-sm text-gray-500">
            Loading story…
          </p>
        )}
        {reader.isError && (
          <p data-testid="reader-error" role="alert" className="text-sm text-red-700">
            Couldn&rsquo;t load the story.
          </p>
        )}
        {isEmpty && (
          <p data-testid="reader-empty" className="text-sm text-gray-500">
            No text to show yet.
          </p>
        )}

        {reader.isSuccess && reader.data.paragraphs.length > 0 && (
          <>
            <Legend entries={legend} />
            <article ref={articleRef} data-testid="reader-text" className="text-gray-900">
              <ReaderEditor
                paragraphs={paragraphs}
                catalog={catalog}
                onEntityClick={handleSelectEntity}
                flash={flash}
                onContextMenuRequest={handleContextMenuRequest}
                // Only resolve drag-selections while re-selecting a boundary span — otherwise every
                // mouseup would walk the paragraph's text nodes for a result nothing consumes.
                onSelectionChange={phase?.kind === "boundary" ? handleSelectionChange : undefined}
              />
            </article>
          </>
        )}
      </div>

      {showPanel && (
        <div className="sticky top-6 max-h-[calc(100vh-3rem)] self-start overflow-y-auto">
          <ReaderEntityPanel
            storyId={storyId}
            entityId={selectedEntityId}
            paragraphs={paragraphs}
            onClose={handleClosePanel}
            onDeleted={handleClosePanel}
            onSelectEntity={handleSelectEntity}
            onNavigateToOccurrence={handleNavigateToOccurrence}
          />
        </div>
      )}

      {phase?.kind === "menu" && (
        <ReaderContextMenu
          request={phase.request}
          onAction={handleAction}
          onDismiss={closeCorrection}
        />
      )}

      {(phase?.kind === "tag" || phase?.kind === "reassign") && (
        <ReaderCorrectionPopover
          storyId={storyId}
          mode={phase.kind}
          request={phase.request}
          pending={phase.kind === "tag" ? tag.isPending : suppress.isPending}
          error={phase.kind === "tag" ? tag.error : suppress.error}
          onSubmitExisting={phase.kind === "tag" ? handleTagExisting : handleReassign}
          onSubmitNew={handleTagNew}
          onCancel={closeCorrection}
        />
      )}

      {phase?.kind === "boundary" && (
        <div
          data-testid="boundary-banner"
          role="dialog"
          aria-label="Change boundaries"
          className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-3 bg-amber-50 px-4 py-2 text-sm shadow"
        >
          <span className="text-amber-900">
            Select the new span for{" "}
            <span className="font-medium">
              {catalog.get(phase.request.entityId ?? "")?.canonical_name ??
                phase.request.selectedText}
            </span>
            , then confirm.
          </span>
          <button
            type="button"
            data-testid="boundary-confirm"
            disabled={
              !boundarySelection ||
              boundarySelection.paragraphId !== phase.request.paragraphId ||
              boundaries.isPending
            }
            onClick={handleConfirmBoundary}
            className="rounded bg-amber-700 px-3 py-1 text-white disabled:opacity-40"
          >
            Confirm
          </button>
          <button
            type="button"
            data-testid="boundary-cancel"
            onClick={closeCorrection}
            className="rounded border border-amber-300 px-3 py-1 text-amber-800"
          >
            Cancel
          </button>
          {boundaries.isError && (
            <span data-testid="boundary-error" role="alert" className="text-xs text-red-700">
              {boundaries.error.detail}
            </span>
          )}
        </div>
      )}
    </main>
  );
}
