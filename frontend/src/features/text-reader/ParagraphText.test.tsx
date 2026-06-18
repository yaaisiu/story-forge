import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ReaderEntity, ReaderParagraph } from "../../lib/api/useReader";
import { ParagraphText } from "./ParagraphText";

const ENTITY: ReaderEntity = {
  entity_id: "e1",
  canonical_name: "Janek",
  type: "character",
  aliases: ["Jan", "młynarz"],
};

function catalogOf(...entities: ReaderEntity[]): Map<string, ReaderEntity> {
  return new Map(entities.map((e) => [e.entity_id, e]));
}

function paragraph(text: string, highlights: ReaderParagraph["highlights"]): ReaderParagraph {
  return { id: "p1", text, highlights };
}

describe("ParagraphText", () => {
  it("renders plain text and a highlighted entity span", () => {
    render(
      <ParagraphText
        paragraph={paragraph("see Janek now", [
          { start: 4, end: 9, entity_id: "e1", type: "character" },
        ])}
        catalog={catalogOf(ENTITY)}
      />,
    );

    const mark = screen.getByTestId("highlight");
    expect(mark).toHaveTextContent("Janek");
    expect(mark.tagName).toBe("MARK");
    expect(mark).toHaveAttribute("data-entity-id", "e1");
    expect(mark).toHaveAttribute("data-entity-type", "character");
    // The surrounding plain text is rendered too.
    expect(screen.getByTestId("reader-paragraph")).toHaveTextContent("see Janek now");
  });

  it("tooltips a highlight with canonical_name + type + aliases (DM-IH-8)", () => {
    render(
      <ParagraphText
        paragraph={paragraph("Janek", [{ start: 0, end: 5, entity_id: "e1", type: "character" }])}
        catalog={catalogOf(ENTITY)}
      />,
    );

    expect(screen.getByTestId("highlight")).toHaveAttribute(
      "title",
      "Janek — character\nAliases: Jan, młynarz",
    );
  });

  it("omits the aliases line when an entity has none", () => {
    render(
      <ParagraphText
        paragraph={paragraph("Zosia", [{ start: 0, end: 5, entity_id: "e2", type: "place" }])}
        catalog={catalogOf({
          entity_id: "e2",
          canonical_name: "Zosia",
          type: "place",
          aliases: [],
        })}
      />,
    );

    expect(screen.getByTestId("highlight")).toHaveAttribute("title", "Zosia — place");
  });

  it("colours a highlight by its type via an inline style", () => {
    render(
      <ParagraphText
        paragraph={paragraph("Janek", [{ start: 0, end: 5, entity_id: "e1", type: "character" }])}
        catalog={catalogOf(ENTITY)}
      />,
    );
    // character → fixed blue #2563eb (jsdom normalises hex to rgb); the mark
    // carries it as a border colour.
    expect(screen.getByTestId("highlight").style.borderBottomColor).toBe("rgb(37, 99, 235)");
  });

  it("still renders a highlight whose entity is missing from the catalog (graceful)", () => {
    render(
      <ParagraphText
        paragraph={paragraph("Janek", [{ start: 0, end: 5, entity_id: "gone", type: "character" }])}
        catalog={catalogOf()}
      />,
    );
    const mark = screen.getByTestId("highlight");
    expect(mark).toHaveTextContent("Janek");
    // Falls back to the surface text as the tooltip rather than crashing.
    expect(mark).toHaveAttribute("title", "Janek");
  });

  it("renders a paragraph with no highlights as plain text", () => {
    render(<ParagraphText paragraph={paragraph("just prose", [])} catalog={catalogOf()} />);
    expect(screen.queryByTestId("highlight")).toBeNull();
    expect(screen.getByTestId("reader-paragraph")).toHaveTextContent("just prose");
  });
});
