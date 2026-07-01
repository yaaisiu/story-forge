// Pure client-side navigation logic for the graph viewer (Session 73, Graph-quality
// S2, spec §3.4). Filtering + degree + name-search are computed over the payload
// `useStoryGraph` already fetched — no backend round-trip (DM-GN-1). Kept free of
// cytoscape *runtime* and React, exactly like graphElements.ts, so CI unit-tests it
// without a canvas; GraphCanvas does the imperative layout/pan-to that jsdom can't.

import type { ElementDefinition } from "cytoscape";

import type { GraphEdge, GraphNode } from "../../lib/api/useStoryGraph";

/** A cytoscape element is a node unless it carries a `source` (the edge idiom used
 *  throughout graphElements.ts / its tests). */
function isNodeElement(el: ElementDefinition): boolean {
  return !("source" in el.data);
}

/**
 * Node id → count of incident edges, over the given (already scope-filtered) edge
 * set — the "connection density" axis of the §3.4 filter. A structural edge type so
 * one implementation serves both the raw `GraphEdge[]` payload and cytoscape edge
 * elements (mapped to `{subject_id, object_id}`). A self-loop counts both incidences
 * (degree 2). An edgeless node is simply absent (read its degree as `?? 0`).
 */
export function nodeDegrees(
  edges: ReadonlyArray<Pick<GraphEdge, "subject_id" | "object_id">>,
): Record<string, number> {
  const degrees: Record<string, number> = {};
  for (const e of edges) {
    degrees[e.subject_id] = (degrees[e.subject_id] ?? 0) + 1;
    degrees[e.object_id] = (degrees[e.object_id] ?? 0) + 1;
  }
  return degrees;
}

/**
 * Sorted, de-duplicated entity types present in the payload — the type-filter's
 * option list. Derived from the data, never a hardcoded enum: types are open-world
 * (INV-4), so a fixed dropdown would silently drop any future type — the same
 * discipline `colorForType` uses (hash, don't enumerate).
 */
export function distinctTypes(nodes: ReadonlyArray<Pick<GraphNode, "type">>): string[] {
  return [...new Set(nodes.map((n) => n.type))].sort();
}

/**
 * AND-combine the type + minDegree axes over a cytoscape element set (DM-GN-4). An
 * empty/absent `types` imposes no type constraint; `minDegree` 0/absent imposes no
 * degree constraint. Degree is computed from the *edge elements in this set* (the
 * rendered, scope-filtered edges — not a cached project-wide count), so density is
 * honest under the story/project scope toggle. Edges whose endpoint got filtered out
 * are dropped (a dangling edge crashes cytoscape — the same guard toCytoscapeElements
 * applies to the raw payload).
 */
export function filterGraph(
  elements: ElementDefinition[],
  opts: { types?: readonly string[]; minDegree?: number },
): ElementDefinition[] {
  const typeSet = opts.types && opts.types.length > 0 ? new Set(opts.types) : null;
  const minDegree = opts.minDegree ?? 0;

  const edgeElements = elements.filter((el) => !isNodeElement(el));
  const degrees = nodeDegrees(
    edgeElements.map((el) => ({
      subject_id: el.data.source as string,
      object_id: el.data.target as string,
    })),
  );

  const keptNodeIds = new Set<string>();
  const nodes = elements.filter((el) => {
    if (!isNodeElement(el)) return false;
    if (typeSet && !typeSet.has(el.data.type as string)) return false;
    if ((degrees[el.data.id as string] ?? 0) < minDegree) return false;
    keptNodeIds.add(el.data.id as string);
    return true;
  });

  const edges = edgeElements.filter(
    (el) => keptNodeIds.has(el.data.source as string) && keptNodeIds.has(el.data.target as string),
  );

  return [...nodes, ...edges];
}

/** Lowercase + strip diacritics (NFD, drop combining marks) so an accent-free query
 *  matches an accented name — this is a Polish-first tool, so "mlyn" must find "Młyn"
 *  and "swiete" must find "Święte". Polish ł/Ł is a *distinct letter*, not a base +
 *  combining mark, so NFD leaves it untouched — fold it to `l` explicitly. */
function fold(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/ł/g, "l")
    .replace(/Ł/g, "L")
    .toLowerCase();
}

/**
 * Ids of the nodes whose PL/EN canonical name or any alias contains `term`
 * (diacritic-folded, case-insensitive substring). Empty/whitespace term → `[]` — a
 * blank search matches nothing rather than everything. Search is focus-not-filter
 * (DM-GN-4): the caller highlights + pans to these, it does not hide the rest.
 */
export function matchNodes(
  term: string,
  nodes: ReadonlyArray<
    Pick<GraphNode, "id" | "canonical_name_pl" | "canonical_name_en" | "aliases">
  >,
): string[] {
  const needle = fold(term.trim());
  if (!needle) return [];
  return nodes
    .filter((n) => {
      const haystacks = [n.canonical_name_pl, n.canonical_name_en, ...n.aliases];
      return haystacks.some((name) => name != null && fold(name).includes(needle));
    })
    .map((n) => n.id);
}
