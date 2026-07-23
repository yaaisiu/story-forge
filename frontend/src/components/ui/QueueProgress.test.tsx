// Pins the queue position indicator's contract (S7): 1-based display over a 0-based cursor,
// and nothing at all for an empty queue (which renders `EmptyQueueNext` instead).

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { QueueProgress } from "./QueueProgress";

describe("QueueProgress", () => {
  it("renders the 0-based cursor as a 1-based position", () => {
    render(<QueueProgress selectedIndex={0} total={12} />);
    expect(screen.getByTestId("queue-progress")).toHaveTextContent("1 of 12 remaining");
  });

  it("tracks the cursor as it moves down the queue", () => {
    render(<QueueProgress selectedIndex={4} total={12} />);
    expect(screen.getByTestId("queue-progress")).toHaveTextContent("5 of 12 remaining");
  });

  it("renders nothing when the queue is empty", () => {
    render(<QueueProgress selectedIndex={0} total={0} />);
    expect(screen.queryByTestId("queue-progress")).not.toBeInTheDocument();
  });
});
