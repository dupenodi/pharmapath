"use client";

import { useRef, useState } from "react";
import { postQuery } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import ComponentRouter from "./ComponentRouter";

function createSessionId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `session-${Date.now()}-${Math.random()}`;
}

export default function Chat() {
  const [sessionId] = useState(createSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const idCounter = useRef(0);

  async function send(text: string) {
    if (!text.trim() || loading) return;
    const userMsg: ChatMessage = { id: `m${idCounter.current++}`, role: "user", text, component: null, componentData: null, warnings: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const res = await postQuery(text, sessionId);
      // res.warnings are internal/developer diagnostics (e.g. "the model
      // skipped calling render_component") -- log them for debugging, never
      // show them in the chat thread itself.
      if (res.warnings.length > 0) console.warn("Agent diagnostics:", res.warnings);
      const assistantMsg: ChatMessage = {
        id: `m${idCounter.current++}`,
        role: "assistant",
        text: res.agent_response,
        component: res.component,
        componentData: res.component_data,
        warnings: res.warnings,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong talking to the backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-0 w-full max-w-4xl flex-1 flex-col px-4 py-6">
      <header className="mb-4">
        <h1 className="text-lg font-semibold text-zinc-100">EaseMed Supply Chain Intelligence</h1>
        <p className="text-sm text-zinc-500">Ask about drug supply chains, supplier matching, shortage risk, or compliance.</p>
      </header>

      <div className="flex-1 space-y-6 overflow-y-auto pb-4">
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "flex justify-end" : "flex flex-col items-start gap-2"}>
            {m.role === "user" ? (
              <div className="max-w-lg rounded-xl bg-zinc-100 px-4 py-2 text-sm text-zinc-900">{m.text}</div>
            ) : (
              <>
                <div className="max-w-lg rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-2 text-sm text-zinc-200">{m.text}</div>
                <ComponentRouter component={m.component} data={m.componentData} onDisambiguationSelect={send} />
              </>
            )}
          </div>
        ))}
        {loading && <div className="text-sm text-zinc-500">Thinking…</div>}
        {error && <div className="text-sm text-red-400">{error}</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex gap-2 border-t border-zinc-800 pt-4"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Find me a supplier to deliver 10,000 units of Acetaminophen to Chicago in 2 weeks"
          className="flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
