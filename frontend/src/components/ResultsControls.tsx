"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { ModeIcon } from "./ModeIcon";
import { buildSearchQuery, MODE_LABEL, SORT_LABEL, type SearchParams } from "@/lib/format";
import { ALL_MODES, type Mode, type SortKey } from "@/lib/types";

/** Sort + mode filters on the results page. State lives in the URL. */
export function ResultsControls({ params }: { params: SearchParams }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
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
      {pending && (
        <span role="status" className="w-full text-sm text-muted">
          Updating results…
        </span>
      )}
    </div>
  );
}
