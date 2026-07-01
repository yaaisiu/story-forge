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

import { useCallback, useEffect, useMemo, useState } from "react";

import { useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { AgentActivityPanel } from "../agent-activity/AgentActivityPanel";
import { ApiError, useExtractStory } from "../../lib/api/useExtractStory";
import {
  storyGraphQueryKey,
  useStoryGraph,
  type GraphNode,
  type GraphScope,
} from "../../lib/api/useStoryGraph";
import { GraphCanvas } from "./GraphCanvas";
import { toCytoscapeElements } from "./graphElements";
import { distinctTypes, filterGraph, matchNodes, nodeDegrees } from "./graphFilters";
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

  // §3.4 client-side navigation state (DM-GN-1: all filtering runs over the payload
  // already fetched, no backend round-trip). Empty `selectedTypes` = no type
  // constraint (all types shown); `minDegree` 0 = no density constraint.
  const [selectedTypes, setSelectedTypes] = useState<ReadonlySet<string>>(new Set());
  const [minDegree, setMinDegree] = useState(0);
  const [searchTerm, setSearchTerm] = useState("");
  // Debounce the search box so a dense graph doesn't recompute the focus set per
  // keystroke (search only highlights/pans — it never re-runs the layout).
  const debouncedTerm = useDebouncedValue(searchTerm, 200);

  // Stable identity so GraphCanvas's effect doesn't rebuild cytoscape every render.
  const handleSelectNode = useCallback((nodeId: string) => setSelectedNodeId(nodeId), []);

  // Clear the selection when the scope changes: a node picked in the whole-project
  // view may not exist in the narrower story view, and a stale id would just blank
  // the details panel with no explanation.
  function handleScopeChange(next: GraphScope) {
    setScope(next);
    setSelectedNodeId(null);
  }

  const nodes = useMemo(() => graph.data?.nodes ?? [], [graph.data]);

  // The type-filter options are derived from the data present (INV-4: types are
  // open-world, never a hardcoded enum). Degree is computed over the *scoped* edge
  // set, so density is honest under the story/project toggle.
  const typeOptions = useMemo(() => distinctTypes(nodes), [nodes]);
  const degrees = useMemo(() => nodeDegrees(graph.data?.edges ?? []), [graph.data]);
  const maxDegree = useMemo(() => Math.max(0, ...Object.values(degrees)), [degrees]);

  // The client-side pipeline: full payload → cytoscape elements → AND-combined
  // type/degree filter → the visible subset GraphCanvas lays out (memoized for a
  // stable prop identity so the canvas rebuilds only when the visible set changes).
  const activeTypes = useMemo(() => [...selectedTypes], [selectedTypes]);
  const baseElements = useMemo(
    () => (graph.data ? toCytoscapeElements(graph.data) : []),
    [graph.data],
  );
  const visibleElements = useMemo(
    () => filterGraph(baseElements, { types: activeTypes, minDegree }),
    [baseElements, activeTypes, minDegree],
  );
  const visibleNodeIds = useMemo(
    () =>
      new Set(
        visibleElements.filter((el) => !("source" in el.data)).map((el) => el.data.id as string),
      ),
    [visibleElements],
  );

  // Search is focus-not-filter (DM-GN-4): match over the whole scoped node set, then
  // highlight/pan only the matches still visible. If matches exist but every one is
  // hidden by an active filter, say so rather than appear to "do nothing".
  const matchedIds = useMemo(
    () => (debouncedTerm.trim() ? matchNodes(debouncedTerm, nodes) : []),
    [debouncedTerm, nodes],
  );
  const focusNodeIds = useMemo(
    () => matchedIds.filter((id) => visibleNodeIds.has(id)),
    [matchedIds, visibleNodeIds],
  );
  const searchHidden = matchedIds.length > 0 && focusNodeIds.length === 0;

  const totalCount = nodes.length;
  const visibleCount = visibleNodeIds.size;

  // A refetch (e.g. after an extraction run) can drop a type the filter had selected.
  // Prune the active set to what's still present so a now-absent value can't silently
  // constrain the graph to nothing.
  useEffect(() => {
    setSelectedTypes((prev) => {
      const pruned = new Set([...prev].filter((t) => typeOptions.includes(t)));
      return pruned.size === prev.size ? prev : pruned;
    });
  }, [typeOptions]);

  // Reactive mirror of handleScopeChange's clear: if a filter hides the selected
  // node, drop the selection rather than leave the details panel showing a node no
  // longer on the canvas.
  useEffect(() => {
    if (selectedNodeId && !visibleNodeIds.has(selectedNodeId)) setSelectedNodeId(null);
  }, [selectedNodeId, visibleNodeIds]);

  function toggleType(type: string) {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  function handleClearFilters() {
    setSelectedTypes(new Set());
    setMinDegree(0);
    setSearchTerm("");
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
  // Every active filter ANDs down to zero: show a "clear filters" affordance, never
  // an unexplained blank canvas.
  const noMatch = graph.isSuccess && nodeCount > 0 && visibleCount === 0;

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

      {graph.isSuccess && nodeCount > 0 && (
        <div
          data-testid="graph-filters"
          className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-gray-200 bg-white p-3 text-sm"
        >
          {/* Type filter — options derived from the data (INV-4), AND-combined. */}
          <div
            data-testid="type-filter"
            role="group"
            aria-label="Filter by entity type"
            className="flex flex-wrap items-center gap-2"
          >
            <span className="text-gray-600">Types:</span>
            {typeOptions.map((type) => {
              const active = selectedTypes.has(type);
              return (
                <button
                  key={type}
                  type="button"
                  data-testid={`type-filter-${type}`}
                  aria-pressed={active}
                  onClick={() => toggleType(type)}
                  className={
                    active
                      ? "rounded-full bg-blue-600 px-3 py-1 font-medium text-white"
                      : "rounded-full border border-gray-300 px-3 py-1 text-gray-700 hover:bg-gray-50"
                  }
                >
                  {type}
                </button>
              );
            })}
          </div>

          {/* Connection-density filter — node degree over the scoped edge set. */}
          <label className="flex items-center gap-2 text-gray-600">
            Min. connections: <span className="font-medium text-gray-900">{minDegree}</span>
            <input
              data-testid="degree-filter"
              type="range"
              min={0}
              max={maxDegree}
              value={minDegree}
              onChange={(e) => setMinDegree(Number(e.target.value))}
              aria-label="Minimum connections"
            />
          </label>

          {/* Name search — focuses/highlights + pans-to, does not hide the rest. */}
          <input
            data-testid="node-search"
            type="search"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Find by name…"
            aria-label="Find a node by name"
            className="rounded border border-gray-300 px-3 py-1"
          />

          <span data-testid="graph-match-count" className="text-gray-600">
            {visibleCount} of {totalCount} entities
          </span>
          {searchHidden && (
            <span data-testid="graph-search-hidden" role="status" className="text-amber-700">
              Match hidden by active filters.
            </span>
          )}
        </div>
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
            {graph.isSuccess &&
              nodeCount > 0 &&
              (noMatch ? (
                <p data-testid="graph-no-match" className="p-4 text-sm text-gray-500">
                  0 of {totalCount} entities match —{" "}
                  <button
                    type="button"
                    data-testid="clear-filters"
                    onClick={handleClearFilters}
                    className="underline hover:text-gray-700"
                  >
                    clear filters
                  </button>
                </p>
              ) : (
                <GraphCanvas
                  elements={visibleElements}
                  focusNodeIds={focusNodeIds}
                  onSelectNode={handleSelectNode}
                />
              ))}
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
