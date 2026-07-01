// Unit tests for the pure client-side navigation logic (Session 73, Graph-quality
// S2). No cytoscape runtime, no canvas — just the filter/degree/search transforms
// (the layout swap + pan-to is the browser-smoke boundary in GraphCanvas). Mirrors
// graphElements.test.ts: small `node()`/`edge()` builders + toCytoscapeElements to
// reach the same element shape filterGraph consumes.

import { describe, expect, it } from "vitest";

import type { GraphEdge, GraphNode, GraphResponse } from "../../lib/api/useStoryGraph";
import { toCytoscapeElements } from "./graphElements";
import { distinctTypes, filterGraph, matchNodes, nodeDegrees } from "./graphFilters";

function node(over: Partial<GraphNode> = {}): GraphNode {
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

function edge(over: Partial<GraphEdge> = {}): GraphEdge {
  return {
    id: "e1",
    type: "KNOWS",
    subject_id: "a",
    object_id: "b",
    confidence: 0.9,
    ...over,
  };
}

describe("nodeDegrees", () => {
  it("counts incident edges per node (subject and object both count)", () => {
    const degrees = nodeDegrees([
      edge({ subject_id: "a", object_id: "b" }),
      edge({ subject_id: "a", object_id: "c" }),
    ]);
    expect(degrees.a).toBe(2);
    expect(degrees.b).toBe(1);
    expect(degrees.c).toBe(1);
  });

  it("leaves an edgeless node out (degree read as 0/absent)", () => {
    const degrees = nodeDegrees([edge({ subject_id: "a", object_id: "b" })]);
    expect(degrees.z ?? 0).toBe(0);
  });

  it("returns an empty map for no edges", () => {
    expect(nodeDegrees([])).toEqual({});
  });

  it("counts a self-loop as degree 2 (both incidences)", () => {
    expect(nodeDegrees([edge({ subject_id: "a", object_id: "a" })]).a).toBe(2);
  });
});

describe("distinctTypes", () => {
  it("returns sorted, de-duplicated types present in the payload", () => {
    const types = distinctTypes([
      node({ type: "Location" }),
      node({ type: "Character" }),
      node({ type: "Location" }),
    ]);
    expect(types).toEqual(["Character", "Location"]);
  });

  it("returns an empty list for no nodes", () => {
    expect(distinctTypes([])).toEqual([]);
  });
});

describe("filterGraph", () => {
  const graph: GraphResponse = {
    nodes: [
      node({ id: "a", type: "Character" }),
      node({ id: "b", type: "Location" }),
      node({ id: "c", type: "Character" }),
    ],
    edges: [
      edge({ id: "e1", subject_id: "a", object_id: "b" }),
      edge({ id: "e2", subject_id: "a", object_id: "c" }),
    ],
  };
  const elements = toCytoscapeElements(graph);

  function nodeIds(els: ReturnType<typeof toCytoscapeElements>): string[] {
    return els.filter((el) => !("source" in el.data)).map((el) => el.data.id as string);
  }
  function edgeIds(els: ReturnType<typeof toCytoscapeElements>): string[] {
    return els.filter((el) => "source" in el.data).map((el) => el.data.id as string);
  }

  it("passes every node when no filter is active", () => {
    const out = filterGraph(elements, {});
    expect(nodeIds(out).sort()).toEqual(["a", "b", "c"]);
    expect(edgeIds(out).sort()).toEqual(["e1", "e2"]);
  });

  it("keeps only nodes of a selected type", () => {
    const out = filterGraph(elements, { types: ["Character"] });
    expect(nodeIds(out).sort()).toEqual(["a", "c"]);
  });

  it("drops nodes below the minimum degree", () => {
    // Degrees over this set: a=2, b=1, c=1. minDegree 2 keeps only `a`.
    const out = filterGraph(elements, { minDegree: 2 });
    expect(nodeIds(out)).toEqual(["a"]);
  });

  it("AND-combines the type and degree axes", () => {
    // Character AND degree>=2 → `a` only (c is Character but degree 1).
    const out = filterGraph(elements, { types: ["Character"], minDegree: 2 });
    expect(nodeIds(out)).toEqual(["a"]);
  });

  it("drops edges whose endpoint was filtered out (would crash cytoscape)", () => {
    // Keep only Location `b`: both edges touch `a`, which is gone → no edges survive.
    const out = filterGraph(elements, { types: ["Location"] });
    expect(nodeIds(out)).toEqual(["b"]);
    expect(edgeIds(out)).toEqual([]);
  });

  it("computes degree from the passed element set, not a wider count", () => {
    // A single edge a–b in isolation: a and b are degree 1, so minDegree 2 empties it.
    const twoNodeElements = toCytoscapeElements({
      nodes: [node({ id: "a" }), node({ id: "b" })],
      edges: [edge({ id: "e1", subject_id: "a", object_id: "b" })],
    });
    expect(nodeIds(filterGraph(twoNodeElements, { minDegree: 2 }))).toEqual([]);
  });

  it("returns an empty set when nothing matches", () => {
    expect(filterGraph(elements, { types: ["Nonexistent"] })).toEqual([]);
  });
});

describe("matchNodes", () => {
  const nodes: GraphNode[] = [
    node({ id: "a", canonical_name_pl: "Młyn", canonical_name_en: null, aliases: [] }),
    node({ id: "b", canonical_name_pl: null, canonical_name_en: "The Mill", aliases: [] }),
    node({ id: "c", canonical_name_pl: null, canonical_name_en: null, aliases: ["Święte"] }),
  ];

  it("matches on the PL canonical name (case-insensitive substring)", () => {
    expect(matchNodes("mły", nodes)).toEqual(["a"]);
  });

  it("matches on the EN canonical name", () => {
    expect(matchNodes("mill", nodes)).toEqual(["b"]);
  });

  it("matches on an alias", () => {
    expect(matchNodes("święte", nodes)).toEqual(["c"]);
  });

  it("folds diacritics — an accent-free term matches an accented name", () => {
    expect(matchNodes("mlyn", nodes)).toEqual(["a"]);
    expect(matchNodes("swiete", nodes)).toEqual(["c"]);
  });

  it("returns every id whose name contains the term", () => {
    const many = [
      node({ id: "a", canonical_name_pl: "Janek Młynarz" }),
      node({ id: "b", canonical_name_pl: "Młyn" }),
    ];
    expect(matchNodes("mły", many).sort()).toEqual(["a", "b"]);
  });

  it("returns an empty list for an empty or whitespace term", () => {
    expect(matchNodes("", nodes)).toEqual([]);
    expect(matchNodes("   ", nodes)).toEqual([]);
  });

  it("returns an empty list when nothing matches", () => {
    expect(matchNodes("zzz", nodes)).toEqual([]);
  });
});
