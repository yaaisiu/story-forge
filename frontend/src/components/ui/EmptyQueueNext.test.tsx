// Pins the emptied-queue onward navigation (S7): the feature's own message survives, and the
// successor link points where the caller said — the thing that turns a dead end into a flow.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { EmptyQueueNext } from "./EmptyQueueNext";

// No default for `storyId`: an explicitly-passed `undefined` still triggers a JS default
// parameter, so the missing-story case would silently render the present-story one.
function renderNext(storyId: string | undefined) {
  return render(
    <MemoryRouter>
      <EmptyQueueNext
        message="Nothing to review — every candidate has been decided."
        storyId={storyId}
        next="relations"
        label="Decide relations"
        testId="queue-empty"
      />
    </MemoryRouter>,
  );
}

describe("EmptyQueueNext", () => {
  it("keeps the feature's own empty message under its existing test id", () => {
    renderNext("s1");
    expect(screen.getByTestId("queue-empty")).toHaveTextContent(
      "Nothing to review — every candidate has been decided.",
    );
  });

  it("offers the next curation step as a link built from the story and the next segment", () => {
    renderNext("s1");
    const link = screen.getByTestId("queue-empty-next");
    expect(link).toHaveTextContent("Decide relations");
    expect(link).toHaveAttribute("href", "/stories/s1/relations");
  });

  it("degrades to message-only without a story rather than linking to /stories/undefined/…", () => {
    renderNext(undefined);
    expect(screen.getByTestId("queue-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("queue-empty-next")).not.toBeInTheDocument();
  });
});
