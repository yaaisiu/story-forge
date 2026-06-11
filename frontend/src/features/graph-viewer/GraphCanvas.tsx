// The cytoscape mount (Session 17 — M2.S5 graph viewer).
//
// This is the one component that touches cytoscape's *runtime*, isolated behind a
// thin prop interface (elements come from the pure `graphElements` mapper; node
// taps call `onSelectNode`). That isolation is deliberate: cytoscape renders to a
// real canvas, which jsdom can't drive, so this component is verified by the
// real-browser smoke walk, while everything around it (data states, the details
// panel, the activity panel) is unit-tested with this module mocked. Keeping the
// canvas boundary tiny keeps the untested surface tiny (the Session-6 lesson:
// the panel/canvas show data CI can't see — smoke-walk it in a browser).

import { useEffect, useRef } from "react";

import cytoscape from "cytoscape";

import type { GraphResponse } from "../../lib/api/useStoryGraph";
import { colorForType, toCytoscapeElements } from "./graphElements";

interface GraphCanvasProps {
  graph: GraphResponse;
  onSelectNode: (nodeId: string) => void;
}

export function GraphCanvas({ graph, onSelectNode }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const cy = cytoscape({
      container,
      elements: toCytoscapeElements(graph),
      // Force-directed layout (spec §3.4). `animate: false` keeps it deterministic
      // and avoids a long settle on large graphs (§3.4 must handle 500+ nodes).
      layout: { name: "cose", animate: false },
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

    return () => cy.destroy();
  }, [graph, onSelectNode]);

  return <div data-testid="graph-canvas" ref={containerRef} className="h-full w-full" />;
}
