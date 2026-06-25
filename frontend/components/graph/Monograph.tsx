"use client";

import type { EntityDetail, GraphNode } from "@/lib/types";
import { typeColor, typeLabel } from "@/lib/graphStyle";

type Field = { label: string; value: string; mono?: boolean };

function str(v: unknown): string {
  if (v == null || v === "") return "";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

/** The identity fields shown at the top of the record, tuned per node type. */
function identityFields(node: GraphNode): Field[] {
  const t = node.type;
  if (t === "Drug") {
    return [
      { label: "Generic name", value: str(node.generic_name) },
      { label: "Brand name", value: str(node.brand_name) || "—" },
      { label: "Strength", value: str(node.strength) || "—" },
      { label: "Dosage form", value: str(node.dosage_form) || "—" },
      { label: "Route", value: str(node.route) || "—" },
      { label: "NDC", value: str(node.ndc_full), mono: true },
      { label: "FDA application", value: str(node.application_no) || "—", mono: true },
      { label: "Category", value: str(node.marketing_category) || "—" },
    ];
  }
  if (t === "Manufacturer") {
    return [
      { label: "Role", value: node.is_repackager ? "Repackager / relabeler" : "Manufacturer" },
      { label: "Known as", value: str((node.raw_names as string[])?.slice(0, 3)) },
      { label: "Country", value: str(node.country) || "—" },
      { label: "Classification source", value: str(node.repackager_source) || "—" },
    ];
  }
  if (t === "Facility") {
    return [
      { label: "Operations", value: str(node.operations) || "—" },
      { label: "Location", value: [str(node.city), str(node.state), str(node.country)].filter(Boolean).join(", ") },
      { label: "FEI number", value: str(node.fei_number) || "—", mono: true },
      { label: "Registered to", value: str(node.registrant_name) || "—" },
    ];
  }
  if (t === "Distributor") {
    const kind = node.distributor_type === "third_party_logistics" ? "Third-party logistics (3PL)" : "Wholesale distributor";
    const states = (node.states_licensed as string[]) || [];
    return [
      { label: "Type", value: kind },
      { label: "Coverage", value: node.national_coverage ? "National" : `${states.length} states` },
      { label: "Home state", value: str(node.home_state) || "—" },
      { label: "State licenses", value: String(node.license_count ?? states.length), mono: true },
    ];
  }
  if (t === "ActiveIngredient") {
    return [{ label: "Ingredient", value: str(node.name) }];
  }
  if (t === "Geography") {
    return [
      { label: "State", value: str(node.name) },
      { label: "Region", value: str(node.region) },
    ];
  }
  return [];
}

function headline(node: GraphNode): string {
  if (node.type === "Drug") {
    const generic = str(node.generic_name);
    const strength = str(node.strength);
    return [generic, strength].filter(Boolean).join(" · ");
  }
  if (node.type === "Distributor") {
    return node.national_coverage ? "Licensed nationwide" : `${(node.states_licensed as string[])?.length ?? 0} state licenses`;
  }
  if (node.type === "Facility") return str(node.operations);
  if (node.type === "Manufacturer") return node.is_repackager ? "Repackager" : "Drug manufacturer";
  return typeLabel(node.type);
}

export default function Monograph({
  detail,
  onSelect,
}: {
  detail: EntityDetail;
  onSelect: (id: string) => void;
}) {
  const node = detail.node;
  const color = typeColor(detail.type);
  const fields = identityFields(node).filter((f) => f.value);
  const status = str(node.status);

  return (
    <article className="flex h-full flex-col overflow-y-auto">
      {/* Header band */}
      <header className="border-b border-border px-6 py-5">
        <div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-muted">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
          {typeLabel(detail.type)}
          {detail.type === "Drug" && (
            <span className="rounded bg-border px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-muted">
              {node.otc ? "over-the-counter" : "prescription"}
            </span>
          )}
          {detail.type === "Drug" && node.is_generic ? (
            <span className="rounded bg-border px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-muted">
              generic
            </span>
          ) : null}
          {status === "discontinued" ? (
            <span className="rounded bg-amber-950/60 px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-amber-400">
              discontinued
            </span>
          ) : null}
        </div>
        <h2
          className="font-serif text-2xl leading-tight text-foreground"
          style={{ fontFamily: "var(--font-newsreader), Georgia, serif" }}
        >
          {detail.label}
        </h2>
        <p className="mt-1 text-sm text-muted">{headline(node)}</p>
      </header>

      {/* Identity fields */}
      <section className="grid grid-cols-2 gap-x-6 gap-y-3 px-6 py-5">
        {fields.map((f) => (
          <div key={f.label} className="min-w-0">
            <dt className="text-[11px] uppercase tracking-wide text-faint">{f.label}</dt>
            <dd className={`mt-0.5 break-words text-sm text-foreground ${f.mono ? "font-mono text-[13px]" : ""}`}>
              {f.value}
            </dd>
          </div>
        ))}
      </section>

      {/* Relationships */}
      {detail.connections.map((group) => (
        <section key={group.relation} className="border-t border-border px-6 py-4">
          <h3 className="mb-2 flex items-baseline gap-2 text-[11px] font-medium uppercase tracking-wider text-muted">
            {group.relation}
            <span className="tabular text-faint">{group.total > group.items.length ? `${group.items.length} of ${group.total}` : group.total}</span>
          </h3>
          <ul className="space-y-1">
            {group.items.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => onSelect(item.id)}
                  className="group flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-white/5"
                >
                  <span
                    className="mt-1 h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: typeColor(item.type) }}
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm text-foreground group-hover:text-white">{item.label}</span>
                    {item.caption ? <span className="block truncate text-xs text-faint">{item.caption}</span> : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </article>
  );
}
