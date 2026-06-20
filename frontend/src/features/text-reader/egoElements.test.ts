import { describe, expect, it } from "vitest";

import { egoNeighbourLabel, toEgoElements } from "./egoElements";
import type { EntityDetailResponse } from "../../lib/api/useEntityDetail";

// The ego-graph mini-view (DM-SP-2 strict 1-hop, DM-SP-4 cytoscape) renders the focal
// entity, its direct neighbours, and only the edges incident to it. This pure mapper
// turns the EntityDetailResponse bundle into cytoscape elements; the focal node is
// flagged so the canvas can style it distinctly, edges are oriented by `direction`, and
// an edge to a neighbour the bundle didn't return is dropped (fail-closed, Layer 6 —
// the backend already omits dangling neighbours, but a dangling edge would make
// cytoscape throw, so we guard defensively as graphElements.ts does).
function detail(overrides: Partial<EntityDetailResponse> = {}): EntityDetailResponse {
  return {
    entity_id: "focal",
    canonical_name: "Elara",
    language: "en",
    type: "character",
    aliases: [],
    properties: {},
    ego_graph: { neighbours: [], edges: [] },
    ...overrides,
  };
}

describe("egoNeighbourLabel", () => {
  it("prefers PL canonical, then EN, then first alias, then type", () => {
    expect(egoNeighbourLabel({ entity_id: "n", type: "place", canonical_name_pl: "Dąb" })).toBe(
      "Dąb",
    );
    expect(egoNeighbourLabel({ entity_id: "n", type: "place", canonical_name_en: "Oak" })).toBe(
      "Oak",
    );
    expect(egoNeighbourLabel({ entity_id: "n", type: "place", aliases: ["the tree"] })).toBe(
      "the tree",
    );
    expect(egoNeighbourLabel({ entity_id: "n", type: "place" })).toBe("place");
  });
});

describe("toEgoElements", () => {
  it("returns just the focal node, flagged, when there are no neighbours", () => {
    expect(toEgoElements(detail())).toEqual([
      { data: { id: "focal", label: "Elara", type: "character", focal: true } },
    ]);
  });

  it("orients an outgoing edge focal→neighbour", () => {
    const elements = toEgoElements(
      detail({
        ego_graph: {
          neighbours: [{ entity_id: "n1", type: "place", canonical_name_pl: "Oakhaven" }],
          edges: [
            {
              id: "edge1",
              type: "lives_in",
              direction: "out",
              neighbour_id: "n1",
              confidence: 0.9,
            },
          ],
        },
      }),
    );
    expect(elements).toContainEqual({
      data: { id: "edge1", source: "focal", target: "n1", label: "lives_in" },
    });
    expect(elements).toContainEqual({ data: { id: "n1", label: "Oakhaven", type: "place" } });
  });

  it("orients an incoming edge neighbour→focal", () => {
    const elements = toEgoElements(
      detail({
        ego_graph: {
          neighbours: [{ entity_id: "n2", type: "character", canonical_name_pl: "Marek" }],
          edges: [
            { id: "edge2", type: "loves", direction: "in", neighbour_id: "n2", confidence: 0.8 },
          ],
        },
      }),
    );
    expect(elements).toContainEqual({
      data: { id: "edge2", source: "n2", target: "focal", label: "loves" },
    });
  });

  it("drops an edge whose neighbour is not in the bundle (dangling, fail-closed)", () => {
    const elements = toEgoElements(
      detail({
        ego_graph: {
          neighbours: [{ entity_id: "n1", type: "place", canonical_name_pl: "Oakhaven" }],
          edges: [
            { id: "ghost", type: "x", direction: "out", neighbour_id: "gone", confidence: 0.5 },
          ],
        },
      }),
    );
    expect(elements.some((e) => e.data.id === "ghost")).toBe(false);
    // The valid focal + neighbour nodes still render.
    expect(elements.map((e) => e.data.id).sort()).toEqual(["focal", "n1"]);
  });

  it("handles a missing ego_graph (neighbours/edges undefined) without throwing", () => {
    const elements = toEgoElements(detail({ ego_graph: {} }));
    expect(elements).toEqual([
      { data: { id: "focal", label: "Elara", type: "character", focal: true } },
    ]);
  });
});
