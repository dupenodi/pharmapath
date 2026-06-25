"use client";

import { useEffect, useRef, useState } from "react";
import { fetchGraphNodes } from "@/lib/api";
import type { NodeListItem } from "@/lib/types";
import { typeColor, typeLabel } from "@/lib/graphStyle";

export default function SearchBar({
  onSelect,
  size = "default",
  autoFocus = false,
  onOverlayChange,
}: {
  onSelect: (id: string) => void;
  size?: "default" | "hero";
  autoFocus?: boolean;
  /** Fires when the results dropdown is showing/hiding, so a parent can keep
   * other content (e.g. example chips) from sharing screen space with it. */
  onOverlayChange?: (visible: boolean) => void;
}) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  // Keyed by the query it answers, so we never show stale results and never
  // call setState synchronously inside an effect.
  const [answered, setAnswered] = useState<{ q: string; items: NodeListItem[]; fuzzy: boolean } | null>(null);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const current = answered && answered.q === debounced ? answered : null;
  const results = current?.items ?? null;
  const overlayVisible = open && !!debounced;

  useEffect(() => {
    onOverlayChange?.(overlayVisible);
  }, [overlayVisible, onOverlayChange]);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 200);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    if (!debounced) return;
    let cancelled = false;
    fetchGraphNodes({ q: debounced, limit: 8 }).then((r) => {
      if (!cancelled) setAnswered({ q: debounced, items: r.items, fuzzy: !!r.fuzzy });
    });
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function pick(item: NodeListItem) {
    onSelect(item.id);
    setQuery("");
    setDebounced("");
    setOpen(false);
  }

  const hero = size === "hero";

  return (
    // isolate: own stacking context, so the dropdown's z-20 is unambiguously
    // composited above sibling content below it (e.g. the example chips).
    <div ref={boxRef} className="relative z-30 w-full isolate">
      <div className="relative">
        <svg
          className={`pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint ${hero ? "h-5 w-5" : "h-4 w-4"}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          autoFocus={autoFocus}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && results && results[0]) pick(results[0]);
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder="Search a drug, ingredient, manufacturer, or distributor…"
          className={`w-full rounded-xl border border-border bg-surface text-foreground outline-none transition-colors placeholder:text-faint focus:border-[var(--border-strong)] focus:ring-1 focus:ring-[var(--focus)]/40 ${
            hero ? "py-3.5 pl-11 pr-4 text-base" : "py-2 pl-9 pr-3 text-sm"
          }`}
        />
      </div>

      {open && results && results.length > 0 && (
        <ul className="absolute left-0 top-full z-20 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-border bg-surface p-1 shadow-2xl shadow-black/40">
          {current?.fuzzy && (
            <li className="px-2.5 pb-1 pt-1.5 text-[11px] text-faint">No exact match -- showing close matches</li>
          )}
          {results.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => pick(item)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-white/5"
              >
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: typeColor(item.type) }} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-foreground">{item.label}</span>
                </span>
                <span className="shrink-0 text-[11px] uppercase tracking-wide text-faint">{typeLabel(item.type)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {open && results && results.length === 0 && debounced && (
        <div className="absolute left-0 top-full z-20 mt-2 w-full rounded-xl border border-border bg-surface px-3 py-3 text-sm text-faint">
          No match for “{debounced}”.
        </div>
      )}
    </div>
  );
}
