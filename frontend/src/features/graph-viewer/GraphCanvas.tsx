// The cytoscape mount (Session 17 — M2.S5 graph viewer; Session 73 — S2 navigation).
//
// This is the one component that touches cytoscape's *runtime*, isolated behind a
// thin prop interface (elements come pre-filtered from GraphViewer's pure pipeline;
// node taps call `onSelectNode`; `focusNodeIds` drives the search highlight). That
// isolation is deliberate: cytoscape renders to a real canvas, which jsdom can't
// drive, so this component is verified by the real-browser smoke walk, while
// everything around it (data states, the details panel, the filters) is unit-tested
// with this module mocked. Keeping the canvas boundary tiny keeps the untested
// surface tiny (the Session-6 lesson: the panel/canvas show data CI can't see —
// smoke-walk it in a browser).

import { useEffect, useRef } from "react";

import cytoscape, { type Core, type ElementDefinition, type LayoutOptions } from "cytoscape";
import fcose from "cytoscape-fcose";

import { colorForType } from "./graphElements";

// fcose (fast CoSE) spreads a dense graph far better than the built-in `cose`
// hairball (DM-GN-2). Registered once at module load — cytoscape.use is idempotent.
cytoscape.use(fcose);

// fcose is a third-party layout, so its options aren't part of cytoscape's typed
// LayoutOptions union — describe the fields we set, then widen for the constructor.
// `animate: false` + `randomize: false` give a deterministic settle the browser
// smoke can assert (§3.4 must handle 500+ nodes without a long/nondeterministic run).
interface FcoseLayoutOptions {
  name: "fcose";
  animate: boolean;
  randomize: boolean;
}
const FCOSE_LAYOUT: FcoseLayoutOptions = { name: "fcose", animate: false, randomize: false };

interface GraphCanvasProps {
  // The already-filtered visible subset (GraphViewer runs the pure filter pipeline).
  elements: ElementDefinition[];
  // Ids of the current search matches — highlighted + panned-to, not filtered.
  focusNodeIds: string[];
  onSelectNode: (nodeId: string) => void;
}

export function GraphCanvas({ elements, focusNodeIds, onSelectNode }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // Rebuild + relayout whenever the visible element set changes. "Hide-and-relayout"
  // (DM-GN-4): a filter feeds a new element array and fcose re-spreads the visible
  // subset. `animate: false` + `randomize: false` keep the settle deterministic so
  // the browser smoke can assert a stable result (§3.4 must handle 500+ nodes).
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const cy = cytoscape({
      container,
      elements,
      layout: FCOSE_LAYOUT as unknown as LayoutOptions,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": (ele) => colorForType(ele.data("type") as string),
            color: "#1f2937",
            "font-size": "10px",
            "text-valign": "center",
            "text-halign": "right",
            "text-margin-x": 4,
            width: 18,
            height: 18,
          },
        },
        {
          // Search-match highlight: a bold ring so a found node stands out without
          // hiding the rest of the graph (search is focus-not-filter, DM-GN-4).
          selector: "node.search-match",
          style: {
            "border-width": 4,
            "border-color": "#f59e0b",
            width: 26,
            height: 26,
            "z-index": 10,
          },
        },
        {
          selector: "edge",
          style: {
            label: "data(label)",
            "font-size": "8px",
            color: "#6b7280",
            width: 1,
            "line-color": "#cbd5e1",
            "target-arrow-color": "#cbd5e1",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
      ],
    });

    cy.on("tap", "node", (event) => onSelectNode(event.target.id()));
    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [elements, onSelectNode]);

  // Search focus: highlight the matched nodes and pan to them, in place — never a
  // rebuild or relayout (the graph stays whole). Keyed on `elements` too so the
  // highlight re-applies after a filter rebuild; declared after the rebuild effect so
  // it runs against the fresh instance.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass("search-match");
    if (focusNodeIds.length === 0) return;
    const focus = new Set(focusNodeIds);
    const matched = cy.nodes().filter((n) => focus.has(n.id()));
    if (matched.nonempty()) {
      matched.addClass("search-match");
      cy.center(matched);
    }
  }, [elements, focusNodeIds]);

  return <div data-testid="graph-canvas" ref={containerRef} className="h-full w-full" />;
}
