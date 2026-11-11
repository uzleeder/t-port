"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { LocationCombobox } from "./LocationCombobox";
import { ModeIcon } from "./ModeIcon";
import { buildSearchQuery, marketToday, MODE_LABEL } from "@/lib/format";
import { ALL_MODES, type Location, type Mode } from "@/lib/types";

interface Props {
  initialOrigin?: Location | null;
  initialDestination?: Location | null;
  initialDate?: string;
  initialModes?: Mode[];
  compact?: boolean;
}

export function SearchForm({
  initialOrigin = null,
  initialDestination = null,
  initialDate,
  initialModes,
  compact = false,
}: Props) {
  const router = useRouter();
  const [origin, setOrigin] = useState<Location | null>(initialOrigin);
  const [destination, setDestination] = useState<Location | null>(initialDestination);
  // "Today" depends on the visitor's clock, so it is resolved after mount (not during prerender).
  const [date, setDate] = useState(initialDate ?? "");
  const [minDate, setMinDate] = useState("");
  const [modes, setModes] = useState<Mode[]>(
    initialModes && initialModes.length ? initialModes : ALL_MODES,
  );
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
    setModes((ms) => (ms.includes(mode) ? ms.filter((m) => m !== mode) : [...ms, mode]));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!origin || !destination) return setError("Choose an origin and a destination from the list.");
    if (origin.id === destination.id) return setError("Origin and destination must be different.");
    if (!date || (minDate && date < minDate)) return setError("Choose today or a future date.");
    if (modes.length === 0) return setError("Select at least one transport mode.");
    setError(null);
    const qs = buildSearchQuery({ origin: origin.id, destination: destination.id, date, modes });
    startTransition(() => router.push(`/search?${qs}`));
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label="Journey search"
      className={`rounded-2xl border border-line bg-surface/90 p-4 shadow-2xl shadow-black/30 backdrop-blur ${compact ? "" : "sm:p-6"}`}
    >
      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr_minmax(10rem,auto)] md:items-end">
        <LocationCombobox
          label="From"
          name="origin"
          value={origin}
          onChange={setOrigin}
          placeholder="City, e.g. Tashkent"
        />
        <button
          type="button"
          onClick={() => {
            setOrigin(destination);
            setDestination(origin);
          }}
          aria-label="Swap origin and destination"
          className="mx-auto flex h-11 w-11 items-center justify-center rounded-full border border-line text-muted transition hover:border-blue hover:text-ink"
        >
          <span aria-hidden="true">⇄</span>
        </button>
        <LocationCombobox
          label="To"
          name="destination"
          value={destination}
          onChange={setDestination}
          placeholder="City, e.g. Samarkand"
        />
        <div>
          <label htmlFor="travel-date" className="mb-1 block text-xs font-medium text-muted">
            Date
          </label>
          <input
            id="travel-date"
            type="date"
            name="date"
            min={minDate || undefined}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full rounded-xl border border-line bg-navy px-3 py-3 text-ink focus:border-blue"
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <fieldset className="flex flex-wrap gap-2">
          <legend className="sr-only">Transport modes</legend>
          {ALL_MODES.map((mode) => {
            const on = modes.includes(mode);
            return (
              <label
                key={mode}
                className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition ${
                  on ? "border-blue bg-blue/15 text-ink" : "border-line text-muted hover:border-muted"
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
                {MODE_LABEL[mode]}
              </label>
            );
          })}
        </fieldset>
        <button
          type="submit"
          disabled={pending}
          className="ml-auto w-full rounded-xl bg-blue px-6 py-3 font-semibold text-white transition hover:bg-blue-hover disabled:opacity-60 sm:w-auto"
        >
          {pending ? "Searching…" : "Search journeys"}
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
