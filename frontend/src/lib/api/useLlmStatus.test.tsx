// Tests for the LLM-status query hook (Session 17 — M2.S5 agent-activity panel).
//
// Pins: GETs /llm/status and resolves the typed LlmStatusResponse (budget, totals,
// and the most recent call). The short-poll interval isn't asserted here (it'd need
// fake timers); the first fetch resolving is what the panel needs.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLlmStatus } from "./useLlmStatus";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const STATUS_BODY = {
  daily_budget_usd: 5.0,
  spent_today_usd: 1.25,
  remaining_usd: 3.75,
  gpu_seconds_today: 12.5,
  calls_today: 4,
  by_task_type: [{ task_type: "extraction", calls: 4, cost_usd: 0.0 }],
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

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useLlmStatus", () => {
  it("GETs /llm/status and resolves the typed status response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, STATUS_BODY));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useLlmStatus(), { wrapper: buildWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(STATUS_BODY);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/llm\/status$/);
    expect(init.method).toBe("GET");
  });
});
