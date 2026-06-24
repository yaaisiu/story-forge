// Graph viewer page (Session 17 — M2.S5, spec §3.4).
//
// Reads a story's entity graph and renders it force-directed (GraphCanvas), with a
// node-details side panel and the §8.5 agent-activity panel alongside. This page
// also hosts the extraction trigger: a freshly-structured story has no graph yet,
// so "Run extraction" POSTs to /stories/{id}/extract and then refetches the graph.
//
// Components render and dispatch; logic lives in the hooks (frontend/src/CLAUDE.md).
// The cytoscape mount is isolated in GraphCanvas (jsdom can't drive a canvas), so
// this container's behaviour — states, extraction, selection wiring — stays testable
// with GraphCanvas mocked; the canvas itself is covered by the real-browser smoke.

import { useCallback, useMemo, useState } from "react";

import { useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { AgentActivityPanel } from "../agent-activity/AgentActivityPanel";
import { ApiError, useExtractStory } from "../../lib/api/useExtractStory";
import {
  storyGraphQueryKey,
  useStoryGraph,
  type GraphNode,
  type GraphScope,
} from "../../lib/api/useStoryGraph";
import { GraphCanvas } from "./GraphCanvas";
import { NodeDetailsPanel } from "./NodeDetailsPanel";

function extractMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "Extraction failed. Please try again.";
  if (error.status === 404) return "That story no longer exists.";
  if (error.status === 502)
    return "The extraction agent failed (LLM unreachable or unusable output).";
  return error.detail || `Extraction failed (HTTP ${error.status}).`;
}

export function GraphViewer() {
  const { storyId } = useParams<{ storyId: string }>();
  const queryClient = useQueryClient();
  // §3.4 story-vs-project scope. `story` (default) narrows the shared project graph
  // to this story; `project` shows the whole project. Switching only changes the
  // query key, so useStoryGraph refetches (or repaints from cache) on its own.
  const [scope, setScope] = useState<GraphScope>("story");
  const graph = useStoryGraph(storyId, scope);
  const extract = useExtractStory();

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Stable identity so GraphCanvas's effect doesn't rebuild cytoscape every render.
  const handleSelectNode = useCallback((nodeId: string) => setSelectedNodeId(nodeId), []);

  // Clear the selection when the scope changes: a node picked in the whole-project
  // view may not exist in the narrower story view, and a stale id would just blank
  // the details panel with no explanation.
  function handleScopeChange(next: GraphScope) {
    setScope(next);
    setSelectedNodeId(null);
  }

  const selectedNode: GraphNode | null = useMemo(
    () => graph.data?.nodes.find((n) => n.id === selectedNodeId) ?? null,
    [graph.data, selectedNodeId],
  );

  function handleExtract() {
    if (!storyId) return;
    extract.mutate(
      { storyId },
      {
        onSuccess: () => {
          // A run writes new nodes/edges and a fresh ledger row: refetch both the
          // graph (so the viewer shows the new entities) and the status (so the
          // activity panel reflects the call that just ran, not on the next poll tick).
          void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
          void queryClient.invalidateQueries({ queryKey: ["llm-status"] });
        },
      },
    );
  }

  const nodeCount = graph.data?.nodes.length ?? 0;
  const isEmpty = graph.isSuccess && nodeCount === 0;

  return (
    <main className="flex h-screen flex-col gap-4 p-6">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Knowledge graph</h1>
          <p className="text-sm text-gray-600">
            Entities and relations extracted from this story. No deduplication yet — duplicates are
            expected and get resolved in a later milestone.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {/* §3.4 scope toggle: this story vs the whole (multi-story) project. */}
          <div
            data-testid="graph-scope-toggle"
            role="group"
            aria-label="Graph scope"
            className="flex overflow-hidden rounded border border-gray-300 text-sm"
          >
            {(
              [
                ["story", "This story"],
                ["project", "Whole project"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                data-testid={`scope-${value}`}
                aria-pressed={scope === value}
                onClick={() => handleScopeChange(value)}
                className={
                  scope === value
                    ? "bg-blue-600 px-3 py-2 font-medium text-white"
                    : "bg-white px-3 py-2 text-gray-700 hover:bg-gray-50"
                }
              >
                {label}
              </button>
            ))}
          </div>
          {storyId && (
            <Link
              to={`/stories/${storyId}/review`}
              data-testid="review-queue-link"
              className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Review queue
            </Link>
          )}
          {storyId && (
            <Link
              to={`/stories/${storyId}/relations`}
              data-testid="relations-link"
              className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Relations
            </Link>
          )}
          {storyId && (
            <Link
              to={`/stories/${storyId}/reader`}
              data-testid="reader-link"
              className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Read text
            </Link>
          )}
          <button
            type="button"
            data-testid="run-extraction"
            onClick={handleExtract}
            disabled={extract.isPending}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            {extract.isPending ? "Extracting…" : "Run extraction"}
          </button>
        </div>
      </header>

      {extract.isError && (
        <p data-testid="extraction-error" role="alert" className="text-sm text-red-700">
          {extractMessage(extract.error)}
        </p>
      )}
      {extract.data?.paused && (
        <p data-testid="extraction-paused" role="status" className="text-sm text-amber-700">
          Extraction paused ({extract.data.pause_reason ?? "budget/quota"}) after{" "}
          {extract.data.paragraphs_done}/{extract.data.paragraphs_total} paragraphs — click Run
          extraction again to resume.
        </p>
      )}

      <div className="flex min-h-0 flex-1 gap-4">
        <div className="flex min-h-0 flex-1 gap-0 overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
          <div className="relative min-h-0 flex-1">
            {graph.isPending && (
              <p data-testid="graph-loading" className="p-4 text-sm text-gray-500">
                Loading graph…
              </p>
            )}
            {graph.isError && (
              <p data-testid="graph-error" role="alert" className="p-4 text-sm text-red-700">
                Couldn&rsquo;t load the graph.
              </p>
            )}
            {isEmpty && (
              <p data-testid="graph-empty" className="p-4 text-sm text-gray-500">
                No entities yet. Run extraction to build the graph.
              </p>
            )}
            {graph.isSuccess && nodeCount > 0 && (
              <GraphCanvas graph={graph.data} onSelectNode={handleSelectNode} />
            )}
          </div>
          {graph.isSuccess && nodeCount > 0 && (
            <NodeDetailsPanel node={selectedNode} onClose={() => setSelectedNodeId(null)} />
          )}
        </div>

        <AgentActivityPanel />
      </div>
    </main>
  );
}
