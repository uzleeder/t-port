import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { Icon } from "../Icons";
import { ModeIcon } from "../ModeIcon";
import { T } from "../T";
import { TAILogo } from "../TAILogo";
import { formatDuration, formatMoney, localTime, marketToday } from "@/lib/format";
import type { Key } from "@/lib/i18n";
import { serverApi } from "@/lib/server-api";
import type { Journey, SearchResponse } from "@/lib/types";

const EXAMPLE_EN = "Find the best way to travel from Tashkent to Samarkand tomorrow.";
const MODE_KEY = { train: "search.train", bus: "search.bus", flight: "search.flight", taxi: "search.taxi" } as const;

/** T-AI introduction with its glass neural arrow and a sourced chat preview. */
export function AIPlannerShowcase() {
  return (
    <section aria-labelledby="ai-h" className="grid items-center gap-10 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <div className="reveal">
        <TAILogo size={176} className="h-32 w-32 sm:h-40 sm:w-40" />
        <p className="mt-8 text-xs font-semibold uppercase tracking-[0.32em] text-gold">T-AI</p>
        <h2 id="ai-h" className="mt-3 text-3xl font-extrabold leading-tight tracking-tight sm:text-5xl">
          <span className="block">
            <T k="ai.title1" />
          </span>
          <span className="l-grad-text block">
            <T k="ai.title2" />
          </span>
        </h2>
        <p className="mt-4 max-w-lg text-base leading-relaxed text-muted sm:text-lg">
          <T k="ai.desc" />
        </p>
        <Link
          href="/planner"
          className="mt-7 inline-flex items-center gap-2 rounded-full bg-blue px-6 py-3.5 font-semibold text-white transition hover:bg-blue-hover"
        >
          <T k="ai.cta" /> <Icon name="arrowRight" className="h-4 w-4" />
        </Link>
        <p className="mt-4 flex items-center gap-2 text-sm text-muted">
          <Icon name="shield" className="h-4 w-4 text-gold" /> <T k="ai.honest" />
        </p>
      </div>

      <div className="reveal rounded-3xl bg-surface p-4 shadow-soft sm:p-6" aria-label="T-AI chat preview" role="group">
        <div className="flex justify-end">
          <p className="max-w-md rounded-2xl rounded-br-md bg-blue/25 px-4 py-3 text-sm ring-1 ring-blue/40">
            <span className="sr-only">
              <T k="ai.you" />:{" "}
            </span>
            “<T k="ai.example" />”
          </p>
        </div>
        <Suspense fallback={<div aria-hidden="true" className="mt-4 h-64 animate-pulse rounded-2xl bg-card" />}>
          <LiveAnswer />
        </Suspense>
        <Link
          href={`/planner?ask=${encodeURIComponent(EXAMPLE_EN)}`}
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-sky hover:underline"
        >
          <Icon name="ai" className="h-4 w-4" /> <T k="ai.ask" />
        </Link>
      </div>
    </section>
  );
}

async function LiveAnswer() {
  await connection(); // "tomorrow" depends on the request time
  const date = marketToday(new Date(), 1);
  let res: SearchResponse | null = null;
  try {
    res = await serverApi<SearchResponse>(
      `/api/v1/journeys/search?origin=tashkent&destination=samarkand&date=${date}&page_size=50`,
    );
  } catch {
    res = null;
  }
  const items = res?.items ?? [];
  if (!res || items.length === 0) {
    return (
      <p className="mt-4 rounded-2xl bg-card px-4 py-3 text-sm text-muted">
        <T k="ai.none" />
      </p>
    );
  }
  const by = (f: (a: Journey, b: Journey) => number) => [...items].sort(f)[0];
  const picks: [Key, Journey][] = [
    ["ai.recommended", items[0]],
    ["ai.cheapest", by((a, b) => Number(a.price) - Number(b.price) || a.total_minutes - b.total_minutes)],
    ["ai.fastest", by((a, b) => a.total_minutes - b.total_minutes || Number(a.price) - Number(b.price))],
  ];
  const demo = items.some((j) => j.is_demo);
  return (
    <div className="mt-4 flex items-start gap-3">
      <TAILogo size={32} still className="mt-1" />
      <div className="min-w-0 flex-1 space-y-3">
        <p className="rounded-2xl rounded-tl-md bg-card px-4 py-3 text-sm">
          <span className="sr-only">T-AI: </span>
          <T k="ai.reply" vars={{ n: res.total }} />
        </p>
        <ul className="grid gap-2.5 sm:grid-cols-3">
          {picks.map(([k, j]) => (
            <li key={k}>
              <Link
                href={`/journeys/${encodeURIComponent(j.id)}`}
                className={`lift block h-full rounded-2xl p-3.5 ring-1 transition ${
                  k === "ai.recommended" ? "bg-gold/10 ring-gold/50" : "bg-card ring-line hover:ring-blue/60"
                }`}
              >
                <span className={`text-[11px] font-semibold uppercase tracking-wide ${k === "ai.recommended" ? "text-gold" : "text-sky"}`}>
                  <T k={k} />
                </span>
                <span className="mt-2 flex items-center gap-1.5 text-sm font-semibold">
                  <ModeIcon mode={j.modes[0]} className="h-4 w-4 text-sky" /> <T k={MODE_KEY[j.modes[0]]} />
                </span>
                <span className="mt-1 block text-xs text-muted tabular-nums">
                  {localTime(j.legs[0].departure_local)} – {localTime(j.legs[j.legs.length - 1].arrival_local)} ·{" "}
                  {formatDuration(j.total_minutes)}
                </span>
                <span className="mt-1 block text-xs text-muted">
                  {j.transfers === 0 ? <T k="ai.direct" /> : <T k="ai.changes" vars={{ n: j.transfers }} />}
                </span>
                <span className="mt-2 block font-bold text-gold tabular-nums">
                  <T k="ai.from" /> {formatMoney(Number(j.price), j.currency)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
        <p className="flex items-center gap-1.5 text-xs text-muted">
          <span className={`h-2 w-2 rounded-full ${demo ? "bg-gold" : "bg-success"}`} aria-hidden="true" />
          {demo ? <T k="ai.demo" /> : <T k="ai.real" />}
        </p>
      </div>
    </div>
  );
}
