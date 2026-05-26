// Outline editor screen (Session 6 — closes M1).
//
// The user picks a mode (auto / manual / hybrid) and the editor builds the
// document tree by POSTing to /stories/{id}/structure. In manual/hybrid mode
// it shows a textarea seeded with the story's raw text (passed via router
// state from the upload screen) plus a live preview of the parsed outline,
// so the user can see what their `##`/`###` markers will become before
// submitting. Auto mode hides the textarea — the LLM decides offline.
//
// The "live preview" parser is a TS mirror of the backend's
// `domain/chunking.parse_manual_outline`. They must agree on the structural
// rules; tests in `outlineParse.test.ts` pin them.
//
// Errors discriminate by HTTP status against `ApiError.status`, not by string
// matching the detail text (spec §6.7 typed-client posture).

import { useMemo, useState } from "react";

import { useLocation, useParams } from "react-router-dom";

import { ApiError, useStructureStory, type ChunkingMode } from "../../lib/api/useStructureStory";
import { countOutline, parseManualOutline } from "./outlineParse";

interface OutlineEditorLocationState {
  rawText?: string;
}

const MODES: ChunkingMode[] = ["auto", "manual", "hybrid"];

function messageForError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Could not build the outline. Please try again.";
  }
  switch (error.status) {
    case 404:
      return "That story no longer exists. Try uploading it again.";
    case 409:
      return "This story already has a structure. Re-structuring isn't supported yet.";
    case 422:
      return `Invalid input: ${error.detail}`;
    case 502:
      return "The chunking agent failed to produce a usable outline. Try a different mode.";
    default:
      return error.detail || `Failed to build outline (HTTP ${error.status}).`;
  }
}

export function OutlineEditor() {
  const { storyId } = useParams<{ storyId: string }>();
  const location = useLocation();
  const initialRawText = (location.state as OutlineEditorLocationState | null)?.rawText ?? "";

  const [mode, setMode] = useState<ChunkingMode>("manual");
  const [rawText, setRawText] = useState<string>(initialRawText);
  const structure = useStructureStory();

  // Re-parse only when the text changes — cheap, but the preview repaints on
  // every keystroke and the parse runs through the whole string each time.
  const previewCounts = useMemo(() => countOutline(parseManualOutline(rawText)), [rawText]);

  // Manual and hybrid both ship the edited text so the user's markers reach
  // the backend; auto sends null so the route uses the stored raw_text.
  const showEditor = mode !== "auto";

  function handleSubmit() {
    if (!storyId) return;
    structure.mutate({
      storyId,
      mode,
      rawText: showEditor ? rawText : undefined,
    });
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <header>
        <h1 className="text-2xl font-semibold">Build outline</h1>
        <p className="text-sm text-gray-600">
          Pick how to split the story into chapters and scenes. Manual gives you full control with{" "}
          <code>##</code> / <code>###</code> markers; auto asks the LLM; hybrid lets you mark what
          you&rsquo;re sure of and the LLM fills the rest.
        </p>
      </header>

      <fieldset className="flex flex-wrap gap-2">
        <legend className="sr-only">Chunking mode</legend>
        {MODES.map((m) => (
          <label
            key={m}
            data-testid={`outline-mode-${m}`}
            className={
              "cursor-pointer rounded border px-3 py-1.5 text-sm transition-colors " +
              (mode === m
                ? "border-blue-600 bg-blue-50 text-blue-900"
                : "border-gray-300 bg-white text-gray-800 hover:border-gray-400")
            }
          >
            <input
              type="radio"
              name="mode"
              value={m}
              checked={mode === m}
              onChange={() => setMode(m)}
              className="sr-only"
            />
            {m}
          </label>
        ))}
      </fieldset>

      {showEditor && (
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-gray-700">Story source</span>
            <textarea
              data-testid="outline-raw-text"
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              className="h-80 w-full resize-y rounded border border-gray-300 bg-white p-3 font-mono text-sm leading-relaxed"
            />
          </label>
          <aside
            data-testid="outline-preview"
            className="flex flex-col gap-2 rounded border border-gray-200 bg-gray-50 p-3 text-sm"
          >
            <p className="font-medium text-gray-800">Preview</p>
            <p className="text-gray-700">
              {previewCounts.chapters} chapter{previewCounts.chapters === 1 ? "" : "s"},{" "}
              {previewCounts.scenes} scene{previewCounts.scenes === 1 ? "" : "s"},{" "}
              {previewCounts.paragraphs} paragraph
              {previewCounts.paragraphs === 1 ? "" : "s"}
            </p>
          </aside>
        </div>
      )}

      <button
        type="button"
        onClick={handleSubmit}
        disabled={structure.isPending}
        className="self-start rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        {structure.isPending ? "Building…" : "Build outline"}
      </button>

      {structure.isSuccess && (
        <section
          data-testid="outline-success"
          className="rounded border border-green-200 bg-green-50 p-4 text-sm text-green-900"
        >
          <p>
            Persisted outline in <span className="font-medium">{structure.data.mode}</span> mode:{" "}
            {structure.data.chapter_count} chapter
            {structure.data.chapter_count === 1 ? "" : "s"}, {structure.data.scene_count} scene
            {structure.data.scene_count === 1 ? "" : "s"}, {structure.data.paragraph_count}{" "}
            paragraph
            {structure.data.paragraph_count === 1 ? "" : "s"}.
          </p>
        </section>
      )}

      {structure.isError && (
        <section
          data-testid="outline-error"
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-900"
        >
          {messageForError(structure.error)}
        </section>
      )}
    </main>
  );
}
