import type { RiskCardData } from "@/lib/types";

const RISK_BANNER: Record<string, string> = {
  low: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
  medium: "bg-amber-500/10 border-amber-500/30 text-amber-400",
  high: "bg-orange-500/10 border-orange-500/30 text-orange-400",
  critical: "bg-red-500/10 border-red-500/30 text-red-400",
};

export default function RiskCard({ data }: { data: RiskCardData }) {
  const risk = data?.risk_summary;
  const shortages = data?.shortages ?? [];
  const activeShortage = shortages.find((s) => s.status === "active");

  return (
    <div className="w-full max-w-xl rounded-xl border border-zinc-800 bg-zinc-950/60">
      <div className={`rounded-t-xl border-b px-4 py-3 ${RISK_BANNER[risk?.overall_risk ?? "low"]}`}>
        <div className="text-sm uppercase tracking-wide opacity-80">{data?.drug_name ?? "Risk summary"}</div>
        <div className="text-lg font-semibold capitalize">{risk?.overall_risk ?? "unknown"} risk</div>
      </div>
      <div className="space-y-4 px-4 py-4 text-sm">
        <section>
          <h3 className="mb-1 font-medium text-zinc-200">Shortage Status</h3>
          {activeShortage ? (
            <p className="text-zinc-400">
              Active as of {activeShortage.start_date ?? "unknown date"}. Reason: {activeShortage.reason ?? "not specified"}.
            </p>
          ) : (
            <p className="text-zinc-500">No active shortage found.</p>
          )}
        </section>
        <section>
          <h3 className="mb-1 font-medium text-zinc-200">Manufacturer Risk</h3>
          <p className="text-zinc-400">
            {risk ? `${risk.manufacturers_flagged} of ${risk.manufacturers_total} manufacturers have active flags.` : "No data."}
          </p>
        </section>
        {risk && risk.risk_flags.length > 0 && (
          <section>
            <h3 className="mb-1 font-medium text-zinc-200">Risk Flags</h3>
            <ul className="list-disc space-y-1 pl-4 text-zinc-400">
              {risk.risk_flags.map((flag, idx) => (
                <li key={idx}>{flag}</li>
              ))}
            </ul>
          </section>
        )}
        <p className="border-t border-zinc-800 pt-3 text-xs text-zinc-600">
          Compliance/shortage data last checked live from openFDA at query time.
        </p>
      </div>
    </div>
  );
}
