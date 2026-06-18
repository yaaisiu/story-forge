// Text reader page (Session 33 — M4.S1 inline highlights, spec §3.5).
//
// A read-only projection of the accepted graph over the prose: the story's text in a
// single column with accepted entities highlighted inline (colour-by-type), hover →
// tooltip. Click-to-side-panel and manual tagging/correction (also in §3.5) are later
// M4 slices and explicitly out of scope here.
//
// Components render and dispatch; logic lives in the hooks + pure modules
// (frontend/src/CLAUDE.md): the span split is `splitParagraph`, colour is `colorForType`,
// the data is `useReader`. Whole-story render for now (DM-IH-6: measure on a real draft,
// virtualise only if it stutters).

import { useMemo } from "react";

import { Link, useParams } from "react-router-dom";

import { useReader, type ReaderEntity } from "../../lib/api/useReader";
import { Legend } from "./Legend";
import { ParagraphText } from "./ParagraphText";
import { legendEntries } from "./palette";

export function TextReader() {
  const { storyId } = useParams<{ storyId: string }>();
  const reader = useReader(storyId);

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

  const isEmpty = reader.isSuccess && reader.data.paragraphs.length === 0;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Reader</h1>
          <p className="text-sm text-gray-600">
            Your story with accepted entities highlighted inline. Hover a highlight for its name,
            type, and aliases.
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
          <article data-testid="reader-text" className="flex flex-col gap-4 text-gray-900">
            {reader.data.paragraphs.map((paragraph) => (
              <ParagraphText key={paragraph.id} paragraph={paragraph} catalog={catalog} />
            ))}
          </article>
        </>
      )}
    </main>
  );
}
