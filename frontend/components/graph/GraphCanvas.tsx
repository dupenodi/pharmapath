"use client";

import cytoscape, { type ElementDefinition } from "cytoscape";
import { useEffect, useRef } from "react";
import type { Neighborhood } from "@/lib/types";
import { EDGE_LABEL, nodeColor, nodeLabel } from "@/lib/graphStyle";

function shortLabel(s: string): string {
  return s.length > 26 ? s.slice(0, 24) + "…" : s;
}

export default function GraphCanvas({
  data,
  focalId,
  onSelect,
}: {
  data: Neighborhood;
  focalId: string;
  onSelect: (id: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  });

  useEffect(() => {
    if (!containerRef.current) return;

    const elements: ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: {
          id: n.id,
          label: shortLabel(nodeLabel(n)),
          color: nodeColor(n),
          focal: n.id === focalId ? 1 : 0,
        },
      })),
      ...data.edges.map((e, i) => ({
        data: {
          id: `e${i}`,
          source: e.source,
          target: e.target,
          label: EDGE_LABEL[e.type] ?? e.type.toLowerCase(),
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            "background-opacity": 0.95,
            label: "data(label)",
            color: "#cdd6e0",
            "font-size": 10,
            "font-family": "var(--font-geist-sans), sans-serif",
            "text-valign": "bottom",
            "text-margin-y": 5,
            "text-max-width": "120",
            "text-wrap": "wrap",
            width: 26,
            height: 26,
            "border-width": 0,
          },
        },
        {
          selector: "node[focal = 1]",
          style: {
            width: 46,
            height: 46,
            "border-width": 3,
            "border-color": "#cfe6ff",
            "border-opacity": 0.9,
            color: "#ffffff",
            "font-size": 12,
            "font-weight": 600,
            "z-index": 10,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "line-color": "#2c3a4c",
            "target-arrow-color": "#2c3a4c",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            "font-family": "var(--font-geist-sans), sans-serif",
            color: "#6f7c8d",
            "text-background-color": "#0d131c",
            "text-background-opacity": 0.9,
            "text-background-padding": "2",
          },
        },
        {
          selector: "node:active, node.hl",
          style: { "border-width": 3, "border-color": "#7dd3fc", "border-opacity": 0.9 },
        },
      ],
      layout: {
        name: "concentric",
        concentric: (n) => (n.data("focal") ? 10 : 1),
        levelWidth: () => 1,
        minNodeSpacing: 44,
        animate: false,
        padding: 28,
      },
      wheelSensitivity: 0.2,
      maxZoom: 2.5,
      minZoom: 0.3,
    });

    cy.one("layoutstop", () => cy.fit(undefined, 56));

    cy.on("tap", "node", (evt) => {
      const id = evt.target.id();
      if (id !== focalId) onSelectRef.current(id);
    });
    cy.on("mouseover", "node", (e) => {
      e.target.addClass("hl");
      if (containerRef.current) containerRef.current.style.cursor = "pointer";
    });
    cy.on("mouseout", "node", (e) => {
      e.target.removeClass("hl");
      if (containerRef.current) containerRef.current.style.cursor = "default";
    });

    return () => cy.destroy();
  }, [data, focalId]);

  return <div ref={containerRef} className="h-full w-full" />;
}
