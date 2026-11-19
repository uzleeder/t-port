"use client";

import { useSyncExternalStore } from "react";
import { Icon } from "./Icons";
import { I18N, isLang, LANG_KEY, LANG_LABEL, LANG_SHORT, LANGS, type Key, type Lang } from "@/lib/i18n";

/*
 * The visitor's interface language lives on <html lang> (set before first paint by the script in
 * app/layout.tsx from localStorage or the browser's languages). This store reads and changes it.
 */
const listeners = new Set<() => void>();

function current(): Lang {
  const l = document.documentElement.lang;
  return isLang(l) ? l : "en";
}

export function setLang(lang: Lang) {
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch {
    // Storage blocked: the choice still applies to this page view.
  }
  document.documentElement.lang = lang;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** Current language; "en" on the server and during hydration. */
export function useLang(): Lang {
  return useSyncExternalStore(subscribe, current, () => "en");
}

/** A translated string for attributes (placeholders, aria-labels) in client components. */
export function useT(): (k: Key) => string {
  const lang = useLang();
  return (k) => I18N[k][lang];
}

export function LanguageSelect({ compact = false, className = "" }: { compact?: boolean; className?: string }) {
  const lang = useLang();
  return (
    <span className={`relative inline-flex items-center ${className}`}>
      <Icon name="globe" className="pointer-events-none absolute left-2.5 h-4 w-4 text-muted" />
      {/* A plain-string name: browsers compute names from hidden multi-language labels unreliably. */}
      <select
        aria-label={I18N["nav.language"][lang]}
        value={lang}
        onChange={(e) => isLang(e.target.value) && setLang(e.target.value)}
        className="h-9 cursor-pointer appearance-none rounded-full bg-surface-2 py-1 pl-8 pr-3 text-sm font-medium text-ink ring-1 ring-line hover:ring-blue/60"
      >
        {LANGS.map((l) => (
          <option key={l} value={l} lang={l} className="bg-navy text-ink">
            {compact ? LANG_SHORT[l] : LANG_LABEL[l]}
          </option>
        ))}
      </select>
    </span>
  );
}
