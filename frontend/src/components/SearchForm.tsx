"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState, useTransition } from "react";
import { Icon } from "./Icons";
import { LocationCombobox } from "./LocationCombobox";
import { ModeIcon } from "./ModeIcon";
import { buildSearchQuery, marketToday, MODE_LABEL } from "@/lib/format";
import { searchDefaults, usePreferences } from "@/lib/preferences";
import { ALL_MODES, type Location, type Mode } from "@/lib/types";

/** Visible text; the landing page passes translations (lib/i18n.ts). */
export interface SearchLabels {
  title: string;
  modes: string;
  from: string;
  to: string;
  date: string;
  placeholder: string;
  swap: string;
  submit: string;
  searching: string;
  errPick: string;
  errSame: string;
  errDate: string;
  errModes: string;
  /** Category names (landing variant). */
  all: string;
  multimodal: string;
  multimodalHint: string;
  mode: Record<Mode, string>;
}

export const SEARCH_LABELS_EN: SearchLabels = {
  title: "Where to?",
  modes: "Transport modes",
  from: "From",
  to: "To",
  date: "Date",
  placeholder: "City, district or region",
  swap: "Swap origin and destination",
  submit: "Search journeys",
  searching: "Searching…",
  errPick: "Choose an origin and a destination from the list.",
  errSame: "Origin and destination must be different.",
  errDate: "Choose today or a future date.",
  errModes: "Select at least one transport mode.",
  all: "All",
  multimodal: "Multimodal",
  multimodalHint: "Any mode, combined, up to 2 changes",
  mode: MODE_LABEL,
};

/** Landing categories: one choice, mapped onto the search API's modes and changes. */
type Category = "all" | Mode | "multimodal";

interface Props {
  initialOrigin?: Location | null;
  initialDestination?: Location | null;
  initialDate?: string;
  initialModes?: Mode[];
  compact?: boolean;
  /** Single-choice transport categories (All, each mode, Multimodal) instead of mode toggles. */
  categories?: boolean;
  labels?: SearchLabels;
}

export function SearchForm({
  initialOrigin = null,
  initialDestination = null,
  initialDate,
  initialModes,
  compact = false,
  categories = false,
  labels: L = SEARCH_LABELS_EN,
}: Props) {
  const router = useRouter();
  const uid = useId();
  const [origin, setOrigin] = useState<Location | null>(initialOrigin);
  const [destination, setDestination] = useState<Location | null>(initialDestination);
  // "Today" depends on the visitor's clock, so it is resolved after mount (not during prerender).
  const [date, setDate] = useState(initialDate ?? "");
  const [minDate, setMinDate] = useState("");
  const [prefs] = usePreferences();
  // null = not touched yet: follow the URL, then the user's saved default, then all modes.
  const [touchedModes, setModes] = useState<Mode[] | null>(null);
  const modes =
    touchedModes ??
    (initialModes && initialModes.length ? initialModes : prefs?.modes.length ? prefs.modes : ALL_MODES);
  const [category, setCategory] = useState<Category>("all");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    const now = new Date();
    /* eslint-disable react-hooks/set-state-in-effect -- one-time sync with the client clock */
    setMinDate(marketToday(now));
    setDate((d) => d || marketToday(now, 1));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  function toggle(mode: Mode) {
    setModes(modes.includes(mode) ? modes.filter((m) => m !== mode) : [...modes, mode]);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!origin || !destination) return setError(L.errPick);
    if (origin.id === destination.id) return setError(L.errSame);
    if (!date || (minDate && date < minDate)) return setError(L.errDate);
    const chosen = categories ? (category === "all" || category === "multimodal" ? ALL_MODES : [category]) : modes;
    if (chosen.length === 0) return setError(L.errModes);
    setError(null);
    // A new search starts from the signed-in user's saved defaults (sort, changes, budget).
    const qs = buildSearchQuery({
      ...searchDefaults(prefs),
      origin: origin.id,
      destination: destination.id,
      date,
      modes: chosen,
      ...(categories && category === "multimodal" ? { maxTransfers: 2 } : {}),
    });
    startTransition(() => router.push(`/search?${qs}`));
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label="Journey search"
      className={`@container rounded-3xl bg-surface p-4 shadow-soft ${compact ? "" : "sm:p-5"}`}
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">{L.title}</p>
        {categories ? (
          <fieldset className="relative -mx-1 flex min-w-0 max-w-full gap-1.5 overflow-x-auto px-1 pb-1 [scrollbar-width:none]">
            <legend className="sr-only">{L.modes}</legend>
            {(["all", ...ALL_MODES, "multimodal"] as Category[]).map((c) => {
              const on = category === c;
              return (
                <label
                  key={c}
                  title={c === "multimodal" ? L.multimodalHint : undefined}
                  className={`flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-sky ${
                    on ? "bg-blue font-semibold text-white" : "bg-card text-muted ring-1 ring-line hover:text-ink"
                  }`}
                >
                  <input
                    type="radio"
                    className="sr-only"
                    name="category"
                    value={c}
                    checked={on}
                    onChange={() => setCategory(c)}
                  />
                  <CategoryIcon category={c} />
                  {c === "all" ? L.all : c === "multimodal" ? L.multimodal : L.mode[c]}
                  {c === "multimodal" && <span className="sr-only">: {L.multimodalHint}</span>}
                </label>
              );
            })}
          </fieldset>
        ) : (
          <fieldset className="flex flex-wrap gap-2">
            <legend className="sr-only">{L.modes}</legend>
            {ALL_MODES.map((mode) => {
              const on = modes.includes(mode);
              return (
                <label
                  key={mode}
                  className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition ${
                    on ? "border-blue bg-blue text-white" : "border-line bg-card text-muted hover:border-blue"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={on}
                    onChange={() => toggle(mode)}
                    name="modes"
                    value={mode}
                  />
                  <ModeIcon mode={mode} className="h-4 w-4" />
                  {L.mode[mode]}
                </label>
              );
            })}
          </fieldset>
        )}
      </div>
      <div className="grid gap-3 @3xl:grid-cols-[1fr_auto_1fr_minmax(10rem,auto)_auto] @3xl:items-end">
        <LocationCombobox
          label={L.from}
          name="origin"
          value={origin}
          onChange={setOrigin}
          placeholder={L.placeholder}
        />
        <button
          type="button"
          onClick={() => {
            setOrigin(destination);
            setDestination(origin);
          }}
          aria-label={L.swap}
          className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-card text-ink shadow-soft transition hover:bg-surface-2"
        >
          <Icon name="swap" className="h-5 w-5" />
        </button>
        <LocationCombobox
          label={L.to}
          name="destination"
          value={destination}
          onChange={setDestination}
          placeholder={L.placeholder}
        />
        <div>
          <label htmlFor={`${uid}-date`} className="mb-1 block text-xs font-medium text-muted">
            {L.date}
          </label>
          <input
            id={`${uid}-date`}
            type="date"
            name="date"
            min={minDate || undefined}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full rounded-xl border border-line bg-card px-3 py-3 text-ink focus:border-blue"
          />
        </div>
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-full bg-blue px-6 py-3 font-semibold text-white transition hover:bg-blue-hover disabled:opacity-60 @3xl:w-auto"
        >
          {pending ? L.searching : L.submit}
        </button>
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error}
        </p>
      )}
    </form>
  );
}

function CategoryIcon({ category: c }: { category: Category }) {
  if (c === "all") return <Icon name="grid" className="h-4 w-4" />;
  if (c === "multimodal") return <Icon name="route" className="h-4 w-4" />;
  return <ModeIcon mode={c} className="h-4 w-4" />;
}
