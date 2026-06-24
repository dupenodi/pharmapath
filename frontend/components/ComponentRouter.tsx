import type { ComponentName } from "@/lib/types";
import ComparisonCard from "./ComparisonCard";
import DisambiguationPrompt from "./DisambiguationPrompt";
import MapView from "./MapView";
import RiskCard from "./RiskCard";
import SupplierTable from "./SupplierTable";
import SupplyChainGraph from "./SupplyChainGraph";

export default function ComponentRouter({
  component,
  data,
  onDisambiguationSelect,
}: {
  component: ComponentName | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
  onDisambiguationSelect: (label: string) => void;
}) {
  if (!component || !data) return null;

  switch (component) {
    case "supply_chain_graph":
      return <SupplyChainGraph data={data} />;
    case "supplier_table":
      return <SupplierTable data={data} />;
    case "risk_card":
      return <RiskCard data={data} />;
    case "map_view":
      return <MapView data={data} />;
    case "comparison_card":
      return <ComparisonCard data={data} />;
    case "disambiguation_prompt":
      return <DisambiguationPrompt data={data} onSelect={onDisambiguationSelect} />;
    default:
      return null;
  }
}
