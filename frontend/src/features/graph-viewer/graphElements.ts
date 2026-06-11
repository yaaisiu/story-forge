// Pure mapping from the API's GraphResponse to cytoscape elements + the
// colour-by-type palette (spec §3.4: "nodes coloured by type, edges labelled with
// relation type"). Kept free of cytoscape *runtime* (only its element type, which
// is erased) and of React, so it stays unit-testable in CI without a canvas — the
// GraphCanvas mount that actually renders is the real-browser-smoke boundary.

import type { ElementDefinition } from "cytoscape";

import type { GraphNode, GraphResponse } from "../../lib/api/useStoryGraph";

// A small fixed palette. Types are open-world (INV-4), so we can't enumerate them;
// instead we hash the type string to a stable slot — the same type always gets the
// same colour within and across renders, without hardcoding a type→colour map.
const PALETTE = [
  "#2563eb", // blue
  "#16a34a", // green
  "#db2777", // pink
  "#d97706", // amber
  "#7c3aed", // violet
  "#0891b2", // cyan
  "#dc2626", // red
  "#4b5563", // gray
] as const;

/** Stable colour for an entity type — same string → same palette slot. */
export function colorForType(type: string): string {
  let hash = 0;
  for (let i = 0; i < type.length; i++) {
    hash = (hash * 31 + type.charCodeAt(i)) | 0;
  }
  // `% length` is always in range; the `?? PALETTE[0]` satisfies noUncheckedIndexedAccess.
  return PALETTE[Math.abs(hash) % PALETTE.length] ?? PALETTE[0];
}

/** Display label for a node: PL canonical, then EN, then first alias, then type. */
export function nodeLabel(node: GraphNode): string {
  return node.canonical_name_pl ?? node.canonical_name_en ?? node.aliases[0] ?? node.type;
}

/**
 * Project a GraphResponse to cytoscape elements. Edges whose endpoints aren't in
 * the node set are dropped — the backend only returns within-project edges, but a
 * dangling edge would make cytoscape throw, so we guard defensively (cheap, and it
 * keeps the no-dedupe M2 graph robust to a half-written relation).
 */
export function toCytoscapeElements(graph: GraphResponse): ElementDefinition[] {
  const nodeIds = new Set(graph.nodes.map((n) => n.id));
  const nodes: ElementDefinition[] = graph.nodes.map((n) => ({
    data: { id: n.id, label: nodeLabel(n), type: n.type },
  }));
  const edges: ElementDefinition[] = graph.edges
    .filter((e) => nodeIds.has(e.subject_id) && nodeIds.has(e.object_id))
    .map((e) => ({
      data: { id: e.id, source: e.subject_id, target: e.object_id, label: e.type },
    }));
  return [...nodes, ...edges];
}
