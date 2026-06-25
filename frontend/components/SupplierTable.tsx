"use client";

import { Fragment, useMemo, useState } from "react";
import type { SupplierMatch, SupplierTableData } from "@/lib/types";

const COMPLIANCE_BADGE: Record<SupplierMatch["compliance_status"], string> = {
  clean: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  flagged: "bg-red-500/15 text-red-400 border-red-500/30",
  unknown: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

const SHORTAGE_LABEL: Record<SupplierMatch["shortage_risk"], string> = {
  none: "None",
  possible: "Possible",
  confirmed: "Confirmed",
};

type SortKey = "score" | "supplier_name" | "compliance_status" | "shortage_risk";

export default function SupplierTable({ data }: { data: SupplierTableData }) {
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showAlternatives, setShowAlternatives] = useState(false);

  const matches = data?.matches ?? [];
  const alternatives = data?.alternatives ?? [];
  const sorted = useMemo(() => {
    const copy = [...matches];
    copy.sort((a, b) => {
      if (sortKey === "score") return b.score - a.score;
      const av = String(a[sortKey] ?? "");
      const bv = String(b[sortKey] ?? "");
      return av.localeCompare(bv);
    });
    return copy;
  }, [matches, sortKey]);

  const hasShortageRisk = matches.some((m) => m.shortage_risk !== "none");

  const headers: { key: SortKey; label: string }[] = [
    { key: "supplier_name", label: "Supplier" },
    { key: "score", label: "Score" },
    { key: "compliance_status", label: "Compliance" },
    { key: "shortage_risk", label: "Shortage Risk" },
  ];

  return (
    <div className="w-full rounded-xl border border-zinc-800 bg-zinc-950/60">
      {data?.explanation && <p className="border-b border-zinc-800 px-4 py-3 text-sm text-zinc-400">{data.explanation}</p>}
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-zinc-500">
            <th className="px-4 py-2 font-medium">Rank</th>
            {headers.map((h) => (
              <th key={h.key} className="px-4 py-2 font-medium">
                <button onClick={() => setSortKey(h.key)} className="hover:text-zinc-200">
                  {h.label} {sortKey === h.key && "↓"}
                </button>
              </th>
            ))}
            <th className="px-4 py-2 font-medium">Type</th>
            <th className="px-4 py-2 font-medium">States</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((m, i) => (
            <Fragment key={m.supplier_id}>
              <tr
                key={m.supplier_id}
                className="cursor-pointer border-t border-zinc-800 hover:bg-zinc-900/60"
                onClick={() => setExpanded(expanded === m.supplier_id ? null : m.supplier_id)}
              >
                <td className="px-4 py-3 text-zinc-500">{i + 1}</td>
                <td className="px-4 py-3 font-medium text-zinc-100">{m.supplier_name}</td>
                <td className="px-4 py-3 tabular-nums text-zinc-200">{m.score.toFixed(3)}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full border px-2 py-0.5 text-xs ${COMPLIANCE_BADGE[m.compliance_status]}`}>
                    {m.compliance_status}
                  </span>
                </td>
                <td className="px-4 py-3 text-zinc-300">{SHORTAGE_LABEL[m.shortage_risk]}</td>
                <td className="px-4 py-3 text-zinc-400">{m.supplier_type === "distributor" ? "Distributor" : "Manufacturer"}</td>
                <td className="px-4 py-3 text-zinc-400">{m.distance_km != null ? `${Math.round(m.distance_km)} km away` : "unknown"}</td>
              </tr>
              {expanded === m.supplier_id && (
                <tr className="border-t border-zinc-800 bg-zinc-900/40">
                  <td colSpan={7} className="px-4 py-3">
                    <div className="grid grid-cols-2 gap-4 text-xs text-zinc-400 sm:grid-cols-4">
                      {Object.entries(m.score_breakdown).map(([k, v]) => (
                        <div key={k}>
                          <span className="text-zinc-500">{k}: </span>
                          <span className="text-zinc-200">{v}</span>
                        </div>
                      ))}
                    </div>
                    {m.caveats.length > 0 && (
                      <ul className="mt-2 list-disc pl-4 text-xs text-amber-400/80">
                        {m.caveats.map((c, idx) => (
                          <li key={idx}>{c}</li>
                        ))}
                      </ul>
                    )}
                    {m.active_flags.length > 0 && (
                      <div className="mt-2 text-xs text-red-400/80">
                        {m.active_flags.length} active compliance flag(s) -- {m.active_flags.map((f) => f.flag_type).join(", ")}
                      </div>
                    )}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
      {sorted.length === 0 && <p className="px-4 py-6 text-center text-sm text-zinc-500">No qualifying suppliers found.</p>}
      {(hasShortageRisk || sorted.length === 0) && alternatives.length > 0 && (
        <div className="border-t border-zinc-800 px-4 py-3">
          <button
            onClick={() => setShowAlternatives((v) => !v)}
            className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-400"
          >
            {showAlternatives ? "Hide" : "Show"} therapeutic alternatives ({alternatives.length})
          </button>
          {showAlternatives && (
            <ul className="mt-3 space-y-1.5 text-sm">
              {alternatives.map((a) => (
                <li key={a.drug_id} className="flex items-center justify-between border-t border-zinc-800/60 pt-1.5 first:border-t-0 first:pt-0">
                  <span className="text-zinc-200">{a.brand_name || a.generic_name}</span>
                  <span className="text-xs uppercase tracking-wide text-zinc-500">Orange Book TE match</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
