import type { ComparisonCardData } from "@/lib/types";

function fieldLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function Side({ data }: { data: Record<string, unknown> }) {
  const title = (data?.name ?? data?.generic_name ?? data?.supplier_name ?? data?.id ?? "Unknown") as string;
  const entries = Object.entries(data ?? {}).filter(([k]) => k !== "name" && k !== "id");
  return (
    <div className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
      <h3 className="mb-3 font-semibold text-zinc-100">{title}</h3>
      <dl className="space-y-2 text-sm">
        {entries.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3">
            <dt className="text-zinc-500">{fieldLabel(k)}</dt>
            <dd className="text-right text-zinc-200">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function ComparisonCard({ data }: { data: ComparisonCardData }) {
  if (!data?.left || !data?.right) {
    return <p className="text-sm text-zinc-500">Not enough data to compare.</p>;
  }
  return (
    <div className="flex w-full max-w-3xl gap-4">
      <Side data={data.left} />
      <Side data={data.right} />
    </div>
  );
}
