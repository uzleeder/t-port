"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { JourneyCard } from "./JourneyCard";
import { ApiError, clientApi } from "@/lib/api";
import { understoodAs, type InterpretResponse } from "@/lib/assistant";

const EXAMPLES = [
  "Cheapest way from Tashkent to Samarkand tomorrow",
  "Fastest train to Bukhara from Tashkent on Friday",
  "Samarqanddan Buxoroga ertaga",
  "Samarkand to Khiva tomorrow, arrive by 6 pm, fewest changes",
  "Compare train and bus from Tashkent to Samarkand",
];

export function Assistant() {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<InterpretResponse | null>(null);

  async function ask(value: string) {
    const q = value.trim();
    if (!q) return;
    setPending(true);
    setError(null);
    try {
      setAnswer(await clientApi<InterpretResponse>("/api/v1/ai/interpret", {
        method: "POST",
        body: JSON.stringify({ text: q }),
      }));
    } catch (e) {
      setAnswer(null);
      setError(e instanceof ApiError ? e.message : "The assistant is unavailable right now.");
    } finally {
      setPending(false);
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
        className="flex w-full items-center gap-3 rounded-2xl border border-dashed border-blue/50 bg-surface/50 px-4 py-3 text-left text-muted transition hover:border-blue hover:text-ink">
        <span aria-hidden="true" className="text-gold">✦</span>
        Or describe your trip in your own words — “cheapest way to Samarkand tomorrow”
      </button>
    );
  }

  const r = answer?.results;
  return (
    <section aria-labelledby={`${id}-h`} className="rounded-2xl border border-blue/40 bg-surface/90 p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <h2 id={`${id}-h`} className="flex items-center gap-2 font-semibold">
          <span aria-hidden="true" className="text-gold">✦</span> Journey assistant
        </h2>
        <button type="button" onClick={() => setOpen(false)} className="text-sm text-muted hover:text-ink">
          Close
        </button>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); void ask(text); }} className="mt-3 flex flex-col gap-2 sm:flex-row">
        <label htmlFor={`${id}-q`} className="sr-only">Describe your trip</label>
        <input id={`${id}-q`} value={text} onChange={(e) => setText(e.target.value)} maxLength={500} autoFocus
          placeholder="e.g. Fastest way from Tashkent to Bukhara on Friday morning"
          className="flex-1 rounded-xl border border-line bg-navy px-3 py-3 text-ink placeholder:text-muted/60 focus:border-blue" />
        <button type="submit" disabled={pending || !text.trim()}
          className="rounded-xl bg-blue px-5 py-3 font-semibold text-white hover:bg-blue-hover disabled:opacity-60">
          {pending ? "Thinking…" : "Ask"}
        </button>
      </form>
      <div className="mt-2 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button key={ex} type="button" onClick={() => { setText(ex); void ask(ex); }}
            className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:border-blue hover:text-ink">
            {ex}
          </button>
        ))}
      </div>

      <div aria-live="polite" className="mt-4 space-y-3">
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        {answer?.needs_clarification && (
          <p className="rounded-xl border border-gold/50 px-4 py-3 text-sm text-gold">{answer.clarification}</p>
        )}
        {answer && !answer.needs_clarification && understoodAs(answer.intent).length > 0 && (
          <ul aria-label="Understood as" className="flex flex-wrap gap-1.5">
            {understoodAs(answer.intent).map((c) => (
              <li key={c} className="rounded-full bg-blue/15 px-2.5 py-0.5 text-xs text-ink">{c}</li>
            ))}
          </ul>
        )}
        {answer?.explanation && <p className="text-sm leading-relaxed">{answer.explanation}</p>}
        {r && r.items.length > 0 && (
          <ol className="space-y-2">
            {r.items.slice(0, 3).map((j) => (
              <li key={j.id}><JourneyCard journey={j} /></li>
            ))}
          </ol>
        )}
        {answer?.search_query && (
          <Link href={`/search?${answer.search_query}`} className="inline-block text-sm text-blue hover:underline">
            See all {r?.total ?? ""} results with filters →
          </Link>
        )}
        {answer && (
          <p className="text-xs text-muted">
            Understood by {answer.engine === "rules" ? "T-Port's built-in parser" : "an AI model"}
            {answer.fallback_used ? " (AI unavailable, used fallback)" : ""}. {answer.disclaimer}
          </p>
        )}
      </div>
    </section>
  );
}
