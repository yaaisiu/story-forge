// Agent-activity panel (Session 17 — M2.S5, spec §8.5).
//
// A small persistent panel that makes the multi-model + agent architecture legible
// to anyone browsing the UI: which agent ran most recently, the model/tier the
// router chose, that call's latency and cost, plus today's running totals and the
// budget headroom. Polls `GET /llm/status` (short interval) so it reflects activity
// live during an extraction run.
//
// Ollama Cloud GPU-quota *remaining* is intentionally not shown: it needs Ollama
// Cloud's account API and is a tracked deferral (docs/PLAN_SHORT.md). We show the
// GPU-seconds the ledger has *observed* today, never a fabricated remaining figure.

import { useLlmStatus, type LastCall } from "../../lib/api/useLlmStatus";

function formatUsd(value: number): string {
  return `$${value.toFixed(2)}`;
}

function formatLatency(ms: number | null): string {
  if (ms === null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms} ms`;
}

function LastCallRow({ call }: { call: LastCall }) {
  return (
    <dl data-testid="activity-last-call" className="flex flex-col gap-1.5 text-sm">
      <div className="flex justify-between gap-2">
        <dt className="text-gray-500">Agent</dt>
        <dd data-testid="activity-task-type" className="font-medium text-gray-900">
          {call.task_type}
        </dd>
      </div>
      <div className="flex justify-between gap-2">
        <dt className="text-gray-500">Tier / model</dt>
        <dd className="text-right text-gray-800">
          {call.tier}
          {call.model ? ` · ${call.model}` : ""}
        </dd>
      </div>
      <div className="flex justify-between gap-2">
        <dt className="text-gray-500">Latency</dt>
        <dd data-testid="activity-latency" className="text-gray-800">
          {formatLatency(call.latency_ms)}
        </dd>
      </div>
      <div className="flex justify-between gap-2">
        <dt className="text-gray-500">Cost / GPU</dt>
        <dd className="text-gray-800">
          {call.cost_estimate !== null
            ? formatUsd(call.cost_estimate)
            : call.gpu_seconds !== null
              ? `${call.gpu_seconds.toFixed(1)} GPU-s`
              : "free"}
        </dd>
      </div>
      <div className="flex justify-between gap-2">
        <dt className="text-gray-500">Outcome</dt>
        <dd className="text-gray-800">{call.outcome}</dd>
      </div>
    </dl>
  );
}

export function AgentActivityPanel() {
  const { data, isError } = useLlmStatus();

  return (
    <section
      data-testid="agent-activity-panel"
      className="flex w-64 shrink-0 flex-col gap-4 rounded-lg border border-gray-200 bg-white p-4"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-700">
        Agent activity
      </h2>

      {isError && (
        <p data-testid="activity-error" role="alert" className="text-sm text-red-700">
          Couldn&rsquo;t load activity.
        </p>
      )}

      {data && (
        <>
          <div>
            <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
              Most recent call
            </h3>
            {data.last_call ? (
              <LastCallRow call={data.last_call} />
            ) : (
              <p data-testid="activity-no-calls" className="text-sm text-gray-500">
                No calls yet.
              </p>
            )}
          </div>

          <div className="border-t border-gray-100 pt-3">
            <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
              Today
            </h3>
            <dl className="flex flex-col gap-1.5 text-sm">
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Spent / budget</dt>
                <dd data-testid="activity-spend" className="text-gray-800">
                  {formatUsd(data.spent_today_usd)} / {formatUsd(data.daily_budget_usd)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Remaining</dt>
                <dd data-testid="activity-remaining" className="text-gray-800">
                  {formatUsd(data.remaining_usd)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">GPU-seconds</dt>
                <dd className="text-gray-800">{data.gpu_seconds_today.toFixed(1)}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-gray-500">Calls</dt>
                <dd data-testid="activity-calls" className="text-gray-800">
                  {data.calls_today}
                </dd>
              </div>
            </dl>
          </div>
        </>
      )}
    </section>
  );
}
