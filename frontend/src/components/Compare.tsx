"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { Icon } from "./Icons";
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
        on ? "border-blue bg-blue text-white" : "border-line bg-card text-muted hover:border-blue"
      } ${full ? "cursor-not-allowed opacity-60" : ""}`}
      title={full ? `You can compare up to ${MAX_COMPARE} journeys` : undefined}
    >
      <input
        type="checkbox"
        checked={on}
        disabled={full}
        onChange={() => toggleCompare(id)}
        className="h-3.5 w-3.5 accent-[var(--color-amber)]"
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
      className="sticky bottom-24 z-20 mx-auto flex max-w-xl flex-wrap items-center gap-3 rounded-full bg-card/95 py-2 pl-5 pr-2 shadow-float backdrop-blur sm:bottom-4"
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
          className="rounded-full bg-blue px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-hover"
        >
          Compare {ids.length}
        </Link>
      ) : (
        <span
          aria-disabled="true"
          className="cursor-not-allowed rounded-full bg-blue/30 px-5 py-2.5 text-sm font-semibold text-white"
        >
          Compare
        </span>
      )}
    </div>
  );
}

/** "Compare (n/4)" button: opens the comparison once at least two journeys are selected. */
export function CompareCount({ label = "Compare", big = false }: { label?: string; big?: boolean }) {
  const ids = useSelection();
  const ready = ids.length >= 2;
  const cls = `flex items-center gap-2 rounded-full font-semibold transition ${big ? "px-6 py-3" : "px-4 py-2 text-sm"}`;
  const text = (
    <>
      <Icon name="route" className="h-4 w-4" /> {label} ({ids.length}/{MAX_COMPARE})
    </>
  );
  return ready ? (
    <Link href={compareHref(ids)} className={`${cls} bg-blue text-white`}>
      {text}
    </Link>
  ) : (
    <span aria-disabled="true" title="Tick Compare on at least two journeys" className={`${cls} text-muted ring-1 ring-blue/50`}>
      {text}
    </span>
  );
}
