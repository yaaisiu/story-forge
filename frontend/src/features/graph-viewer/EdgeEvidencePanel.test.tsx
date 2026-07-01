// Tests for the edge-evidence side panel (Session 76 — Graph-quality S3b).
//
// Presentational + pure (the container owns the fetch): asserts each state — no
// selection, loading, error, populated (predicate + source quote/paragraph), and the
// zero-provenance "added manually" affordance — plus the close-button dispatch.

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EdgeEvidencePanel } from "./EdgeEvidencePanel";
import type { EdgeEvidence } from "../../lib/api/useEdgeEvidence";

const EDGE_ID = "33333333-3333-3333-3333-333333333333";

const EVIDENCE: EdgeEvidence = {
  predicate: "TRAVELS_WITH",
  source_provenance: [
    {
      paragraph_id: "44444444-4444-4444-4444-444444444444",
      paragraph_text: "Janek and Katarzyna left the mill together at dawn.",
      evidence_quote: "left the mill together",
    },
  ],
};

function renderPanel(over: Partial<Parameters<typeof EdgeEvidencePanel>[0]> = {}) {
  const onClose = vi.fn();
  const onRetry = vi.fn();
  render(
    <EdgeEvidencePanel
      edgeId={EDGE_ID}
      evidence={EVIDENCE}
      isPending={false}
      onRetry={onRetry}
      onClose={onClose}
      {...over}
    />,
  );
  return { onClose, onRetry };
}

describe("EdgeEvidencePanel", () => {
  it("prompts to select an edge when none is selected", () => {
    renderPanel({ edgeId: null });
    expect(screen.getByTestId("edge-evidence-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("edge-evidence")).not.toBeInTheDocument();
  });

  it("shows a loading state while the evidence is in flight", () => {
    renderPanel({ isPending: true, evidence: undefined });
    expect(screen.getByTestId("edge-evidence-loading")).toBeInTheDocument();
  });

  it("shows an error state with a working Retry when the read fails with no data", () => {
    const { onRetry } = renderPanel({ evidence: undefined });
    expect(screen.getByTestId("edge-evidence-error")).toBeInTheDocument();
    // Re-tapping the same edge is a no-op, so recovery must be an explicit refetch.
    fireEvent.click(screen.getByTestId("edge-evidence-retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("keeps the last-good evidence visible when a background refetch fails (no blanking)", () => {
    // TanStack keeps `data` across a background-refetch error; the panel must not throw
    // away what the user is reading. isPending is false (data in hand) → render, not error.
    renderPanel({ isPending: false, evidence: EVIDENCE });
    expect(screen.getByTestId("edge-evidence")).toBeInTheDocument();
    expect(screen.queryByTestId("edge-evidence-error")).not.toBeInTheDocument();
  });

  it("renders the predicate and each source paragraph with its quote", () => {
    renderPanel();
    expect(screen.getByTestId("edge-evidence-predicate")).toHaveTextContent("TRAVELS_WITH");
    const sources = screen.getAllByTestId("edge-evidence-source");
    expect(sources).toHaveLength(1);
    expect(sources[0]).toHaveTextContent("left the mill together");
    expect(sources[0]).toHaveTextContent("Janek and Katarzyna left the mill");
  });

  it("shows all sources when one fact is attested in several paragraphs (one-to-many)", () => {
    renderPanel({
      evidence: {
        predicate: "KNOWS",
        source_provenance: [
          { paragraph_id: "p1", paragraph_text: "First mention.", evidence_quote: "a" },
          { paragraph_id: "p2", paragraph_text: "Second mention.", evidence_quote: "b" },
        ],
      },
    });
    expect(screen.getAllByTestId("edge-evidence-source")).toHaveLength(2);
  });

  it("says 'added manually' for a zero-provenance edge instead of an empty/broken panel", () => {
    renderPanel({ evidence: { predicate: "KNOWS", source_provenance: [] } });
    expect(screen.getByTestId("edge-evidence-none")).toHaveTextContent(/added manually/i);
    expect(screen.queryByTestId("edge-evidence-source")).not.toBeInTheDocument();
  });

  it("tolerates a null predicate", () => {
    renderPanel({ evidence: { predicate: null, source_provenance: [] } });
    expect(screen.getByTestId("edge-evidence-predicate")).toHaveTextContent(/unknown/i);
  });

  it("dispatches onClose from the close button", () => {
    const { onClose } = renderPanel();
    fireEvent.click(screen.getByTestId("edge-evidence-close"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
