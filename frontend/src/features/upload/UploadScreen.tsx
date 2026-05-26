// Upload screen (Session 6 — Frontend upload UI). Lets the user pick or drop a
// story file (.txt / .md / .docx), POSTs it to /stories/upload, and on success
// shows the detected language + paragraph count from the typed response. On
// failure, surfaces a message keyed off `ApiError.status` so the three distinct
// backend rejections (415 wrong type, 413 too large, 400 empty/unparseable)
// each get their own copy without parsing the detail string.
//
// Plain Tailwind — no shadcn primitives this session (recorded as "B now,
// A when needed" in PLAN_SHORT.md Decided). When an actual interactive
// primitive earns its place (a modal, a combobox), we hand-vendor that one
// component from the shadcn docs and document it in
// `frontend/src/components/ui/CLAUDE.md`.

import { useState, type ChangeEvent, type DragEvent } from "react";

import { Link } from "react-router-dom";

import { ApiError, useUploadStory } from "../../lib/api/useUploadStory";
import { cn } from "../../lib/utils";

const ACCEPTED_EXTENSIONS = ".txt,.md,.docx";

/** Map a backend `ApiError` to a user-facing message keyed by status code. */
function messageForError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Upload failed. Please try again.";
  }
  switch (error.status) {
    case 413:
      return "That file is too large — maximum size is 10 MiB.";
    case 415:
      return "Unsupported file type. Please upload a .txt, .md, or .docx file.";
    case 400:
      return `That file couldn't be parsed: ${error.detail}`;
    default:
      return error.detail || `Upload failed (HTTP ${error.status}).`;
  }
}

export function UploadScreen() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const upload = useUploadStory();

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] ?? null;
    setFile(next);
    // Reset any prior result so the success/error block doesn't linger over a
    // new pick. The mutation's own state machine resets on the next call.
    upload.reset();
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const dropped = event.dataTransfer.files?.[0] ?? null;
    if (dropped) {
      setFile(dropped);
      upload.reset();
    }
  }

  function handleSubmit() {
    if (!file) return;
    upload.mutate({ file });
  }

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <header>
        <h1 className="text-2xl font-semibold">Upload a story</h1>
        <p className="text-sm text-gray-600">
          Accepts <code>.txt</code>, <code>.md</code>, and <code>.docx</code> files up to
          10&nbsp;MiB. The language is detected automatically.
        </p>
      </header>

      <div
        data-testid="upload-dropzone"
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-10 text-center transition-colors",
          isDragging
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 bg-gray-50 hover:border-gray-400",
        )}
      >
        <p className="text-sm text-gray-700">Drag a file here, or</p>
        <label className="cursor-pointer rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800">
          Choose file
          <input
            data-testid="upload-file-input"
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            onChange={handleFileChange}
            className="sr-only"
          />
        </label>
        {file && (
          <p data-testid="upload-selected-file" className="text-sm text-gray-800">
            Selected: <span className="font-medium">{file.name}</span>
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={!file || upload.isPending}
        className="self-start rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        {upload.isPending ? "Uploading…" : "Upload"}
      </button>

      {upload.isSuccess && (
        <section
          data-testid="upload-success"
          className="flex flex-col gap-3 rounded border border-green-200 bg-green-50 p-4 text-sm text-green-900"
        >
          <p>
            Uploaded <span className="font-medium">{upload.data.title}</span> — detected language{" "}
            <span data-testid="upload-language">{upload.data.language}</span>,{" "}
            {upload.data.paragraph_count} paragraph
            {upload.data.paragraph_count === 1 ? "" : "s"}.
          </p>
          {/* Carry the parsed raw_text into the outline editor via router
              state so the manual editor opens pre-seeded — avoids a separate
              GET /stories/{id} round-trip that doesn't exist yet. */}
          <Link
            data-testid="upload-continue-link"
            to={`/stories/${upload.data.story_id}/structure`}
            state={{ rawText: upload.data.raw_text }}
            className="self-start rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            Continue to outline →
          </Link>
        </section>
      )}

      {upload.isError && (
        <section
          data-testid="upload-error"
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-900"
        >
          {messageForError(upload.error)}
        </section>
      )}
    </main>
  );
}
