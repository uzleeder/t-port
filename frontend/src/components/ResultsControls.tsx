"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useTransition } from "react";
import { CompareCount } from "./Compare";
import { Icon } from "./Icons";
import { ModeIcon } from "./ModeIcon";
import { buildSearchQuery, MODE_LABEL, SORT_LABEL, type SearchParams } from "@/lib/format";
import { ALL_MODES, type Mode, type SortKey } from "@/lib/types";

const CHANGES: { value: 0 | 1 | 2; label: string }[] = [
  { value: 0, label: "Direct only" },
  { value: 1, label: "Up to 1 change" },
  { value: 2, label: "Up to 2 changes" },
];

const WINDOWS: { key: string; label: string; after: string | null; before: string | null }[] = [
  { key: "any", label: "Any time", after: null, before: null },
  { key: "early", label: "Early morning (00:00–06:00)", after: "00:00", before: "06:00" },
  { key: "morning", label: "Morning (06:00–12:00)", after: "06:00", before: "12:00" },
  { key: "afternoon", label: "Afternoon (12:00–18:00)", after: "12:00", before: "18:00" },
  { key: "evening", label: "Evening (18:00–24:00)", after: "18:00", before: "23:59" },
];

function useGo(params: SearchParams) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const go = (next: Partial<SearchParams>) => {
    const qs = buildSearchQuery({ ...params, page: 1, ...next });
    startTransition(() => router.push(`/search?${qs}`, { scroll: false }));
  };
  return { go, pending };
}

/** Left filter panel (transport type, departure time, changes, arrival time, budget). State is the URL. */
export function ResultsControls({ params, counts }: { params: SearchParams; counts: Record<string, number> }) {
  const id = useId();
  const { go, pending } = useGo(params);
  const active = params.modes.length ? params.modes : ALL_MODES;
  const slot = WINDOWS.find((w) => w.after === (params.departAfter ?? null) && w.before === (params.departBefore ?? null))?.key ?? "custom";
  const anyFilter = Boolean(
    params.modes.length || params.arriveBefore || params.maxPrice || params.departAfter || params.departBefore || params.maxTransfers !== 1,
  );

  function toggle(mode: Mode) {
    const next = active.includes(mode) ? active.filter((m) => m !== mode) : [...active, mode];
    if (next.length === 0) return; // at least one mode stays selected
    go({ modes: next });
  }

  return (
    <aside
      aria-label="Filters"
      aria-busy={pending}
      data-pending={pending || undefined}
      className="space-y-5 rounded-3xl bg-surface p-5 shadow-soft"
    >
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-2 font-semibold">
          <Icon name="compass" className="h-5 w-5 text-sky" /> Filters
        </p>
        {anyFilter && (
          <button
            type="button"
            disabled={pending}
            onClick={() =>
              go({ modes: [], arriveBefore: null, maxPrice: null, departAfter: null, departBefore: null, maxTransfers: 1 })
            }
            className="text-sm text-sky underline-offset-2 hover:underline"
          >
            Reset all
          </button>
        )}
      </div>

      <fieldset>
        <legend className="mb-2 text-sm font-medium text-ink">Transport type</legend>
        <div className="flex flex-wrap gap-2 xl:flex-col">
          {ALL_MODES.map((mode) => {
            const on = active.includes(mode);
            return (
              <button
                key={mode}
                type="button"
                aria-pressed={on}
                onClick={() => toggle(mode)}
                disabled={pending || (on && active.length === 1)}
                title={on && active.length === 1 ? "At least one mode must stay selected" : undefined}
                className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition disabled:cursor-not-allowed ${
                  on ? "border-blue bg-blue/20 text-ink" : "border-line text-muted hover:border-blue"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`flex h-4 w-4 items-center justify-center rounded ${on ? "bg-blue text-white" : "ring-1 ring-line"}`}
                >
                  {on && <Icon name="check" className="h-3 w-3" strokeWidth={3} />}
                </span>
                <ModeIcon mode={mode} className="h-4 w-4" />
                {MODE_LABEL[mode]}
                {counts[mode] !== undefined && (
                  <span aria-hidden="true" className="text-muted">
                    ({counts[mode]})
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-2 text-sm font-medium text-ink">Departure time</legend>
        <div className="space-y-1.5">
          {WINDOWS.map((w) => (
            <label key={w.key} className="flex cursor-pointer items-center gap-2 text-sm text-muted hover:text-ink">
              <input
                type="radio"
                name={`${id}-window`}
                checked={slot === w.key}
                disabled={pending}
                onChange={() => go({ departAfter: w.after, departBefore: w.before })}
                className="h-4 w-4 accent-[var(--color-blue)]"
              />
              {w.label}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="flex flex-col gap-1 text-sm font-medium text-ink">
        Changes
        <select
          value={params.maxTransfers ?? 1}
          disabled={pending}
          onChange={(e) => go({ maxTransfers: Number(e.target.value) as 0 | 1 | 2 })}
          className="rounded-xl border border-line bg-card px-3 py-2 font-normal text-ink"
        >
          {CHANGES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </label>

      <form
        key={`${params.arriveBefore}-${params.maxPrice}`}
        className="space-y-3"
        aria-label="Arrival time and budget"
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          const arrive = String(form.get("arrive_before") ?? "");
          const price = String(form.get("max_price") ?? "").replace(/[\s,]/g, "");
          go({ arriveBefore: arrive || null, maxPrice: price || null });
        }}
      >
        <label htmlFor={`${id}-arrive`} className="flex flex-col gap-1 text-sm font-medium text-ink">
          Arrive by
          <input
            id={`${id}-arrive`}
            name="arrive_before"
            type="time"
            defaultValue={params.arriveBefore ?? ""}
            className="rounded-xl border border-line bg-card px-3 py-2 font-normal text-ink"
          />
        </label>
        <label htmlFor={`${id}-price`} className="flex flex-col gap-1 text-sm font-medium text-ink">
          Max price (UZS)
          <input
            id={`${id}-price`}
            name="max_price"
            type="number"
            inputMode="numeric"
            min={1000}
            step={1000}
            defaultValue={params.maxPrice ?? ""}
            placeholder="Any"
            className="rounded-xl border border-line bg-card px-3 py-2 font-normal text-ink"
          />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white hover:bg-blue-hover disabled:opacity-60"
        >
          Apply
        </button>
      </form>
      {pending && (
        <p role="status" className="text-sm text-muted">
          Updating results…
        </p>
      )}
    </aside>
  );
}

/** "All / Train / Flight / …" tabs with counts, plus the sort control. */
export function ResultsTabs({
  params,
  counts,
  total,
}: {
  params: SearchParams;
  counts: Record<string, number>;
  total: number;
}) {
  const { go, pending } = useGo(params);
  const single = params.modes.length === 1 ? params.modes[0] : null;
  const tab = (modes: Mode[]) => `/search?${buildSearchQuery({ ...params, page: 1, modes })}`;
  const base = "flex shrink-0 items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-medium transition";
  return (
    <div className="space-y-3">
      <nav aria-label="Transport mode tabs" className="flex gap-1 overflow-x-auto rounded-3xl bg-surface p-1.5 shadow-soft">
        <Link href={tab([])} scroll={false} className={`${base} ${single ? "text-muted hover:text-ink" : "bg-blue text-white"}`}>
          All ({total})
        </Link>
        {ALL_MODES.filter((m) => counts[m] !== undefined || single === m).map((m) => (
          <Link
            key={m}
            href={tab([m])}
            scroll={false}
            className={`${base} ${single === m ? "bg-blue text-white" : "text-muted hover:text-ink"}`}
          >
            <ModeIcon mode={m} className="h-4 w-4" />
            {MODE_LABEL[m]} ({counts[m] ?? 0})
          </Link>
        ))}
      </nav>
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <p className="text-sm text-muted">{total} results found</p>
        <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-muted">
          Sort by
          <select
            value={params.sort}
            disabled={pending}
            onChange={(e) => go({ sort: e.target.value as SortKey })}
            className="rounded-xl border border-line bg-card px-3 py-2 text-ink"
          >
            {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
              <option key={k} value={k}>
                {SORT_LABEL[k]}
              </option>
            ))}
          </select>
        </label>
        <CompareCount />
        </div>
      </div>
    </div>
  );
}
