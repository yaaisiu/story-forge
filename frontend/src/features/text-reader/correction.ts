// Shared types for the reader's manual-correction UI (M4.S3c-fe2, spec §3.5).
//
// `ReaderEditor` (the untestable Tiptap surface) resolves a right-click into a
// `ContextMenuRequest` — the addressed occurrence (a highlight) or a fresh text selection,
// already mapped to **codepoint** span offsets within one paragraph (selectionOffsets.ts). The
// container (`TextReader`) routes the chosen `CorrectionAction` to the right mutation hook.
// Keeping these types in one place lets the editor, the menu, the popover, and the container
// share one contract without a circular import.

/** Whether the right-click landed on an existing highlight or on a free text selection. */
export type CorrectionTarget = "highlight" | "selection";

/** A text selection resolved to one paragraph + a codepoint span (the change-boundaries new span). */
export interface ParagraphSpan {
  paragraphId: string;
  span_start: number;
  span_end: number;
  selectedText: string;
}

/** A right-click resolved by `ReaderEditor`, consumed by `TextReader`. */
export interface ContextMenuRequest {
  /** Viewport coordinates of the click, where the menu is positioned. */
  anchor: { x: number; y: number };
  target: CorrectionTarget;
  paragraphId: string;
  /** Codepoint offsets `[span_start, span_end)` within the paragraph. */
  span_start: number;
  span_end: number;
  /** The selected / highlighted surface text (pre-fills a new-entity name). */
  selectedText: string;
  // Highlight-only — the addressed occurrence's identity (DM-S3c-6).
  entityId?: string;
  source?: "search" | "manual";
  mentionId?: string | null;
}

/**
 * What the author picked from the context menu. `tag` is selection-only; the rest act on a
 * highlight. `not-this` / `not-an-entity` are one-click suppressions (ADR 0008 §4 — never a
 * delete); `reassign` opens the picker; `change-boundaries` enters the re-select mode.
 */
export type CorrectionAction =
  | "tag"
  | "not-this"
  | "reassign"
  | "not-an-entity"
  | "change-boundaries";
