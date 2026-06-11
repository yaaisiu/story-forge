// Tests for the agent-activity panel (Session 17 — M2.S5, spec §8.5).
//
// The panel reads useLlmStatus; we mock that hook's module so the test asserts the
// panel's rendering contract (most-recent call + today's totals, the no-calls and
// error states) without a fetch or a poll timer.

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LlmStatusResponse } from "../../lib/api/useLlmStatus";

const useLlmStatus = vi.fn();
vi.mock("../../lib/api/useLlmStatus", () => ({
  useLlmStatus: () => useLlmStatus(),
}));

// Imported after the mock is registered.
const { AgentActivityPanel } = await import("./AgentActivityPanel");

function ok(data: LlmStatusResponse) {
  return { data, isError: false } as ReturnType<typeof useLlmStatus>;
}

const STATUS: LlmStatusResponse = {
  daily_budget_usd: 5.0,
  spent_today_usd: 1.25,
  remaining_usd: 3.75,
  gpu_seconds_today: 12.5,
  calls_today: 4,
  by_task_type: [],
  last_call: {
    task_type: "extraction",
    tier: "cloud_free",
    provider: "OllamaProvider",
    model: "gpt-oss:120b-cloud",
    outcome: "success",
    latency_ms: 842,
    cost_estimate: null,
    gpu_seconds: 3.5,
    created_at: "2026-06-11T09:30:00Z",
  },
};

function renderPanel(): void {
  render(<AgentActivityPanel />);
}

afterEach(() => {
  useLlmStatus.mockReset();
});

describe("AgentActivityPanel", () => {
  it("shows the most recent call and today's totals", () => {
    useLlmStatus.mockReturnValue(ok(STATUS));
    renderPanel();

    expect(screen.getByTestId("activity-task-type")).toHaveTextContent("extraction");
    expect(screen.getByTestId("activity-latency")).toHaveTextContent("842 ms");
    expect(screen.getByTestId("activity-spend")).toHaveTextContent("$1.25 / $5.00");
    expect(screen.getByTestId("activity-remaining")).toHaveTextContent("$3.75");
    expect(screen.getByTestId("activity-calls")).toHaveTextContent("4");
  });

  it("formats sub-second-and-over latency in seconds", () => {
    useLlmStatus.mockReturnValue(
      ok({ ...STATUS, last_call: { ...STATUS.last_call!, latency_ms: 1500 } }),
    );
    renderPanel();
    expect(screen.getByTestId("activity-latency")).toHaveTextContent("1.50 s");
  });

  it("says 'no calls yet' before any call", () => {
    useLlmStatus.mockReturnValue(ok({ ...STATUS, last_call: null }));
    renderPanel();
    expect(screen.getByTestId("activity-no-calls")).toBeInTheDocument();
  });

  it("renders an error state when the status fetch fails", () => {
    useLlmStatus.mockReturnValue({ data: undefined, isError: true });
    renderPanel();
    expect(screen.getByTestId("activity-error")).toBeInTheDocument();
  });
});
