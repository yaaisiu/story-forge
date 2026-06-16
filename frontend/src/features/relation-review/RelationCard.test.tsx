// Tests for the per-relation review card (Session 30 — M3.S4f).
//
// The card is presentational: it renders the surface triple + confidence and dispatches
// the author's decision up via `onAct`. Logic (keyboard, selection) lives in the
// container + relationQueue.ts, so this only asserts render + dispatch.

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RelationCard } from "./RelationCard";
import type { RelationView } from "../../lib/api/useRelations";

function relation(over: Partial<RelationView> = {}): RelationView {
  return {
    id: "r1",
    paragraph_id: "p1",
    subject: "Janek",
    predicate: "works_at",
    object: "the mill",
    confidence: 0.91,
    subject_entity_id: "e1",
    object_entity_id: "e2",
    ...over,
  };
}

function renderCard(over: Partial<Parameters<typeof RelationCard>[0]> = {}) {
  const onAct = vi.fn();
  const props = { relation: relation(), isSelected: false, onAct, ...over };
  render(<RelationCard {...props} />);
  return { onAct };
}

describe("RelationCard — render", () => {
  it("shows the surface triple — subject, predicate, object", () => {
    renderCard();
    const triple = screen.getByTestId("relation-triple");
    expect(triple).toHaveTextContent("Janek");
    expect(triple).toHaveTextContent("works_at");
    expect(triple).toHaveTextContent("the mill");
  });

  it("shows the confidence when present, and omits it when null", () => {
    renderCard();
    expect(screen.getByTestId("relation-triple")).toHaveTextContent("confidence 0.91");

    renderCard({ relation: relation({ confidence: null }) });
    // The second render is appended; assert no card shows a confidence label for the null one.
    const cards = screen.getAllByTestId("relation-triple");
    expect(cards.some((c) => /confidence/.test(c.textContent ?? ""))).toBe(true);
    expect(cards.filter((c) => /confidence/.test(c.textContent ?? "")).length).toBe(1);
  });

  it("reflects selection via the data-selected attribute", () => {
    renderCard({ isSelected: true });
    expect(screen.getByTestId("relation-card")).toHaveAttribute("data-selected", "true");
  });
});

describe("RelationCard — dispatch", () => {
  it("Commit dispatches a commit action", () => {
    const { onAct } = renderCard();
    fireEvent.click(screen.getByTestId("commit-relation"));
    expect(onAct).toHaveBeenCalledWith("commit");
  });

  it("Reject dispatches a reject action", () => {
    const { onAct } = renderCard();
    fireEvent.click(screen.getByTestId("reject-relation"));
    expect(onAct).toHaveBeenCalledWith("reject");
  });

  it("disables both actions while a decision is in flight", () => {
    renderCard({ pending: true });
    expect(screen.getByTestId("commit-relation")).toBeDisabled();
    expect(screen.getByTestId("reject-relation")).toBeDisabled();
  });
});
