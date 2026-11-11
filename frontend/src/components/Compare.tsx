"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import {
  clearCompare,
  compareHref,
  getServerSnapshot,
  getSnapshot,
  MAX_COMPARE,
  subscribe,
  toggleCompare,
} from "@/lib/compare-store";

function useSelection(): string[] {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/** "Compare" checkbox on a journey card. Sits above the card's stretched details link. */
export function CompareToggle({ id, label }: { id: string; label: string }) {
  const ids = useSelection();
  const on = ids.includes(id);
  const full = !on && ids.length >= MAX_COMPARE;
  return (
    <label
      className={`relative z-10 inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
        on ? "border-blue bg-blue/15 text-ink" : "border-line text-muted hover:border-blue"
      } ${full ? "cursor-not-allowed opacity-60" : ""}`}
      title={full ? `You can compare up to ${MAX_COMPARE} journeys` : undefined}
    >
      <input
        type="checkbox"
        checked={on}
        disabled={full}
        onChange={() => toggleCompare(id)}
        className="h-3.5 w-3.5 accent-[var(--color-blue)]"
      />
      Compare<span className="sr-only">: {label}</span>
    </label>
  );
}

/** Sticky bar showing the current selection with a link to the comparison page. */
export function CompareTray() {
  const ids = useSelection();
  if (ids.length === 0) return null;
  const ready = ids.length >= 2;
  return (
    <div
      role="region"
      aria-label="Journeys selected for comparison"
      className="sticky bottom-4 z-20 mx-auto flex max-w-xl flex-wrap items-center gap-3 rounded-2xl border border-blue/60 bg-surface/95 px-4 py-3 shadow-lg backdrop-blur"
    >
      <p className="flex-1 text-sm" aria-live="polite">
        {ids.length} of {MAX_COMPARE} selected{ready ? "" : " · pick at least 2"}
      </p>
      <button type="button" onClick={clearCompare} className="text-sm text-muted hover:text-ink">
        Clear
      </button>
      {ready ? (
        <Link
          href={compareHref(ids)}
          className="rounded-xl bg-blue px-4 py-2 text-sm font-semibold text-white hover:bg-blue-hover"
        >
          Compare {ids.length}
        </Link>
      ) : (
        <span
          aria-disabled="true"
          className="cursor-not-allowed rounded-xl bg-blue/40 px-4 py-2 text-sm font-semibold text-white/70"
        >
          Compare
        </span>
      )}
    </div>
  );
}
