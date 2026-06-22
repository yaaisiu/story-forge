// Reader paragraphs → a Tiptap/ProseMirror document (M4.S3c-fe1, spec §3.5).
//
// The reader moved from a per-paragraph `<mark>` splitter to a single read-only Tiptap
// editor over the whole story, with highlights drawn as ProseMirror *decorations* (an
// overlay, not part of the document). This module builds that document: one `paragraph`
// node per reader paragraph, in document order, each carrying its `paragraphId` as a node
// attribute. The attribute earns its place twice — the custom Paragraph extension renders
// it as `data-paragraph-id` (so scroll-to-paragraph + occurrence-flash keep working), and
// it lets a text selection be mapped back to the paragraph it sits in (Session B).
//
// Pure (no editor runtime) so it unit-tests without mounting ProseMirror. The one rule
// ProseMirror imposes: a text node may not be empty — so an empty paragraph emits a
// paragraph node with no `content`, never a `{ type: "text", text: "" }` child.

import type { JSONContent } from "@tiptap/core";

import type { ReaderParagraph } from "../../lib/api/useReader";

/** Build the Tiptap document for the reader from its paragraphs (document order preserved). */
export function buildReaderDoc(paragraphs: readonly ReaderParagraph[]): JSONContent {
  return {
    type: "doc",
    content: paragraphs.map((paragraph) => {
      const node: JSONContent = { type: "paragraph", attrs: { paragraphId: paragraph.id } };
      if (paragraph.text.length > 0) {
        node.content = [{ type: "text", text: paragraph.text }];
      }
      return node;
    }),
  };
}
