// Tests for the per-candidate review card (Session 25 — M3.S4b Stage 4).
//
// The card is presentational: it renders the §3.3 review set (quote/context, NEW-vs-MERGE
// proposal, reasoning, top-3 alternatives) and dispatches the reviewer's action up via
// callbacks. Logic (keyboard, selection, merge-target cycling) lives in the container +
// reviewQueue.ts, so this only asserts render + dispatch.

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CandidateCard } from "./CandidateCard";
import type { CandidateView } from "../../lib/api/useCandidates";

function candidate(over: Partial<CandidateView> = {}): CandidateView {
  return {
    id: "c1",
    paragraph_id: "p1",
    candidate_name: "Janek",
    type: "Character",
    context: "Janek entered the mill at dawn...",
    proposal: "merge",
    target_entity_id: "e1",
    stage_reached: 3,
    confidence: 0.91,
    reasoning: "Same diminutive as the existing Jan.",
    alternatives: [
      { entity_id: "e1", canonical_name: "Jan", score: 91 },
      { entity_id: "e2", canonical_name: "Janusz", score: 70 },
    ],
    ...over,
  };
}

function renderCard(over: Partial<Parameters<typeof CandidateCard>[0]> = {}) {
  const onAct = vi.fn();
  const onPickTarget = vi.fn();
  render(
    <CandidateCard
      candidate={candidate()}
      isSelected={false}
      mergeTargetIndex={null}
      onAct={onAct}
      onPickTarget={onPickTarget}
      {...over}
    />,
  );
  return { onAct, onPickTarget };
}

describe("CandidateCard — render", () => {
  it("shows the candidate name, type, quote/context and reasoning", () => {
    renderCard();
    expect(screen.getByText("Janek")).toBeInTheDocument();
    expect(screen.getByTestId("candidate-context")).toHaveTextContent("entered the mill");
    expect(screen.getByTestId("candidate-reasoning")).toHaveTextContent("diminutive");
  });

  it("renders a MERGE proposal with the target's name", () => {
    renderCard();
    expect(screen.getByTestId("proposal-badge")).toHaveTextContent(/merge/i);
    expect(screen.getByTestId("proposal-badge")).toHaveTextContent("Jan");
  });

  it("renders a NEW proposal when the cascade proposes a new entity", () => {
    renderCard({ candidate: candidate({ proposal: "new", target_entity_id: null }) });
    expect(screen.getByTestId("proposal-badge")).toHaveTextContent(/new/i);
  });

  it("never shows a raw UUID when the merge target is not among the alternatives", () => {
    // Stage-2/3 merges pick the target by embedding cosine / judge, a different signal
    // from the fuzzy top-3 alternatives, so target_entity_id need not be in the list.
    const uuid = "99999999-9999-9999-9999-999999999999";
    renderCard({ candidate: candidate({ proposal: "merge", target_entity_id: uuid }) });
    const badge = screen.getByTestId("proposal-badge");
    expect(badge).toHaveTextContent(/merge/i);
    expect(badge).not.toHaveTextContent(uuid);
    expect(badge).toHaveTextContent(/existing entity/i);
  });

  it("omits the reasoning block when the cascade gave none", () => {
    renderCard({ candidate: candidate({ reasoning: null }) });
    expect(screen.queryByTestId("candidate-reasoning")).not.toBeInTheDocument();
  });

  it("lists the top-3 alternatives and flags the active merge target", () => {
    renderCard({ mergeTargetIndex: 1 });
    const alts = screen.getAllByTestId("candidate-alternative");
    expect(alts).toHaveLength(2);
    expect(alts[1]).toHaveAttribute("data-active", "true");
    expect(alts[0]).toHaveAttribute("data-active", "false");
  });

  it("marks the selected card for the queue's focus styling", () => {
    renderCard({ isSelected: true });
    expect(screen.getByTestId("candidate-card")).toHaveAttribute("data-selected", "true");
  });
});

describe("CandidateCard — dispatch", () => {
  it("Accept fires the cascade proposal (no override)", () => {
    const { onAct } = renderCard();
    fireEvent.click(screen.getByTestId("accept-proposal"));
    expect(onAct).toHaveBeenCalledWith({ decision: "accept" });
  });

  it("New fires accept-as-create", () => {
    const { onAct } = renderCard();
    fireEvent.click(screen.getByTestId("accept-create"));
    expect(onAct).toHaveBeenCalledWith({ decision: "accept", accept: { action: "create" } });
  });

  it("Reject fires a reject", () => {
    const { onAct } = renderCard();
    fireEvent.click(screen.getByTestId("reject"));
    expect(onAct).toHaveBeenCalledWith({ decision: "reject" });
  });

  it("clicking an alternative picks it as the merge target", () => {
    const { onPickTarget } = renderCard();
    fireEvent.click(screen.getAllByTestId("candidate-alternative")[1]!);
    expect(onPickTarget).toHaveBeenCalledWith(1);
  });

  it("Merge commits accept-as-merge to the picked target", () => {
    const { onAct } = renderCard({ mergeTargetIndex: 1 });
    fireEvent.click(screen.getByTestId("accept-merge"));
    expect(onAct).toHaveBeenCalledWith({
      decision: "accept",
      accept: { action: "merge", target_entity_id: "e2" },
    });
  });

  it("disables Merge until a target is picked", () => {
    renderCard({ mergeTargetIndex: null });
    expect(screen.getByTestId("accept-merge")).toBeDisabled();
  });
});
