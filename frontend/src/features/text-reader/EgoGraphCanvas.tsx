// The cytoscape mount for the side panel's 1-hop ego-graph (Session 35 — M4.S2b,
// spec §3.5, DM-SP-4).
//
// Same boundary discipline as graph-viewer/GraphCanvas: this is the one reader-panel
// component that touches cytoscape's *runtime*, isolated behind a thin prop interface
// (elements come from the pure `toEgoElements` mapper; a neighbour tap calls
// `onSelectNeighbour` so the panel can re-target to that entity — DM-SP-4 "inspect
// nodes"). cytoscape renders to a real canvas jsdom can't drive, so this is verified by
// the browser smoke walk while everything around it (the panel, the mappers) is unit-
// tested with this module mocked. Keeping the canvas boundary tiny keeps the untested
// surface tiny.
//
// DM-SP-4 is a *verify-at-build* call: cytoscape reused in a ~288px column vs a static
// view. We reuse cytoscape (one renderer, node colours + taps inherited); the layout is
// confirmed in the browser, flagged in the PR.

import { useEffect, useRef } from "react";

import cytoscape from "cytoscape";

import type { EntityDetailResponse } from "../../lib/api/useEntityDetail";
import { toEgoElements } from "./egoElements";
import { colorForType } from "./palette";

interface EgoGraphCanvasProps {
  detail: EntityDetailResponse;
  /** Tap a neighbour node → inspect that entity (the focal node is not re-selectable). */
  onSelectNeighbour: (entityId: string) => void;
}

export function EgoGraphCanvas({ detail, onSelectNeighbour }: EgoGraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const cy = cytoscape({
      container,
      elements: toEgoElements(detail),
      // `cose` is force-directed (matches the main graph viewer); a 1-hop neighbourhood
      // is a handful of nodes, so it settles instantly. `animate: false` keeps it
      // deterministic in the narrow panel.
      layout: { name: "cose", animate: false },
      // Disable user zoom/pan: the panel is a fixed mini-view, not an explorable canvas.
      userZoomingEnabled: false,
      userPanningEnabled: false,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": (ele) => colorForType(ele.data("type") as string),
            color: "#1f2937",
            "font-size": "9px",
            "text-valign": "center",
            "text-halign": "right",
            "text-margin-x": 3,
            width: 16,
            height: 16,
          },
        },
        {
          // The focal entity stands out: larger, ringed.
          selector: "node[?focal]",
          style: {
            width: 24,
            height: 24,
            "border-width": 3,
            "border-color": "#1f2937",
            "font-weight": "bold",
            "font-size": "11px",
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

    // Only neighbours navigate — tapping the focal node would re-fetch what's already shown.
    cy.on("tap", "node", (event) => {
      const id = event.target.id();
      if (id !== detail.entity_id) onSelectNeighbour(id);
    });

    return () => cy.destroy();
  }, [detail, onSelectNeighbour]);

  return (
    <div
      data-testid="ego-graph-canvas"
      ref={containerRef}
      className="h-56 w-full rounded border border-gray-200 bg-gray-50"
    />
  );
}
