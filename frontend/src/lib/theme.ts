/**
 * Theme preference ("system" | "light" | "dark"), kept per device in localStorage and applied as
 * <html data-theme>. The inline script in app/layout.tsx applies it before first paint; this module
 * keeps it in sync afterwards and follows the system setting while the preference is "system".
 */

export type ThemePref = "system" | "light" | "dark";
const KEY = "tport.theme";
const listeners = new Set<() => void>();
let media: MediaQueryList | null = null;

function systemTheme(): "light" | "dark" {
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function apply(pref: ThemePref) {
  document.documentElement.dataset.theme = pref === "system" ? systemTheme() : pref;
}

export function setThemePref(pref: ThemePref) {
  try {
    if (pref === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, pref);
  } catch {
    // Storage blocked: the choice still applies to this page view.
  }
  apply(pref);
  listeners.forEach((l) => l());
}

export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener);
  if (!media) {
    media = window.matchMedia("(prefers-color-scheme: light)");
    media.addEventListener("change", () => {
      if (readPref() === "system") apply("system");
      listeners.forEach((l) => l());
    });
  }
  return () => listeners.delete(listener);
}

export const serverPref = (): ThemePref => "system";
