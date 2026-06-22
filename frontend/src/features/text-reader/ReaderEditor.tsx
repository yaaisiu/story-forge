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

import { type KeyboardEvent, useEffect, useMemo, useRef } from "react";

import { Extension } from "@tiptap/core";
import Document from "@tiptap/extension-document";
import Paragraph from "@tiptap/extension-paragraph";
import Text from "@tiptap/extension-text";
import { Plugin } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import type { Node as PmNode } from "@tiptap/pm/model";
import { EditorContent, useEditor } from "@tiptap/react";

import type { ReaderEntity, ReaderParagraph } from "../../lib/api/useReader";
import { decorationAttrs, paragraphHighlightRanges } from "./decorations";
import { buildReaderDoc } from "./readerDoc";

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

export function ReaderEditor({ paragraphs, catalog, onEntityClick, flash }: ReaderEditorProps) {
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
    <div onKeyDown={handleHighlightKeyDown}>
      <EditorContent editor={editor} />
    </div>
  );
}
