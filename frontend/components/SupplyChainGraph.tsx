"use client";

import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { useEffect, useRef, useState } from "react";
import type { GraphNode, SupplyChainGraphData } from "@/lib/types";
import { EDGE_LABEL, nodeColor, nodeLabel } from "@/lib/graphStyle";

export default function SupplyChainGraph({ data }: { data: SupplyChainGraphData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);

  useEffect(() => {
    if (!containerRef.current || !data) return;

    const elements: ElementDefinition[] = [
      ...data.nodes.map((n) => ({ data: { id: n.id, label: nodeLabel(n), raw: n }, classes: n.type })),
      ...data.edges.map((e, i) => ({
        data: { id: `e${i}`, source: e.source, target: e.target, label: EDGE_LABEL[e.type] ?? e.type },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": (el) => nodeColor(el.data("raw")),
            label: "data(label)",
            color: "#e4e4e7",
            "font-size": 10,
            "text-valign": "bottom",
            "text-margin-y": 4,
            width: 28,
            height: 28,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#52525b",
            "target-arrow-color": "#52525b",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            color: "#a1a1aa",
          },
        },
      ],
      layout: { name: "cose", animate: false },
    });

    cy.on("tap", "node", (evt) => setSelected(evt.target.data("raw")));
    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [data]);

  return (
    <div className="flex w-full max-w-3xl gap-3">
      <div ref={containerRef} className="h-96 flex-1 rounded-xl border border-zinc-800 bg-zinc-950/60" />
      {selected && (
        <div className="w-64 shrink-0 rounded-xl border border-zinc-800 bg-zinc-900/60 p-3 text-xs text-zinc-300">
          <div className="mb-2 font-semibold text-zinc-100">{nodeLabel(selected)}</div>
          <div className="mb-2 text-zinc-500">{selected.type}</div>
          <dl className="space-y-1">
            {Object.entries(selected)
              .filter(([k]) => !["id", "type", "raw_names"].includes(k))
              .slice(0, 8)
              .map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <dt className="text-zinc-500">{k}</dt>
                  <dd className="truncate text-right text-zinc-300">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
                </div>
              ))}
          </dl>
        </div>
      )}
    </div>
  );
}
