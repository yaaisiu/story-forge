// LLM status query hook (Session 17 — M2.S5 agent-activity panel).
//
// Reads `GET /llm/status` — today's spend against the cap, GPU-seconds, the
// per-task-type breakdown, and the most recent call (`last_call`) — for the §8.5
// agent-activity panel. Short-polls so the panel reflects activity live while an
// extraction run is in flight; the endpoint is a cheap aggregate read.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type LlmStatusResponse = components["schemas"]["LlmStatusResponse"];
export type LastCall = components["schemas"]["LastCall"];

/** How often the panel re-polls `/llm/status` while mounted (ms). */
export const LLM_STATUS_POLL_MS = 5_000;

export function useLlmStatus(): UseQueryResult<LlmStatusResponse, ApiError> {
  return useQuery<LlmStatusResponse, ApiError>({
    queryKey: ["llm-status"],
    queryFn: () => getJson<LlmStatusResponse>("/llm/status"),
    refetchInterval: LLM_STATUS_POLL_MS,
  });
}
