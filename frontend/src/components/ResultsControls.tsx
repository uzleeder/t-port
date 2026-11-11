"use client";

import { useRouter } from "next/navigation";
import { useId, useTransition } from "react";
import { ModeIcon } from "./ModeIcon";
import { buildSearchQuery, MODE_LABEL, SORT_LABEL, type SearchParams } from "@/lib/format";
import { ALL_MODES, type Mode, type SortKey } from "@/lib/types";

const CHANGES: { value: 0 | 1 | 2; label: string }[] = [
  { value: 0, label: "Direct only" },
  { value: 1, label: "Up to 1 change" },
  { value: 2, label: "Up to 2 changes" },
];

/** Sort, mode and journey filters on the results page. State lives in the URL. */
export function ResultsControls({ params }: { params: SearchParams }) {
  const router = useRouter();
  const id = useId();
  const [pending, startTransition] = useTransition();
  const filtered = Boolean(params.arriveBefore || params.maxPrice);
  const active = params.modes.length ? params.modes : ALL_MODES;

  function go(next: Partial<SearchParams>) {
    const qs = buildSearchQuery({ ...params, page: 1, ...next });
    startTransition(() => router.push(`/search?${qs}`, { scroll: false }));
  }

  function toggle(mode: Mode) {
    const next = active.includes(mode) ? active.filter((m) => m !== mode) : [...active, mode];
    if (next.length === 0) return; // at least one mode stays selected
    go({ modes: next });
  }

  return (
    <div
      className="flex flex-wrap items-center gap-3"
      aria-busy={pending}
      data-pending={pending || undefined}
    >
      <fieldset className="flex flex-wrap gap-2">
        <legend className="sr-only">Filter by transport mode</legend>
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
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition disabled:cursor-not-allowed ${
                on ? "border-blue bg-blue/15" : "border-line text-muted hover:border-muted"
              }`}
            >
              <ModeIcon mode={mode} className="h-4 w-4" />
              {MODE_LABEL[mode]}
            </button>
          );
        })}
      </fieldset>
      <label className="ml-auto flex items-center gap-2 text-sm text-muted">
        Sort by
        <select
          value={params.sort}
          disabled={pending}
          onChange={(e) => go({ sort: e.target.value as SortKey })}
          className="rounded-lg border border-line bg-navy px-3 py-2 text-ink"
        >
          {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
            <option key={k} value={k}>
              {SORT_LABEL[k]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2 text-sm text-muted">
        Changes
        <select
          value={params.maxTransfers ?? 1}
          disabled={pending}
          onChange={(e) => go({ maxTransfers: Number(e.target.value) as 0 | 1 | 2 })}
          className="rounded-lg border border-line bg-navy px-3 py-2 text-ink"
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
        className="flex w-full flex-wrap items-end gap-3 sm:w-auto"
        aria-label="Arrival time and budget"
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          const arrive = String(form.get("arrive_before") ?? "");
          const price = String(form.get("max_price") ?? "").replace(/[\s,]/g, "");
          go({ arriveBefore: arrive || null, maxPrice: price || null });
        }}
      >
        <label htmlFor={`${id}-arrive`} className="flex flex-col gap-1 text-xs text-muted">
          Arrive by
          <input
            id={`${id}-arrive`}
            name="arrive_before"
            type="time"
            defaultValue={params.arriveBefore ?? ""}
            className="rounded-lg border border-line bg-navy px-3 py-2 text-sm text-ink"
          />
        </label>
        <label htmlFor={`${id}-price`} className="flex flex-col gap-1 text-xs text-muted">
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
            className="w-36 rounded-lg border border-line bg-navy px-3 py-2 text-sm text-ink"
          />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg border border-blue px-3 py-2 text-sm hover:bg-blue/15 disabled:opacity-60"
        >
          Apply
        </button>
        {filtered && (
          <button
            type="button"
            disabled={pending}
            onClick={() => go({ arriveBefore: null, maxPrice: null })}
            className="px-1 py-2 text-sm text-muted hover:text-ink"
          >
            Clear
          </button>
        )}
      </form>
      {pending && (
        <span role="status" className="w-full text-sm text-muted">
          Updating results…
        </span>
      )}
    </div>
  );
}
