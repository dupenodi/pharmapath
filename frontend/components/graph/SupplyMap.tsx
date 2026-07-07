"use client";

import { useEffect, useState } from "react";
import { fetchEntity, fetchNeighborhood } from "@/lib/api";
import type { EntityDetail, Neighborhood } from "@/lib/types";
import { NODE_META } from "@/lib/graphStyle";
import SearchBar from "./SearchBar";
import GraphCanvas from "./GraphCanvas";
import Monograph from "./Monograph";

// Hardcoded to specific Drug records (not resolved via search) so the first
// click always lands on a real product monograph -- a name-only lookup would
// rank the ActiveIngredient hub first (it always has the highest degree),
// never showing a newcomer the actual NDC/equivalents/manufacturer record.
const DEFAULT_DRUG_ID = "drug:0480-3588";

const EXAMPLES = [
  { label: "Atorvastatin", id: DEFAULT_DRUG_ID },
  { label: "Amoxicillin", id: "drug:83112-500" },
  { label: "Lisinopril", id: "drug:24979-243" },
  { label: "Metformin", id: "drug:72336-095" },
  { label: "Gabapentin", id: "drug:0071-0805" },
  { label: "Omeprazole", id: "drug:80425-0169" },
];

const LEGEND_TYPES = ["Drug", "ActiveIngredient", "Manufacturer", "Facility", "Distributor", "Geography"];

export default function SupplyMap() {
  const [history, setHistory] = useState<string[]>([DEFAULT_DRUG_ID]);
  const [neighborhood, setNeighborhood] = useState<{ id: string; data: Neighborhood } | null>(null);
  const [detail, setDetail] = useState<{ id: string; data: EntityDetail } | null>(null);
  // Hide the example chips while the search dropdown is showing -- they'd
  // otherwise occupy the same space as results for short result lists.
  const [searchOverlayVisible, setSearchOverlayVisible] = useState(false);

  const selectedId = history[history.length - 1] ?? null;

  function open(id: string) {
    setHistory((h) => (h[h.length - 1] === id ? h : [...h, id]));
  }
  function back() {
    setHistory((h) => h.slice(0, -1));
  }
  function reset() {
    setHistory([]);
  }

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    fetchNeighborhood(selectedId).then((d) => !cancelled && setNeighborhood({ id: selectedId, data: d }));
    fetchEntity(selectedId).then((d) => !cancelled && setDetail({ id: selectedId, data: d }));
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  // ---- Empty state ----
  if (!selectedId) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-4">
        <div className="w-full max-w-xl text-center">
          <p className="mb-3 text-[12px] font-medium uppercase tracking-[0.2em] text-faint">EaseMed · Supply Map</p>
          <h1 className="mb-3 text-balance font-serif text-3xl leading-tight text-foreground" style={{ fontFamily: "var(--font-newsreader), Georgia, serif" }}>
            Trace any drug to its makers, ingredients, equivalents, and licensed distributors.
          </h1>
          <p className="mb-7 text-sm text-muted">Start with a product name and follow the chain from there.</p>
          <SearchBar onSelect={open} size="hero" autoFocus onOverlayChange={setSearchOverlayVisible} />
          <div
            className={`mt-5 flex flex-wrap justify-center gap-2 transition-opacity ${
              searchOverlayVisible ? "pointer-events-none opacity-0" : "opacity-100"
            }`}
          >
            {EXAMPLES.map((ex) => (
              <button
                key={ex.id}
                onClick={() => open(ex.id)}
                className="rounded-full border border-border px-3 py-1.5 text-xs text-muted transition-colors hover:border-[var(--border-strong)] hover:text-foreground"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const nb = neighborhood?.id === selectedId ? neighborhood.data : null;
  const det = detail?.id === selectedId ? detail.data : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Control bar */}
      <div className="flex items-center gap-3 border-b border-border px-4 py-2.5">
        <button
          onClick={back}
          disabled={history.length < 2}
          className="rounded-md border border-border px-2 py-1.5 text-muted transition-colors enabled:hover:text-foreground disabled:opacity-40"
          aria-label="Back"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
        <div className="max-w-md flex-1">
          <SearchBar onSelect={open} />
        </div>
        <button onClick={reset} className="text-xs text-faint transition-colors hover:text-foreground">
          Clear
        </button>
      </div>

      {/* Map + record. Mobile: stacked, this region scrolls as a whole.
          Desktop (lg): fixed side-by-side split; only the record scrolls internally,
          so the map's height is never at the mercy of the record's content length. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden">
        <div className="relative h-[55vh] shrink-0 map-field lg:h-full lg:min-h-0 lg:flex-1">
          {nb ? (
            <GraphCanvas data={nb} focalId={selectedId} onSelect={open} />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-faint">Mapping the network…</div>
          )}
          {nb?.truncated && (
            <div className="absolute left-3 top-3 rounded-md border border-border bg-surface/90 px-2.5 py-1 text-[11px] text-muted backdrop-blur">
              Showing {nb.nodes.length - 1} of {nb.total_degree} connections
            </div>
          )}
          {/* Legend */}
          <div className="absolute bottom-3 left-3 flex flex-wrap gap-x-3 gap-y-1 rounded-lg border border-border bg-surface/90 px-3 py-2 backdrop-blur">
            {LEGEND_TYPES.map((t) => (
              <span key={t} className="flex items-center gap-1.5 text-[11px] text-muted">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: NODE_META[t].color }} />
                {NODE_META[t].label}
              </span>
            ))}
          </div>
        </div>

        <div className="border-t border-border bg-surface lg:h-full lg:w-[400px] lg:min-h-0 lg:shrink-0 lg:border-l lg:border-t-0">
          {det ? (
            <Monograph detail={det} onSelect={open} />
          ) : (
            <div className="flex h-64 items-center justify-center text-sm text-faint">Loading record…</div>
          )}
        </div>
      </div>
    </div>
  );
}
