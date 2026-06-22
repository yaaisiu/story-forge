import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

// Shared render with the now-required onEntityClick; tests that assert on the click pass
// their own spy via overrides.
function renderParagraph(
  para: ReaderParagraph,
  catalog: Map<string, ReaderEntity>,
  overrides: { onEntityClick?: (id: string) => void; flashEntityId?: string | null } = {},
) {
  return render(
    <ParagraphText
      paragraph={para}
      catalog={catalog}
      onEntityClick={overrides.onEntityClick ?? vi.fn()}
      flashEntityId={overrides.flashEntityId ?? null}
    />,
  );
}

describe("ParagraphText", () => {
  it("renders plain text and a highlighted entity span", () => {
    renderParagraph(
      paragraph("see Janek now", [
        { start: 4, end: 9, entity_id: "e1", type: "character", source: "search" },
      ]),
      catalogOf(ENTITY),
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
    renderParagraph(
      paragraph("Janek", [
        { start: 0, end: 5, entity_id: "e1", type: "character", source: "search" },
      ]),
      catalogOf(ENTITY),
    );

    expect(screen.getByTestId("highlight")).toHaveAttribute(
      "title",
      "Janek — character\nAliases: Jan, młynarz",
    );
  });

  it("omits the aliases line when an entity has none", () => {
    renderParagraph(
      paragraph("Zosia", [{ start: 0, end: 5, entity_id: "e2", type: "place", source: "search" }]),
      catalogOf({ entity_id: "e2", canonical_name: "Zosia", type: "place", aliases: [] }),
    );

    expect(screen.getByTestId("highlight")).toHaveAttribute("title", "Zosia — place");
  });

  it("colours a highlight by its type via an inline style", () => {
    renderParagraph(
      paragraph("Janek", [
        { start: 0, end: 5, entity_id: "e1", type: "character", source: "search" },
      ]),
      catalogOf(ENTITY),
    );
    // character → fixed blue #2563eb (jsdom normalises hex to rgb); the mark
    // carries it as a border colour.
    expect(screen.getByTestId("highlight").style.borderBottomColor).toBe("rgb(37, 99, 235)");
  });

  it("still renders a highlight whose entity is missing from the catalog (graceful)", () => {
    renderParagraph(
      paragraph("Janek", [
        { start: 0, end: 5, entity_id: "gone", type: "character", source: "search" },
      ]),
      catalogOf(),
    );
    const mark = screen.getByTestId("highlight");
    expect(mark).toHaveTextContent("Janek");
    // Falls back to the surface text as the tooltip rather than crashing.
    expect(mark).toHaveAttribute("title", "Janek");
  });

  it("renders a paragraph with no highlights as plain text", () => {
    renderParagraph(paragraph("just prose", []), catalogOf());
    expect(screen.queryByTestId("highlight")).toBeNull();
    expect(screen.getByTestId("reader-paragraph")).toHaveTextContent("just prose");
  });

  it("fires onEntityClick with the entity id when a highlight is clicked", () => {
    const onEntityClick = vi.fn();
    renderParagraph(
      paragraph("Janek", [
        { start: 0, end: 5, entity_id: "e1", type: "character", source: "search" },
      ]),
      catalogOf(ENTITY),
      { onEntityClick },
    );

    fireEvent.click(screen.getByTestId("highlight"));
    expect(onEntityClick).toHaveBeenCalledWith("e1");
  });

  it("fires onEntityClick on Enter for keyboard access", () => {
    const onEntityClick = vi.fn();
    renderParagraph(
      paragraph("Janek", [
        { start: 0, end: 5, entity_id: "e1", type: "character", source: "search" },
      ]),
      catalogOf(ENTITY),
      { onEntityClick },
    );

    fireEvent.keyDown(screen.getByTestId("highlight"), { key: "Enter" });
    expect(onEntityClick).toHaveBeenCalledWith("e1");
  });

  it("flashes only the marks of the flashed entity", () => {
    renderParagraph(
      paragraph("Janek met Zosia.", [
        { start: 0, end: 5, entity_id: "e1", type: "character", source: "search" },
        { start: 10, end: 15, entity_id: "e2", type: "character", source: "search" },
      ]),
      catalogOf(ENTITY, {
        entity_id: "e2",
        canonical_name: "Zosia",
        type: "character",
        aliases: [],
      }),
      { flashEntityId: "e1" },
    );

    const marks = screen.getAllByTestId("highlight");
    expect(marks[0]).toHaveAttribute("data-flash", "true");
    expect(marks[1]).not.toHaveAttribute("data-flash");
  });
});
