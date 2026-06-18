// Text reader page (Session 33 — M4.S1 inline highlights, spec §3.5).
//
// A read-only projection of the accepted graph over the prose: the story's text in a
// single column with accepted entities highlighted inline (colour-by-type), hover →
// tooltip. M4.S2b adds the entity side panel: clicking a highlight opens it (details +
// properties + a 1-hop ego-graph + an occurrence timeline); a neighbour tap re-targets
// it; an occurrence click scrolls back to that paragraph and flashes the highlight.
// Manual tagging/correction (also in §3.5) is a later M4 slice and out of scope here.
//
// Components render and dispatch; logic lives in the hooks + pure modules
// (frontend/src/CLAUDE.md): the span split is `splitParagraph`, occurrences are
// `entityOccurrences`, the panel's data is `useEntityDetail`. Whole-story render for now
// (DM-IH-6: measure on a real draft, virtualise only if it stutters).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Link, useParams } from "react-router-dom";

import { useReader, type ReaderEntity } from "../../lib/api/useReader";
import { Legend } from "./Legend";
import { ParagraphText } from "./ParagraphText";
import { ReaderEntityPanel } from "./ReaderEntityPanel";
import { legendEntries } from "./palette";

// How long an occurrence drill-down keeps the target highlight pulsing.
const FLASH_MS = 1500;

interface Flash {
  paragraphId: string;
  entityId: string;
}

export function TextReader() {
  const { storyId } = useParams<{ storyId: string }>();
  const reader = useReader(storyId);

  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [flash, setFlash] = useState<Flash | null>(null);
  const articleRef = useRef<HTMLDivElement>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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
            <Link
              to={`/stories/${storyId}/graph`}
              data-testid="graph-link"
              className="shrink-0 rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Knowledge graph
            </Link>
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
            <article
              ref={articleRef}
              data-testid="reader-text"
              className="flex flex-col gap-4 text-gray-900"
            >
              {paragraphs.map((paragraph) => (
                <ParagraphText
                  key={paragraph.id}
                  paragraph={paragraph}
                  catalog={catalog}
                  onEntityClick={handleSelectEntity}
                  flashEntityId={flash?.paragraphId === paragraph.id ? flash.entityId : null}
                />
              ))}
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
            onSelectEntity={handleSelectEntity}
            onNavigateToOccurrence={handleNavigateToOccurrence}
          />
        </div>
      )}
    </main>
  );
}
