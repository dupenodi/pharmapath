"use client";

import mapboxgl from "mapbox-gl";
import { useEffect, useRef, useState } from "react";
import type { Distributor, MapViewData } from "@/lib/types";

const STATE_CENTROIDS: Record<string, [number, number]> = {
  IL: [-88.99, 40.35],
  TX: [-97.56, 31.05],
  OH: [-82.76, 40.39],
  PA: [-77.21, 40.59],
};

function badgeColor(complianceKnown: boolean, flagged: boolean): string {
  if (!complianceKnown) return "#a1a1aa";
  return flagged ? "#f87171" : "#34d399";
}

export default function MapView({ data }: { data: MapViewData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [selected, setSelected] = useState<Distributor | null>(null);
  const [filterType, setFilterType] = useState<string | null>(null);
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  const distributors = (data?.distributors ?? []).filter((d) => !filterType || d.distributor_type === filterType);

  useEffect(() => {
    if (!containerRef.current || !token) return;
    mapboxgl.accessToken = token;

    const center = STATE_CENTROIDS[data?.state] ?? [-98.5, 39.8];
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center,
      zoom: data?.state ? 5 : 3,
    });
    mapRef.current = map;

    return () => map.remove();
  }, [data?.state, token]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const markers: mapboxgl.Marker[] = [];
    for (const dist of distributors) {
      const coords = STATE_CENTROIDS[dist.home_state];
      if (!coords) continue;
      const el = document.createElement("div");
      el.style.width = "14px";
      el.style.height = "14px";
      el.style.borderRadius = "50%";
      el.style.background = badgeColor(true, false);
      el.style.border = "2px solid white";
      el.style.cursor = "pointer";
      el.onclick = () => setSelected(dist);
      const marker = new mapboxgl.Marker(el).setLngLat(coords).addTo(map);
      markers.push(marker);
    }
    return () => markers.forEach((m) => m.remove());
  }, [distributors]);

  if (!token) {
    return (
      <div className="w-full max-w-2xl rounded-xl border border-zinc-800 bg-zinc-950/60 p-6 text-sm text-zinc-400">
        Map view requires <code className="text-zinc-300">NEXT_PUBLIC_MAPBOX_TOKEN</code> to be set. Showing distributor list
        instead:
        <ul className="mt-3 space-y-1">
          {distributors.map((d) => (
            <li key={d.id} className="flex justify-between border-b border-zinc-800 py-1">
              <span>{d.name}</span>
              <span className="text-zinc-500">{d.home_state}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl">
      <div className="mb-2 flex gap-2 text-xs">
        {["wholesale_distributor", "third_party_logistics"].map((t) => (
          <button
            key={t}
            onClick={() => setFilterType(filterType === t ? null : t)}
            className={`rounded-full border px-2 py-1 ${
              filterType === t ? "border-zinc-400 text-zinc-100" : "border-zinc-700 text-zinc-500"
            }`}
          >
            {t.replace("_", " ")}
          </button>
        ))}
      </div>
      <div ref={containerRef} className="h-80 rounded-xl border border-zinc-800" />
      {selected && (
        <div className="mt-2 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-xs text-zinc-300">
          <div className="font-semibold text-zinc-100">{selected.name}</div>
          <div>License: {selected.id}</div>
          <div>States covered: {selected.national_coverage ? "All 50 states" : selected.states_licensed.join(", ")}</div>
        </div>
      )}
    </div>
  );
}
