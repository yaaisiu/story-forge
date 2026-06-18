// Pure mapping from the EntityDetailResponse bundle to cytoscape elements for the
// reader side panel's 1-hop ego-graph (M4.S2b, spec §3.5, DM-SP-2 / DM-SP-4).
//
// Mirrors graph-viewer/graphElements.ts in spirit but over a *single entity's*
// neighbourhood, not the whole project graph: the focal node, its direct neighbours,
// and only the edges incident to the focal node (oriented by `direction`). The focal
// node carries `focal: true` so the canvas can style it distinctly. Kept free of
// cytoscape *runtime* (only its element type, erased at compile) and of React, so it
// unit-tests without a canvas — the EgoGraphCanvas mount is the browser-smoke boundary.
//
// Fail-closed (Layer 6, [[referential-integrity]]): the backend already omits a
// dangling neighbour, but we still drop an edge whose `neighbour_id` isn't in the node
// set — a dangling edge would make cytoscape throw, same defensive guard graphElements
// applies to the whole-project graph.

import type { ElementDefinition } from "cytoscape";

import type { EgoNeighbour, EntityDetailResponse } from "../../lib/api/useEntityDetail";

/** Display label for a neighbour: PL canonical, then EN, then first alias, then type. */
export function egoNeighbourLabel(neighbour: EgoNeighbour): string {
  return (
    neighbour.canonical_name_pl ??
    neighbour.canonical_name_en ??
    neighbour.aliases?.[0] ??
    neighbour.type
  );
}

/**
 * Project an entity's detail bundle to cytoscape elements: the focal node (flagged),
 * its 1-hop neighbours, and the entity-incident edges oriented focal↔neighbour. An edge
 * to a neighbour absent from the bundle is dropped (dangling, fail-closed).
 */
export function toEgoElements(detail: EntityDetailResponse): ElementDefinition[] {
  const neighbours = detail.ego_graph.neighbours ?? [];
  const edges = detail.ego_graph.edges ?? [];

  const focalNode: ElementDefinition = {
    data: { id: detail.entity_id, label: detail.canonical_name, type: detail.type, focal: true },
  };
  const neighbourNodes: ElementDefinition[] = neighbours.map((n) => ({
    data: { id: n.entity_id, label: egoNeighbourLabel(n), type: n.type },
  }));

  const nodeIds = new Set<string>([detail.entity_id, ...neighbours.map((n) => n.entity_id)]);

  const edgeElements: ElementDefinition[] = edges
    .filter((e) => nodeIds.has(e.neighbour_id))
    .map((e) => ({
      data: {
        id: e.id,
        // `out` = focal is the subject (focal→neighbour); `in` = focal is the object.
        source: e.direction === "out" ? detail.entity_id : e.neighbour_id,
        target: e.direction === "out" ? e.neighbour_id : detail.entity_id,
        label: e.type,
      },
    }));

  return [focalNode, ...neighbourNodes, ...edgeElements];
}
