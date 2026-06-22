import { describe, expect, it } from "vitest";

import { buildReaderDoc } from "./readerDoc";
import type { ReaderParagraph } from "../../lib/api/useReader";

// `buildReaderDoc` maps the reader's paragraphs into a Tiptap/ProseMirror document:
// one `paragraph` node per paragraph, each carrying its `paragraphId` so the editor's
// rendered <p> gets a `data-paragraph-id` (scroll-to-paragraph + flash) and so a
// selection can be mapped back to the paragraph it sits in (Session B). The text is a
// single child text node — except an *empty* paragraph, which must emit no text node at
// all (ProseMirror forbids an empty text node).
function para(id: string, text: string): ReaderParagraph {
  return { id, text, highlights: [] };
}

describe("buildReaderDoc", () => {
  it("maps a paragraph to a paragraph node with its id and a single text child", () => {
    expect(buildReaderDoc([para("p1", "Janek walked home.")])).toEqual({
      type: "doc",
      content: [
        {
          type: "paragraph",
          attrs: { paragraphId: "p1" },
          content: [{ type: "text", text: "Janek walked home." }],
        },
      ],
    });
  });

  it("emits no text child for an empty paragraph (no empty ProseMirror text node)", () => {
    expect(buildReaderDoc([para("p1", "")])).toEqual({
      type: "doc",
      content: [{ type: "paragraph", attrs: { paragraphId: "p1" } }],
    });
  });

  it("preserves paragraph order", () => {
    const doc = buildReaderDoc([para("p1", "First."), para("p2", "Second."), para("p3", "Third.")]);
    expect(doc.content?.map((n) => n.attrs?.paragraphId)).toEqual(["p1", "p2", "p3"]);
  });

  it("returns an empty doc body for no paragraphs", () => {
    expect(buildReaderDoc([])).toEqual({ type: "doc", content: [] });
  });
});
