// Unit tests for the pure GraphResponse → cytoscape mapping (Session 17, M2.S5).
// No cytoscape runtime, no canvas — just the data transform and the palette.

import { describe, expect, it } from "vitest";

import type { GraphResponse } from "../../lib/api/useStoryGraph";
import { colorForType, nodeLabel, toCytoscapeElements } from "./graphElements";

function node(over: Partial<GraphResponse["nodes"][number]> = {}): GraphResponse["nodes"][number] {
  return {
    id: "n1",
    type: "Character",
    canonical_name_pl: "Janek",
    canonical_name_en: null,
    aliases: [],
    first_seen_paragraph_id: null,
    ...over,
  };
}

describe("colorForType", () => {
  it("is deterministic — the same type always maps to the same colour", () => {
    expect(colorForType("Character")).toBe(colorForType("Character"));
    expect(colorForType("Location")).toBe(colorForType("Location"));
  });

  it("returns a hex colour from the palette", () => {
    expect(colorForType("Anything")).toMatch(/^#[0-9a-f]{6}$/i);
  });
});

describe("nodeLabel", () => {
  it("prefers PL canonical, then EN, then first alias, then type", () => {
    expect(nodeLabel(node({ canonical_name_pl: "Janek" }))).toBe("Janek");
    expect(nodeLabel(node({ canonical_name_pl: null, canonical_name_en: "Johnny" }))).toBe(
      "Johnny",
    );
    expect(
      nodeLabel(node({ canonical_name_pl: null, canonical_name_en: null, aliases: ["Młynarz"] })),
    ).toBe("Młynarz");
    expect(
      nodeLabel(
        node({ canonical_name_pl: null, canonical_name_en: null, aliases: [], type: "Object" }),
      ),
    ).toBe("Object");
  });
});

describe("toCytoscapeElements", () => {
  it("maps nodes (id/label/type) and edges (id/source/target/label)", () => {
    const graph: GraphResponse = {
      nodes: [
        node({ id: "a", type: "Character" }),
        node({ id: "b", type: "Location", canonical_name_pl: "Młyn" }),
      ],
      edges: [{ id: "e1", type: "LIVES_IN", subject_id: "a", object_id: "b", confidence: 0.9 }],
    };

    const elements = toCytoscapeElements(graph);

    expect(elements).toContainEqual({ data: { id: "a", label: "Janek", type: "Character" } });
    expect(elements).toContainEqual({ data: { id: "b", label: "Młyn", type: "Location" } });
    expect(elements).toContainEqual({
      data: { id: "e1", source: "a", target: "b", label: "LIVES_IN" },
    });
  });

  it("drops a dangling edge whose endpoint isn't in the node set (would crash cytoscape)", () => {
    const graph: GraphResponse = {
      nodes: [node({ id: "a" })],
      edges: [{ id: "e1", type: "KNOWS", subject_id: "a", object_id: "ghost", confidence: 0.5 }],
    };

    const elements = toCytoscapeElements(graph);

    expect(elements).toHaveLength(1); // only the node, no edge
    expect(elements.every((el) => !("source" in el.data))).toBe(true);
  });
});
