// Tests for the node-details side panel (Session 17 — M2.S5).

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { GraphNode } from "../../lib/api/useStoryGraph";
import { NodeDetailsPanel } from "./NodeDetailsPanel";

const JANEK: GraphNode = {
  id: "n1",
  type: "Character",
  canonical_name_pl: "Janek",
  canonical_name_en: null,
  aliases: ["Janek z młyna", "młynarz"],
  first_seen_paragraph_id: "22222222-2222-2222-2222-222222222222",
};

describe("NodeDetailsPanel", () => {
  it("prompts to pick a node when none is selected", () => {
    render(<NodeDetailsPanel node={null} onClose={() => {}} />);
    expect(screen.getByTestId("node-details-empty")).toBeInTheDocument();
  });

  it("shows the selected node's name, type, aliases, and first-seen paragraph", () => {
    render(<NodeDetailsPanel node={JANEK} onClose={() => {}} />);

    expect(screen.getByRole("heading", { name: "Janek" })).toBeInTheDocument();
    expect(screen.getByTestId("node-details-type")).toHaveTextContent("Character");
    expect(screen.getByTestId("node-details-aliases")).toHaveTextContent("Janek z młyna, młynarz");
    expect(screen.getByTestId("node-details-first-seen")).toHaveTextContent(
      "22222222-2222-2222-2222-222222222222",
    );
  });

  it("invokes onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<NodeDetailsPanel node={JANEK} onClose={onClose} />);
    fireEvent.click(screen.getByTestId("node-details-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
