// Pins the emptied-queue onward navigation (S7): the feature's own message survives, and the
// successor link points where the caller said — the thing that turns a dead end into a flow.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { EmptyQueueNext } from "./EmptyQueueNext";

function renderNext() {
  return render(
    <MemoryRouter>
      <EmptyQueueNext
        message="Nothing to review — every candidate has been decided."
        to="/stories/s1/relations"
        label="Decide relations"
        testId="queue-empty"
      />
    </MemoryRouter>,
  );
}

describe("EmptyQueueNext", () => {
  it("keeps the feature's own empty message under its existing test id", () => {
    renderNext();
    expect(screen.getByTestId("queue-empty")).toHaveTextContent(
      "Nothing to review — every candidate has been decided.",
    );
  });

  it("offers the next curation step as a link to the caller's target", () => {
    renderNext();
    const link = screen.getByTestId("queue-empty-next");
    expect(link).toHaveTextContent("Decide relations");
    expect(link).toHaveAttribute("href", "/stories/s1/relations");
  });
});
