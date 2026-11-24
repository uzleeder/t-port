"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { Icon, type IconName } from "./Icons";
import { LocationCombobox } from "./LocationCombobox";
import { ModeIcon } from "./ModeIcon";
import { TAILogo } from "./TAILogo";
import { ApiError, clientApi } from "@/lib/api";
import { understoodAs, type InterpretResponse, type PlaceAnswer } from "@/lib/assistant";
import { PLACE_IMAGE } from "@/lib/explore";
import {
  buildSearchQuery,
  formatDuration,
  formatMoney,
  formatPriceRange,
  localTime,
  marketToday,
  MODE_LABEL,
} from "@/lib/format";
import { ALL_MODES, type Journey, type Location, type Mode, type SearchResponse, type SortKey } from "@/lib/types";

type Message = { role: "user" | "assistant"; text: string; places?: PlaceAnswer[]; lang?: "en" | "uz" };
type Tab = "recommended" | "cheapest" | "fastest" | "fewest" | "all";

const PROMPTS = [
  "Find the cheapest route from Tashkent to Samarkand tomorrow",
  "What can I see in Khiva?",
  "Fastest way from Tashkent to Bukhara on Friday",
  "Buxoro haqida aytib bering",
];

const PRIORITIES: { value: SortKey; label: string }[] = [
  { value: "recommended", label: "Balanced (recommended)" },
  { value: "price", label: "Cheapest" },
  { value: "duration", label: "Fastest" },
  { value: "transfers", label: "Fewest changes" },
];

interface Picks {
  recommended: Journey;
  cheapest: Journey;
  fastest: Journey;
  fewest: Journey;
}

function pick(items: Journey[]): Picks | null {
  if (items.length === 0) return null;
  const by = (f: (a: Journey, b: Journey) => number) => [...items].sort(f)[0];
  return {
    recommended: items[0], // the search engine's own ranking for the chosen priority
    cheapest: by((a, b) => Number(a.price) - Number(b.price) || a.total_minutes - b.total_minutes),
    fastest: by((a, b) => a.total_minutes - b.total_minutes || Number(a.price) - Number(b.price)),
    fewest: by((a, b) => a.transfers - b.transfers || a.total_minutes - b.total_minutes),
  };
}

export function Planner() {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [origin, setOrigin] = useState<Location | null>(null);
  const [destination, setDestination] = useState<Location | null>(null);
  const [date, setDate] = useState("");
  const [mode, setMode] = useState<Mode | "all">("all");
  const [priority, setPriority] = useState<SortKey>("recommended");
  const [maxTransfers, setMaxTransfers] = useState<0 | 1 | 2>(1);
  const [maxPrice, setMaxPrice] = useState("");
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [query, setQuery] = useState<string | null>(null);
  const [chips, setChips] = useState<string[]>([]);
  const [tab, setTab] = useState<Tab>("recommended");
  const [tripPlaces, setTripPlaces] = useState<Message | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- "tomorrow" uses the visitor's clock, after mount
    setDate((d) => d || marketToday(new Date(), 1));
  }, []);

  // "Ask T-AI" links (e.g. from Explore) open the chat with a question: /planner?ask=...
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("ask")?.trim();
    if (!q) return;
    const t = setTimeout(() => {
      window.history.replaceState(null, "", window.location.pathname); // a reload won't ask again
      void ask(q.slice(0, 500));
    }, 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once, on arrival
  }, []);

  const picks = result ? pick(result.items) : null;

  async function runSearch(qs: string, userText: string, explanation?: string | null) {
    const res = await clientApi<SearchResponse>(`/api/v1/journeys/search?${qs}&page_size=50`);
    setResult(res);
    setQuery(qs);
    setTab("recommended");
    setMessages((m) => [
      ...m,
      {
        role: "assistant",
        text:
          explanation ??
          (res.total
            ? `I found ${res.total} option(s) from ${res.query.origin.name} to ${res.query.destination.name} and compared them for you.`
            : `I couldn't find a matching journey for "${userText}" in the data T-Port currently has.`),
      },
    ]);
  }

  async function ask(value: string) {
    const q = value.trim();
    if (!q || pending) return;
    setPending(true);
    setError(null);
    setText("");
    setTripPlaces(null);
    setMessages((m) => [...m, { role: "user", text: q }]);
    try {
      const answer = await clientApi<InterpretResponse>("/api/v1/ai/interpret", {
        method: "POST",
        body: JSON.stringify({ text: q }),
      });
      setChips(understoodAs(answer.intent));
      const intro = answer.answer;
      const isTrip = !answer.needs_clarification && !!answer.search_query;
      if (answer.places.length > 0 && intro) {
        const placesMsg: Message = { role: "assistant", text: intro, places: answer.places, lang: answer.language };
        if (isTrip) setTripPlaces(placesMsg);
        else setMessages((m) => [...m, placesMsg]);
      }
      if (answer.needs_clarification || !answer.search_query) {
        setMessages((m) => [
          ...m,
          { role: "assistant", text: answer.clarification ?? answer.explanation ?? "Could you tell me more?" },
        ]);
        setResult(null);
      } else {
        await runSearch(answer.search_query, q, answer.explanation);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "T-AI is unavailable right now.");
    } finally {
      setPending(false);
    }
  }

  async function planFromForm(e: React.FormEvent) {
    e.preventDefault();
    if (!origin || !destination) return setError("Choose where you start and where you're going.");
    if (origin.id === destination.id) return setError("Origin and destination must be different.");
    const summary = `I want to go from ${origin.name} to ${destination.name} on ${date}${
      mode === "all" ? "" : ` by ${MODE_LABEL[mode].toLowerCase()}`
    }. Priority: ${PRIORITIES.find((p) => p.value === priority)?.label.toLowerCase()}, up to ${maxTransfers} change${
      maxTransfers === 1 ? "" : "s"
    }${maxPrice ? `, under ${Number(maxPrice).toLocaleString("en-US")} UZS` : ""}.`;
    setPending(true);
    setError(null);
    setChips([]);
    setTripPlaces(null);
    setMessages((m) => [...m, { role: "user", text: summary }]);
    try {
      const qs = buildSearchQuery({
        origin: origin.id,
        destination: destination.id,
        date,
        modes: mode === "all" ? [] : [mode],
        sort: priority,
        maxTransfers,
        maxPrice: maxPrice || null,
      });
      await runSearch(qs, summary);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed. Please try again.");
    } finally {
      setPending(false);
    }
  }

  const tabs: [Tab, string, IconName][] = [
    ["recommended", "Recommended", "sparkle"],
    ["cheapest", "Cheapest", "coin"],
    ["fastest", "Fastest", "clock"],
    ["fewest", "Fewest changes", "route"],
    ["all", `All options (${result?.total ?? 0})`, "compass"],
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1fr)_21rem]">
      <section
        aria-label="Conversation with T-AI"
        className="flex min-h-[36rem] flex-col rounded-3xl bg-surface p-5 shadow-soft"
      >
        <div className="flex-1 space-y-4" aria-live="polite">
          <Bubble role="assistant">
            Hi! I&apos;m <strong>T-AI</strong>, T-Port&apos;s travel assistant. Tell me your trip and I&apos;ll find and
            compare real options, or ask me about any of Uzbekistan&apos;s 14 regions and what to see there. I never
            invent prices, times or facts: everything comes from listed sources.
          </Bubble>
          {messages.length === 0 && (
            <div>
              <p className="mb-2 flex items-center gap-1.5 text-sm text-gold">
                <Icon name="ai" className="h-4 w-4" /> Try asking
              </p>
              <ul className="flex flex-wrap gap-2">
                {PROMPTS.map((p) => (
                  <li key={p}>
                    <button
                      type="button"
                      onClick={() => void ask(p)}
                      className="rounded-full px-3 py-1.5 text-sm text-ink ring-1 ring-line hover:ring-blue"
                    >
                      “{p}”
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {messages.map((m, i) => (
            <Bubble key={i} role={m.role}>
              {m.text}
              {m.places && m.places.length > 0 && (
                <ul className="mt-3 grid gap-3 sm:grid-cols-2">
                  {m.places.map((p) => (
                    <li key={p.key}>
                      <PlaceAnswerCard place={p} lang={m.lang ?? "en"} />
                    </li>
                  ))}
                </ul>
              )}
            </Bubble>
          ))}
          {chips.length > 0 && (
            <ul aria-label="Understood as" className="flex flex-wrap gap-1.5 pl-12">
              {chips.map((c) => (
                <li key={c} className="flex items-center gap-1 rounded-full bg-card px-2.5 py-1 text-xs">
                  <Icon name="check" className="h-3.5 w-3.5 text-success" /> {c}
                </li>
              ))}
            </ul>
          )}
          {pending && (
            <div role="status" className="flex items-center gap-3 pl-12 text-sm text-muted">
              <TAILogo size={32} /> T-AI is thinking…
            </div>
          )}
          {error && (
            <p role="alert" className="pl-12 text-sm text-danger">
              {error}
            </p>
          )}

          {picks && result && (
            <>
              <div role="tablist" aria-label="Recommendation views" className="flex gap-2 overflow-x-auto pb-1">
                {tabs.map(([key, label, icon]) => (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    aria-selected={tab === key}
                    onClick={() => setTab(key)}
                    className={`flex shrink-0 items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-medium transition ${
                      tab === key ? "bg-blue text-white" : "text-muted ring-1 ring-line hover:text-ink"
                    }`}
                  >
                    <Icon name={icon} className="h-4 w-4" /> {label}
                  </button>
                ))}
              </div>
              {tab === "all" ? (
                <ul className="space-y-2">
                  {result.items.map((j) => (
                    <li key={j.id}>
                      <Link
                        href={`/journeys/${encodeURIComponent(j.id)}`}
                        className="flex flex-wrap items-center gap-3 rounded-2xl bg-card px-4 py-3 ring-1 ring-line hover:ring-blue"
                      >
                        <span className="flex gap-1 text-sky">
                          {j.modes.map((m) => (
                            <ModeIcon key={m} mode={m} className="h-5 w-5" />
                          ))}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm font-medium">
                          {j.legs.map((l) => l.operator).join(" + ")}
                        </span>
                        <span className="text-sm text-muted tabular-nums">
                          {localTime(j.legs[0].departure_local)} · {formatDuration(j.total_minutes)}
                        </span>
                        <span className="font-semibold text-gold tabular-nums">
                          {formatPriceRange(j.price, j.price_max, j.currency)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
                  <PickCard kind="recommended" journey={picks.recommended} active={tab === "recommended"} />
                  <PickCard kind="cheapest" journey={picks.cheapest} active={tab === "cheapest"} />
                  <PickCard kind="fastest" journey={picks.fastest} active={tab === "fastest"} />
                  <PickCard kind="fewest" journey={picks.fewest} active={tab === "fewest"} />
                </div>
              )}
              <Insight picks={picks} result={result} />
              {query && (
                <Link
                  href={`/search?${query}`}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-sky hover:underline"
                >
                  See all {result.total} results with filters <Icon name="arrowRight" className="h-4 w-4" />
                </Link>
              )}
            </>
          )}
          {tripPlaces && (
            <Bubble role="assistant">
              {tripPlaces.text}
              <ul className="mt-3 grid gap-3 sm:grid-cols-2">
                {tripPlaces.places?.map((p) => (
                  <li key={p.key}>
                    <PlaceAnswerCard place={p} lang={tripPlaces.lang ?? "en"} />
                  </li>
                ))}
              </ul>
            </Bubble>
          )}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void ask(text);
          }}
          className="mt-5 flex items-center gap-2 rounded-full bg-card p-1.5 pl-4 ring-1 ring-line focus-within:ring-blue"
        >
          <Icon name="ai" className="h-5 w-5 shrink-0" />
          <label htmlFor={`${id}-ask`} className="sr-only">
            Ask T-AI
          </label>
          <input
            ref={inputRef}
            id={`${id}-ask`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={500}
            placeholder="Ask T-AI about a trip or a place…"
            className="min-w-0 flex-1 bg-transparent py-2 text-sm text-ink outline-none placeholder:text-muted/80"
          />
          <button
            type="submit"
            disabled={pending || !text.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue text-white disabled:opacity-40"
          >
            <Icon name="send" className="h-4 w-4" />
            <span className="sr-only">Send</span>
          </button>
        </form>
      </section>

      <form
        onSubmit={planFromForm}
        aria-label="Plan your trip"
        className="grid h-fit gap-4 rounded-3xl bg-surface p-5 shadow-soft md:grid-cols-2 md:gap-x-6 xl:sticky xl:top-24 xl:grid-cols-1"
      >
        <div className="flex items-start gap-3 md:col-span-2 xl:col-span-1">
          <Icon name="compass" className="mt-0.5 h-6 w-6 text-sky" />
          <div>
            <p className="text-lg font-semibold">Plan your trip</p>
            <p className="text-sm text-muted">Tell T-AI your travel preferences.</p>
          </div>
        </div>
        <div className="h-fit space-y-3 rounded-2xl bg-card p-3">
          <LocationCombobox
            label="From"
            name="origin"
            value={origin}
            onChange={setOrigin}
            placeholder="City or region"
          />
          <LocationCombobox
            label="To"
            name="destination"
            value={destination}
            onChange={setDestination}
            placeholder="City or region"
          />
          <label htmlFor={`${id}-date`} className="block text-xs font-medium text-muted">
            Travel date
            <input
              id={`${id}-date`}
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 w-full rounded-xl border border-line bg-card px-3 py-2.5 text-sm text-ink"
            />
          </label>
        </div>
        <div className="space-y-3">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Icon name="sparkle" className="h-4 w-4 text-gold" /> Travel preferences
          </p>
          <Select
            id={`${id}-mode`}
            label="Preferred transport"
            value={mode}
            onChange={(v) => setMode(v as Mode | "all")}
          >
            <option value="all">Any (all modes)</option>
            {ALL_MODES.map((m) => (
              <option key={m} value={m}>
                {MODE_LABEL[m]}
              </option>
            ))}
          </Select>
          <Select id={`${id}-priority`} label="Priority" value={priority} onChange={(v) => setPriority(v as SortKey)}>
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </Select>
          <Select
            id={`${id}-changes`}
            label="Max transfers"
            value={String(maxTransfers)}
            onChange={(v) => setMaxTransfers(Number(v) as 0 | 1 | 2)}
          >
            <option value="0">Direct only</option>
            <option value="1">Up to 1 transfer</option>
            <option value="2">Up to 2 transfers</option>
          </Select>
          <label htmlFor={`${id}-budget`} className="block text-xs font-medium text-muted">
            Budget (UZS, optional)
            <input
              id={`${id}-budget`}
              type="number"
              inputMode="numeric"
              min={1000}
              step={1000}
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
              placeholder="Any"
              className="mt-1 w-full rounded-xl border border-line bg-card px-3 py-2.5 text-sm text-ink"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={pending}
          className="btn-gold flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-3.5 font-bold disabled:opacity-60 md:col-span-2 xl:col-span-1"
        >
          <Icon name="ai" className="h-5 w-5" /> Plan with T-AI
        </button>
      </form>
    </div>
  );
}

function Select({
  id,
  label,
  value,
  onChange,
  children,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label htmlFor={id} className="flex items-center justify-between gap-3 text-sm text-muted">
      {label}
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-44 rounded-xl border border-line bg-card px-3 py-2 text-sm text-ink"
      >
        {children}
      </select>
    </label>
  );
}

function Bubble({ role, children }: { role: "user" | "assistant"; children: React.ReactNode }) {
  const mine = role === "user";
  return (
    <div className={`flex items-start gap-3 ${mine ? "flex-row-reverse" : ""}`}>
      {mine ? (
        <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-2">
          <Icon name="user" className="h-4 w-4 text-ink" />
        </span>
      ) : (
        <TAILogo size={36} still />
      )}
      <div
        className={`max-w-[46rem] rounded-2xl px-4 py-3 text-sm leading-relaxed ${mine ? "bg-blue/20 ring-1 ring-blue/40" : "bg-card"}`}
      >
        <span className="sr-only">{mine ? "You: " : "T-AI: "}</span>
        {children}
      </div>
    </div>
  );
}

const KIND: Record<"recommended" | "cheapest" | "fastest" | "fewest", { title: string; icon: IconName; tone: string }> =
  {
    recommended: { title: "Recommended", icon: "sparkle", tone: "btn-gold" },
    cheapest: { title: "Cheapest", icon: "coin", tone: "bg-success text-white" },
    fastest: { title: "Fastest", icon: "clock", tone: "bg-blue text-white" },
    fewest: { title: "Fewest changes", icon: "route", tone: "bg-violet text-white" },
  };

function PickCard({ kind, journey, active }: { kind: keyof typeof KIND; journey: Journey; active: boolean }) {
  const k = KIND[kind];
  const first = journey.legs[0];
  const last = journey.legs[journey.legs.length - 1];
  return (
    <article
      className={`flex flex-col overflow-hidden rounded-2xl bg-card transition ${
        active ? (kind === "recommended" ? "ring-2 ring-gold" : "ring-2 ring-blue") : "ring-1 ring-line"
      }`}
    >
      <div className="relative flex h-20 items-end bg-gradient-to-br from-[#14306e] via-[#1d3f8f] to-[#3a2a7a] p-3">
        <ModeIcon mode={journey.modes[0]} className="absolute right-3 top-3 h-10 w-10 text-white/25" />
        <span className={`flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${k.tone}`}>
          <Icon name={k.icon} className="h-3.5 w-3.5" /> {k.title}
        </span>
      </div>
      <div className="flex flex-1 flex-col p-4">
        <p className="flex items-center gap-2 font-semibold">
          <ModeIcon mode={journey.modes[0]} className="h-4 w-4 text-sky" />
          {journey.modes.map((m) => MODE_LABEL[m]).join(" + ")}
        </p>
        <p className="text-xs text-muted">
          {first.origin.name} → {last.destination.name}
        </p>
        <p className="mt-3 flex items-baseline justify-between text-sm">
          <span className="font-semibold tabular-nums">
            {first.departure_local
              ? `${localTime(first.departure_local)} – ${localTime(last.arrival_local)}`
              : "Flexible"}
          </span>
          <span className="text-muted">{formatDuration(journey.total_minutes)}</span>
        </p>
        <p className="mt-2 flex flex-wrap gap-1.5 text-xs">
          <span className="rounded-full bg-surface-2 px-2 py-0.5">
            {journey.transfers === 0 ? "Direct" : `${journey.transfers} change(s)`}
          </span>
          {journey.is_demo && <span className="rounded-full bg-gold/15 px-2 py-0.5 text-gold">Demo data</span>}
        </p>
        <div className="mt-auto flex items-center justify-between gap-2 pt-4">
          <span className="text-sm text-muted">
            from{" "}
            <span className="text-lg font-bold text-gold tabular-nums">
              {formatPriceRange(journey.price, journey.price_max, journey.currency)}
            </span>
          </span>
          <Link
            href={`/journeys/${encodeURIComponent(journey.id)}`}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full btn-gold"
          >
            <Icon name="arrowRight" className="h-4 w-4" />
            <span className="sr-only">Select route</span>
          </Link>
        </div>
      </div>
    </article>
  );
}

/** Facts about the recommended pick, computed from the results (no invented claims). */
function Insight({ picks, result }: { picks: Picks; result: SearchResponse }) {
  const r = picks.recommended;
  const facts: string[] = [];
  if (r.id === picks.fastest.id) facts.push(`${formatDuration(r.total_minutes)} — the fastest option`);
  else facts.push(`${formatDuration(r.total_minutes)} (fastest is ${formatDuration(picks.fastest.total_minutes)})`);
  facts.push(r.transfers === 0 ? "Direct (no transfers)" : `${r.transfers} transfer(s), connections checked`);
  if (r.id === picks.cheapest.id) facts.push("Cheapest listed fare");
  else facts.push(`${formatMoney(Number(r.price) - Number(picks.cheapest.price), r.currency)} more than the cheapest`);
  return (
    <section
      aria-label="T-AI insight"
      className="flex flex-wrap items-center gap-4 rounded-2xl bg-gradient-to-r from-violet/20 via-blue/10 to-transparent p-4 ring-1 ring-violet/40"
    >
      <p className="flex items-center gap-2 font-semibold">
        <Icon name="ai" className="h-6 w-6" /> T-AI Insight
      </p>
      <div className="min-w-0 flex-1 text-sm sm:border-l sm:border-line sm:pl-4">
        <p>
          I recommend the <strong>{r.modes.map((m) => MODE_LABEL[m]).join(" + ")}</strong> by{" "}
          {r.legs.map((l) => l.operator).join(" + ")} — the top result for your priority among {result.total} option(s).
        </p>
        <ul className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {facts.map((f) => (
            <li key={f} className="flex items-center gap-1">
              <Icon name="check" className="h-3.5 w-3.5 text-success" /> {f}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

const PLACE_LABELS = {
  en: {
    history: "History & significance",
    see: "What to see",
    tip: "Plan your visit",
    more: "Read more",
    sources: "Sources",
    journeys: "Journeys to",
    art: "Illustration",
  },
  uz: {
    history: "Tarix va ahamiyat",
    see: "Nimalarni ko‘rish mumkin",
    tip: "Tashrif uchun maslahat",
    more: "Batafsil",
    sources: "Manbalar",
    journeys: "Yo‘nalishlar:",
    art: "Illyustratsiya",
  },
} as const;

/** One place from T-AI's knowledge: quoted text, its sources, and where to go next. */
function PlaceAnswerCard({ place: p, lang }: { place: PlaceAnswer; lang: "en" | "uz" }) {
  const t = PLACE_LABELS[lang];
  const origin = p.city_id === "tashkent" ? "samarkand" : "tashkent";
  return (
    <article lang={lang} aria-label={p.name} className="overflow-hidden rounded-2xl bg-surface ring-1 ring-line">
      <div className="relative">
        <Image
          src={p.image}
          alt=""
          width={PLACE_IMAGE.width}
          height={PLACE_IMAGE.height}
          sizes="(min-width: 1024px) 22rem, 90vw"
          className="h-auto w-full"
        />
        <span className="absolute left-2 top-2 rounded-full bg-black/55 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur">
          {t.art}
        </span>
      </div>
      <div className="space-y-2 p-3.5">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-sky">{p.category}</p>
          <h3 className="font-semibold leading-tight">{p.name}</h3>
          <p className="text-xs text-muted">{p.area}</p>
        </div>
        {(
          [
            [t.history, p.history],
            [t.see, p.see],
            [t.tip, p.tip],
          ] as const
        ).map(([label, text]) => (
          <p key={label} className="text-sm">
            <span className="font-medium">{label}. </span>
            <span className="text-muted">{text}</span>
          </p>
        ))}
        <p className="text-xs text-muted">
          {t.sources}:{" "}
          {p.sources.map((s, i) => (
            <span key={s.url}>
              {i > 0 && ", "}
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-sky underline">
                {s.label}
              </a>
            </span>
          ))}
        </p>
        <div className="flex flex-wrap gap-2 pt-1">
          <Link
            href={`/search?origin=${origin}&destination=${p.city_id}`}
            className="inline-flex items-center gap-1 rounded-full bg-blue px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-hover"
          >
            {t.journeys} {p.city_name} <Icon name="arrowRight" className="h-3.5 w-3.5" />
          </Link>
          <Link
            href={p.explore_url}
            className="inline-flex items-center rounded-full px-3 py-1.5 text-xs font-medium ring-1 ring-line hover:text-sky"
          >
            {t.more}
          </Link>
        </div>
      </div>
    </article>
  );
}
