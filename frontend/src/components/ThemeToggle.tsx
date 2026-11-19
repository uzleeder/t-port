"use client";

import { useSyncExternalStore } from "react";
import { readPref, serverPref, setThemePref, subscribeTheme, type ThemePref } from "@/lib/theme";

const NEXT: Record<ThemePref, ThemePref> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<ThemePref, string> = { system: "System theme", light: "Light theme", dark: "Dark theme" };

const ICON: Record<ThemePref, string> = {
  light: "M12 4V2m0 20v-2m8-8h2M2 12h2m13.66-5.66 1.41-1.41M4.93 19.07l1.41-1.41m0-11.32L4.93 4.93m14.14 14.14-1.41-1.41M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z",
  dark: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z",
  system: "M4 5h16v11H4zM9 20h6m-3-4v4",
};

export function useThemePref(): ThemePref {
  return useSyncExternalStore(subscribeTheme, readPref, serverPref);
}

/** Header button: cycles System → Light → Dark. */
export function ThemeToggle() {
  const pref = useThemePref();
  return (
    <button
      type="button"
      onClick={() => setThemePref(NEXT[pref])}
      title={`${LABEL[pref]} (click to change)`}
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface text-ink shadow-soft hover:bg-surface-2"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5" aria-hidden="true">
        <path d={ICON[pref]} />
      </svg>
      <span className="sr-only">{LABEL[pref]}. Switch theme</span>
    </button>
  );
}

/** Segmented control for the profile page. */
export function ThemeChooser() {
  const pref = useThemePref();
  return (
    <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-2">
      {(["system", "dark", "light"] as const).map((p) => (
        <button
          key={p}
          type="button"
          role="radio"
          aria-checked={pref === p}
          onClick={() => setThemePref(p)}
          className={`flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
            pref === p ? "bg-blue text-white" : "text-muted ring-1 ring-line hover:text-ink hover:ring-blue"
          }`}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true">
            <path d={ICON[p]} />
          </svg>
          {p === "system" ? "System" : p === "dark" ? "Dark" : "Light"}
        </button>
      ))}
    </div>
  );
}
