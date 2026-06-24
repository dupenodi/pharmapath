import type { DisambiguationPromptData } from "@/lib/types";

export default function DisambiguationPrompt({
  data,
  onSelect,
}: {
  data: DisambiguationPromptData;
  onSelect: (label: string) => void;
}) {
  return (
    <div className="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
      <p className="mb-3 text-sm text-zinc-300">
        I found multiple matches{data?.query ? ` for "${data.query}"` : ""}. Which did you mean?
      </p>
      <div className="flex flex-wrap gap-2">
        {(data?.options ?? []).map((opt) => (
          <button
            key={opt.drug_id}
            onClick={() => onSelect(opt.label)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-200 hover:border-zinc-500 hover:bg-zinc-800"
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
