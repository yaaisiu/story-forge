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

// Stub the picker: it owns a network hook (covered by EntityPicker.test.tsx). Here it
// stands in as a button that hands the card a fixed handpicked entity, so the card's own
// wiring — handpick → merge-accept, precedence over the alternatives — is tested in
// isolation. It echoes its storyId so we can assert the card threads it through.
const HANDPICKED = {
  entity_id: "handpicked-id",
  canonical_name: "Katarzyna",
  type: "Character",
  score: 42,
  aliases: [],
};

vi.mock("./EntityPicker", () => ({
  EntityPicker: ({
    storyId,
    onPick,
    disabled,
  }: {
    storyId?: string;
    onPick: (r: typeof HANDPICKED) => void;
    disabled?: boolean;
  }) => (
    <button
      type="button"
      data-testid="entity-picker-stub"
      data-story-id={storyId ?? ""}
      data-disabled={String(Boolean(disabled))}
      onClick={() => onPick(HANDPICKED)}
    >
      pick handpicked
    </button>
  ),
}));

function candidate(over: Partial<CandidateView> = {}): CandidateView {
  return {
    id: "c1",
    paragraph_id: "p1",
    candidate_name: "Janek",
    type: "Character",
    context: "Janek entered the mill at dawn...",
    proposal: "merge",
    target_entity_id: "e1",
    target_canonical_name: "Jan",
    stage_reached: 3,
    confidence: 0.91,
    reasoning: "Same diminutive as the existing Jan.",
    alternatives: [
      {
        entity_id: "e1",
        canonical_name: "Jan",
        score: 91,
        type: "Character",
        aliases: [],
        context_quote: null,
      },
      {
        entity_id: "e2",
        canonical_name: "Janusz",
        score: 70,
        type: "Character",
        aliases: [],
        context_quote: null,
      },
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

  it("shows the resolved target name for a merge outside the fuzzy top-3 (DM-EE-3)", () => {
    // Stage-2/3 merges pick the target by embedding cosine / judge, a different signal
    // from the fuzzy top-3 alternatives, so target_entity_id need not be in the list —
    // but the backend now resolves its name, so the badge shows it (not "an existing entity").
    const uuid = "99999999-9999-9999-9999-999999999999";
    renderCard({
      candidate: candidate({
        proposal: "merge",
        target_entity_id: uuid,
        target_canonical_name: "Kasia",
      }),
    });
    const badge = screen.getByTestId("proposal-badge");
    expect(badge).toHaveTextContent(/merge/i);
    expect(badge).toHaveTextContent("Kasia");
    expect(badge).not.toHaveTextContent(uuid);
  });

  it("falls back to a generic label (never a raw UUID) when enrichment degraded the name to null", () => {
    // A graph-DB outage degrades target_canonical_name to null; with a target outside the
    // top-3 there's no name to show — a generic label, never the raw UUID.
    const uuid = "99999999-9999-9999-9999-999999999999";
    renderCard({
      candidate: candidate({
        proposal: "merge",
        target_entity_id: uuid,
        target_canonical_name: null,
      }),
    });
    const badge = screen.getByTestId("proposal-badge");
    expect(badge).not.toHaveTextContent(uuid);
    expect(badge).toHaveTextContent(/existing entity/i);
  });

  it("shows each alternative's verification context and an honest name-match score (DM-EE-3/4)", () => {
    renderCard({
      candidate: candidate({
        alternatives: [
          {
            entity_id: "e1",
            canonical_name: "Jan",
            score: 100,
            type: "Character",
            aliases: ["Janek"],
            context_quote: "Jan crossed the yard.",
          },
        ],
      }),
    });
    const alt = screen.getAllByTestId("candidate-alternative")[0]!;
    // The score is framed as a *name* match, never a bare self-evident "(100)".
    expect(alt).toHaveTextContent("name match 100");
    expect(alt).not.toHaveTextContent("(100)");
    expect(screen.getByTestId("alternative-identity")).toHaveTextContent("Character");
    expect(screen.getByTestId("alternative-identity")).toHaveTextContent("Janek");
    expect(screen.getByTestId("alternative-quote")).toHaveTextContent("Jan crossed the yard");
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

  it("does not arm the merge affordance on a New card until a target is picked (DM-EE-6 amber fix)", () => {
    renderCard({ candidate: candidate({ proposal: "new", target_entity_id: null }) });
    expect(screen.getByTestId("accept-merge")).toHaveAttribute("data-armed", "false");
  });

  it("arms the merge affordance once a target is picked", () => {
    renderCard({ mergeTargetIndex: 1 });
    expect(screen.getByTestId("accept-merge")).toHaveAttribute("data-armed", "true");
  });
});

describe("CandidateCard — duplicate-create guard (DM-EE-5)", () => {
  it("warns and offers the merge instead of immediately creating a same-named duplicate", () => {
    const { onAct } = renderCard({ candidate: candidate({ candidate_name: "Jan" }) });
    fireEvent.click(screen.getByTestId("accept-create"));
    expect(onAct).not.toHaveBeenCalled();
    expect(screen.getByTestId("dup-warning")).toHaveTextContent("Jan");
  });

  it("'Merge instead' commits a merge into the existing same-named entity", () => {
    const { onAct } = renderCard({ candidate: candidate({ candidate_name: "Jan" }) });
    fireEvent.click(screen.getByTestId("accept-create"));
    fireEvent.click(screen.getByTestId("dup-warning-merge"));
    expect(onAct).toHaveBeenCalledWith({
      decision: "accept",
      accept: { action: "merge", target_entity_id: "e1" },
    });
  });

  it("'Create anyway' still creates the duplicate — the guard warns, never blocks (INV-1)", () => {
    const { onAct } = renderCard({ candidate: candidate({ candidate_name: "Jan" }) });
    fireEvent.click(screen.getByTestId("accept-create"));
    fireEvent.click(screen.getByTestId("dup-warning-create"));
    expect(onAct).toHaveBeenCalledWith({ decision: "accept", accept: { action: "create" } });
  });

  it("creates immediately when no same-named entity exists (no needless warning)", () => {
    // Default fixture candidate is "Janek" — no alternative shares that exact name.
    const { onAct } = renderCard();
    fireEvent.click(screen.getByTestId("accept-create"));
    expect(onAct).toHaveBeenCalledWith({ decision: "accept", accept: { action: "create" } });
    expect(screen.queryByTestId("dup-warning")).not.toBeInTheDocument();
  });
});

describe("CandidateCard — manual handpick (M3.S4d)", () => {
  it("threads the story id into the picker", () => {
    renderCard({ storyId: "s1" });
    expect(screen.getByTestId("entity-picker-stub")).toHaveAttribute("data-story-id", "s1");
  });

  it("a handpicked entity enables Merge and commits to it — even with no alternative picked", () => {
    const { onAct } = renderCard({ mergeTargetIndex: null });
    // No alternative picked → Merge starts disabled.
    expect(screen.getByTestId("accept-merge")).toBeDisabled();

    fireEvent.click(screen.getByTestId("entity-picker-stub"));

    expect(screen.getByTestId("accept-merge")).toBeEnabled();
    fireEvent.click(screen.getByTestId("accept-merge"));
    expect(onAct).toHaveBeenCalledWith({
      decision: "accept",
      accept: { action: "merge", target_entity_id: "handpicked-id" },
    });
  });

  it("a handpicked entity takes precedence over a picked alternative", () => {
    const { onAct } = renderCard({ mergeTargetIndex: 1 }); // alternative "e2" picked
    fireEvent.click(screen.getByTestId("entity-picker-stub")); // then handpick

    fireEvent.click(screen.getByTestId("accept-merge"));
    expect(onAct).toHaveBeenCalledWith({
      decision: "accept",
      accept: { action: "merge", target_entity_id: "handpicked-id" },
    });
  });

  it("picking an alternative after a handpick wins — the handpick is cleared (last pick wins)", () => {
    // Precedence is handpick-over-alternative *only while the handpick stands*; choosing an
    // alternative is a newer decision and must override the handpick, not be swallowed by it.
    const { onPickTarget } = renderCard({ mergeTargetIndex: null });
    fireEvent.click(screen.getByTestId("entity-picker-stub")); // handpick "handpicked-id"
    fireEvent.click(screen.getAllByTestId("candidate-alternative")[0]!); // then an alternative

    expect(onPickTarget).toHaveBeenCalledWith(0);
    // The handpick is gone, so the handpick "will merge into" hint clears.
    expect(screen.queryByTestId("handpick-target")).not.toBeInTheDocument();
  });

  it("shows which entity a handpick will merge into", () => {
    renderCard();
    fireEvent.click(screen.getByTestId("entity-picker-stub"));
    expect(screen.getByTestId("handpick-target")).toHaveTextContent("Katarzyna");
  });

  it("disables the picker while a decision is in flight", () => {
    renderCard({ pending: true });
    expect(screen.getByTestId("entity-picker-stub")).toHaveAttribute("data-disabled", "true");
  });
});
