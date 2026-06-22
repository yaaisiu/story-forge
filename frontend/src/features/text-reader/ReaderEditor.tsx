// The read-only Tiptap editor for the reader (M4.S3c-fe1, spec §3.5, DM-S3c-7).
//
// Same boundary discipline as EgoGraphCanvas/GraphCanvas: this is the one reader component
// that touches the ProseMirror/Tiptap *runtime*, isolated behind a thin prop interface. The
// story renders as a single read-only editor; accepted-entity highlights are drawn as
// ProseMirror inline **decorations** (a render-time overlay — the document text is never
// rewritten, so positions stay stable and nothing is injected via innerHTML). The fiddly,
// testable halves live next door and are unit-tested: `buildReaderDoc` (paragraphs → doc)
// and `decorations` (codepoint→UTF-16 offsets + the decoration DOM attributes). What stays
// here is the editor mount + reactive sync, which a real browser drives but jsdom can't —
// so this module has no unit test and is mocked in `TextReader.test.tsx`, exactly as the
// cytoscape canvases are. The owner chose Tiptap now (over a native-selection renderer) so
// the V2 editing modes inherit the engine; M4.S3c-fe2 adds selection→tag + the correction
// menu on top of this.
//
// Why Tiptap is adopted for a *read-only* view: it gives the document model the next slice
// needs to map a text selection back to (paragraphId, paragraph-relative offset) without
// trusting the rendered DOM. Each paragraph node carries its `paragraphId`, rendered as
// `data-paragraph-id` so scroll-to-paragraph + occurrence-flash keep working.

import { type KeyboardEvent, type MouseEvent, useEffect, useMemo, useRef } from "react";

import { type Editor, Extension } from "@tiptap/core";
import Document from "@tiptap/extension-document";
import Paragraph from "@tiptap/extension-paragraph";
import Text from "@tiptap/extension-text";
import { Plugin } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import type { Node as PmNode } from "@tiptap/pm/model";
import { EditorContent, useEditor } from "@tiptap/react";

import type { ReaderEntity, ReaderParagraph } from "../../lib/api/useReader";
import type { ContextMenuRequest, ParagraphSpan } from "./correction";
import { decorationAttrs, paragraphHighlightRanges } from "./decorations";
import { buildReaderDoc } from "./readerDoc";
import { selectionToSpan } from "./selectionOffsets";

/** The paragraph + entity whose highlights should pulse after an occurrence drill-down. */
export interface ReaderFlash {
  paragraphId: string;
  entityId: string;
}

interface ReaderEditorProps {
  paragraphs: readonly ReaderParagraph[];
  catalog: ReadonlyMap<string, ReaderEntity>;
  onEntityClick: (entityId: string) => void;
  flash: ReaderFlash | null;
  /** Right-click resolved to a correction target (M4.S3c-fe2). Omitted = no correction UI. */
  onContextMenuRequest?: (request: ContextMenuRequest) => void;
  /** The current text selection after a drag (for the change-boundaries re-select), or null. */
  onSelectionChange?: (selection: ParagraphSpan | null) => void;
}

/** A text selection resolved to one paragraph + its UTF-16 endpoints (the untestable surface). */
interface ResolvedSelection {
  paragraphId: string;
  paragraphText: string;
  utf16Start: number;
  utf16End: number;
  selectedText: string;
}

// Selection capture on a read-only ProseMirror view (M4.S3c-fe2). This is the one part of the
// reader that touches the live editor/DOM selection runtime — jsdom can't drive it, so it has no
// unit test and is verified in the browser smoke (the EgoGraphCanvas/ReaderEditor precedent). The
// offset *math* it feeds into (UTF-16 → codepoint) is the pure, tested `selectionToSpan`.
//
// `editable:false` constrains ProseMirror's *edit* handlers (the S47 keydown gotcha), so the
// editor's own selection may not always track a DOM drag — we try the ProseMirror selection first
// (it hands back a paragraph-relative offset directly via `parentOffset`) and fall back to the
// native DOM Selection, mapping it through the paragraph's text nodes.
function resolveSelection(editor: Editor): ResolvedSelection | null {
  return resolvePmSelection(editor) ?? resolveNativeSelection();
}

function resolvePmSelection(editor: Editor): ResolvedSelection | null {
  const { from, to, empty } = editor.state.selection;
  if (empty) return null;
  const $from = editor.state.doc.resolve(from);
  const $to = editor.state.doc.resolve(to);
  if (!$from.sameParent($to) || $from.parent.type.name !== "paragraph") return null;
  const paragraphId = $from.parent.attrs.paragraphId as string | null;
  if (!paragraphId) return null;
  return {
    paragraphId,
    paragraphText: $from.parent.textContent,
    utf16Start: $from.parentOffset,
    utf16End: $to.parentOffset,
    selectedText: editor.state.doc.textBetween(from, to),
  };
}

function resolveNativeSelection(): ResolvedSelection | null {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);
  const startParagraph = range.startContainer.parentElement?.closest("[data-paragraph-id]");
  const endParagraph = range.endContainer.parentElement?.closest("[data-paragraph-id]");
  // Selection must sit within a single paragraph (a mention is paragraph-scoped, §6.4).
  if (!startParagraph || startParagraph !== endParagraph) return null;
  const paragraphId = startParagraph.getAttribute("data-paragraph-id");
  if (!paragraphId) return null;
  return {
    paragraphId,
    paragraphText: startParagraph.textContent ?? "",
    utf16Start: utf16OffsetWithin(startParagraph, range.startContainer, range.startOffset),
    utf16End: utf16OffsetWithin(startParagraph, range.endContainer, range.endOffset),
    selectedText: range.toString(),
  };
}

// Sum the UTF-16 lengths of all text nodes in `root` preceding `container`, plus `offset` —
// turning a DOM (node, offset) pair into a paragraph-relative UTF-16 offset. Decoration spans are
// inline overlays, so a paragraph's concatenated text-node content equals its original text.
function utf16OffsetWithin(root: Element, container: Node, offset: number): number {
  let total = 0;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    if (node === container) return total + offset;
    total += (node.textContent ?? "").length;
    node = walker.nextNode();
  }
  return total + offset;
}

interface DecorationInputs {
  paragraphs: readonly ReaderParagraph[];
  catalog: ReadonlyMap<string, ReaderEntity>;
  flash: ReaderFlash | null;
}

// Paragraph carrying the reader's `paragraphId`, surfaced as `data-paragraph-id` on the
// rendered <p> so the container can scroll to and flash a specific paragraph.
const ReaderParagraphNode = Paragraph.extend({
  addAttributes() {
    return {
      paragraphId: {
        default: null,
        parseHTML: (element) => element.getAttribute("data-paragraph-id"),
        renderHTML: (attributes) =>
          attributes.paragraphId ? { "data-paragraph-id": attributes.paragraphId } : {},
      },
    };
  },
});

/** Build the decoration set for the live document from the current highlight inputs. */
function buildDecorations(doc: PmNode, inputs: DecorationInputs): DecorationSet {
  const byId = new Map(inputs.paragraphs.map((paragraph) => [paragraph.id, paragraph]));
  const decorations: Decoration[] = [];
  doc.descendants((node, pos) => {
    if (node.type.name !== "paragraph") return false;
    const paragraphId = node.attrs.paragraphId as string | null;
    const paragraph = paragraphId ? byId.get(paragraphId) : undefined;
    if (!paragraph) return false;
    const contentStart = pos + 1; // position just inside the paragraph node
    for (const { from, to, highlight } of paragraphHighlightRanges(
      paragraph.text,
      paragraph.highlights,
    )) {
      const flashing =
        inputs.flash?.paragraphId === paragraphId && inputs.flash.entityId === highlight.entity_id;
      decorations.push(
        Decoration.inline(
          contentStart + from,
          contentStart + to,
          // `from`/`to` are UTF-16 offsets, so a UTF-16 slice recovers the surface text — the
          // tooltip fallback when the entity is (defensively) absent from the catalog.
          decorationAttrs(
            highlight,
            inputs.catalog.get(highlight.entity_id),
            flashing,
            paragraph.text.slice(from, to),
          ),
        ),
      );
    }
    return false; // highlights live on the paragraph; no need to descend into its text
  });
  return DecorationSet.create(doc, decorations);
}

export function ReaderEditor({
  paragraphs,
  catalog,
  onEntityClick,
  flash,
  onContextMenuRequest,
  onSelectionChange,
}: ReaderEditorProps) {
  // Refs so the once-created editor's plugin/handlers always read the latest props without
  // being rebuilt: `decorations(state)` re-runs on every view update and reads these.
  const inputsRef = useRef<DecorationInputs>({ paragraphs, catalog, flash });
  inputsRef.current = { paragraphs, catalog, flash };
  const onEntityClickRef = useRef(onEntityClick);
  onEntityClickRef.current = onEntityClick;

  // The decoration plugin + click handler, built once (the closures read the refs above).
  const highlightExtension = useMemo(
    () =>
      Extension.create({
        name: "readerHighlights",
        addProseMirrorPlugins() {
          return [
            new Plugin({
              props: {
                decorations: (state) => buildDecorations(state.doc, inputsRef.current),
                handleClick: (_view, _pos, event) => {
                  const target = (event.target as HTMLElement | null)?.closest?.(
                    "[data-entity-id]",
                  );
                  const entityId = target?.getAttribute("data-entity-id");
                  if (entityId) {
                    onEntityClickRef.current(entityId);
                    return true;
                  }
                  return false;
                },
              },
            }),
          ];
        },
      }),
    [],
  );

  // Keyboard parity: open a focused highlight's side panel on Enter/Space. This must be a
  // React/DOM handler, not ProseMirror's `handleKeyDown` — that is an *edit* handler PM only
  // runs while the view is editable, so on this read-only view it never fires (click works
  // because `handleClick` is a regular handler). The keydown bubbles from the focused
  // highlight span (tabindex=0 role=button — see decorationAttrs) to this wrapper.
  const handleHighlightKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const entityId = (event.target as HTMLElement | null)
      ?.closest?.("[data-entity-id]")
      ?.getAttribute("data-entity-id");
    if (entityId) {
      event.preventDefault();
      onEntityClick(entityId);
    }
  };

  const editor = useEditor({
    editable: false,
    extensions: [Document, ReaderParagraphNode, Text, highlightExtension],
    content: buildReaderDoc(paragraphs),
    editorProps: {
      attributes: {
        // Spacing between paragraphs (was the article's gap-4); no focus ring on a read-only view.
        class: "leading-relaxed [&_p]:mb-4 [&_p:last-child]:mb-0 focus:outline-none",
        "data-testid": "reader-editor",
      },
    },
  });

  // Right-click → a correction target. On a highlight, read the addressed occurrence's identity +
  // codepoint span off the decoration DOM (the same data-* the click handler reads); otherwise map
  // the current text selection to a paragraph-scoped codepoint span. Either way hand the container
  // a resolved `ContextMenuRequest`; it owns the menu, popover, and mutation hooks.
  const handleContextMenu = (event: MouseEvent<HTMLDivElement>) => {
    if (!onContextMenuRequest) return;
    const highlightEl = (event.target as HTMLElement | null)?.closest?.("[data-entity-id]");
    if (highlightEl) {
      const paragraphId = highlightEl
        .closest("[data-paragraph-id]")
        ?.getAttribute("data-paragraph-id");
      if (!paragraphId) return;
      event.preventDefault();
      const source = highlightEl.getAttribute("data-source");
      onContextMenuRequest({
        anchor: { x: event.clientX, y: event.clientY },
        target: "highlight",
        paragraphId,
        span_start: Number(highlightEl.getAttribute("data-start")),
        span_end: Number(highlightEl.getAttribute("data-end")),
        selectedText: highlightEl.textContent ?? "",
        entityId: highlightEl.getAttribute("data-entity-id") ?? undefined,
        source: source === "manual" || source === "search" ? source : undefined,
        mentionId: highlightEl.getAttribute("data-mention-id"),
      });
      return;
    }
    if (!editor) return;
    const resolved = resolveSelection(editor);
    if (!resolved) return;
    const span = selectionToSpan(resolved.paragraphText, resolved.utf16Start, resolved.utf16End);
    if (!span) return;
    event.preventDefault();
    onContextMenuRequest({
      anchor: { x: event.clientX, y: event.clientY },
      target: "selection",
      paragraphId: resolved.paragraphId,
      span_start: span.span_start,
      span_end: span.span_end,
      selectedText: resolved.selectedText,
    });
  };

  // Report the current selection after each drag (mouseup) so the change-boundaries re-select can
  // light up its Confirm. Resolves to a paragraph-scoped codepoint span, or null for a collapsed /
  // cross-paragraph selection (a normal click clears it). Same untestable selection runtime above.
  const handleMouseUp = () => {
    if (!onSelectionChange || !editor) return;
    const resolved = resolveSelection(editor);
    const span = resolved
      ? selectionToSpan(resolved.paragraphText, resolved.utf16Start, resolved.utf16End)
      : null;
    onSelectionChange(
      resolved && span
        ? {
            paragraphId: resolved.paragraphId,
            span_start: span.span_start,
            span_end: span.span_end,
            selectedText: resolved.selectedText,
          }
        : null,
    );
  };

  // Reader data changed (a correction/extraction invalidated the query) → reload the document.
  // setContent dispatches a transaction, so the decorations recompute against the new doc. Guard
  // against an empty body: the default `doc` schema is `block+`, so an empty doc would throw —
  // TextReader only mounts this with paragraphs, but the guard keeps a later empty refetch safe.
  useEffect(() => {
    if (editor && paragraphs.length > 0) {
      editor.commands.setContent(buildReaderDoc(paragraphs));
    }
  }, [editor, paragraphs]);

  // Flash changed but the document didn't → nudge the view so `decorations` re-runs and the
  // target paragraph's highlights pick up (or drop) the pulse class.
  useEffect(() => {
    if (editor) editor.view.dispatch(editor.state.tr);
  }, [editor, flash]);

  return (
    <div
      onKeyDown={handleHighlightKeyDown}
      onContextMenu={handleContextMenu}
      onMouseUp={handleMouseUp}
    >
      <EditorContent editor={editor} />
    </div>
  );
}
