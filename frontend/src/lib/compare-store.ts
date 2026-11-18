/**
 * Journeys picked for side-by-side comparison. Kept in sessionStorage so the selection survives
 * pagination and filter changes within a tab, and read through useSyncExternalStore.
 */

export const MAX_COMPARE = 4;
const KEY = "tport.compare";
const EMPTY: string[] = [];

let cache: string[] | null = null;
const listeners = new Set<() => void>();

/** Pure toggle: adds or removes ``id``; refuses to add beyond ``max``. */
export function nextSelection(current: string[], id: string, max = MAX_COMPARE): string[] {
  if (current.includes(id)) return current.filter((x) => x !== id);
  if (current.length >= max) return current;
  return [...current, id];
}

/** /compare URL; IDs are encoded individually (multi-leg IDs contain "+" and "~"). */
export function compareHref(ids: string[]): string {
  return `/compare?ids=${ids.map(encodeURIComponent).join(",")}`;
}

function read(): string[] {
  if (cache) return cache;
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(KEY) ?? "[]");
    cache = Array.isArray(parsed)
      ? parsed.filter((x): x is string => typeof x === "string" && x.length <= 128).slice(0, MAX_COMPARE)
      : [];
  } catch {
    cache = [];
  }
  return cache;
}

function write(ids: string[]): void {
  cache = ids;
  try {
    sessionStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    // Storage unavailable (private mode): the selection still works for this page view.
  }
  listeners.forEach((l) => l());
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const getSnapshot = read;
export const getServerSnapshot = (): string[] => EMPTY;

export function toggleCompare(id: string): void {
  write(nextSelection(read(), id));
}

export function clearCompare(): void {
  write([]);
}
