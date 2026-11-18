"use client";

import { useEffect, useState } from "react";
import { clientApi } from "./api";
import type { SearchParams } from "./format";
import { useMe } from "./session";
import type { Mode, SortKey } from "./types";

export interface Preferences {
  modes: Mode[]; // empty = all
  prefer_modes: Mode[];
  sort: SortKey;
  max_transfers: 0 | 1 | 2;
  max_price: string | null;
  updated_at: string | null;
}

export const DEFAULT_PREFERENCES: Preferences = {
  modes: [],
  prefer_modes: [],
  sort: "recommended",
  max_transfers: 1,
  max_price: null,
  updated_at: null,
};

/** Search parameters a new search starts with: the user's saved defaults over the built-in ones. */
export function searchDefaults(p: Preferences | null): Partial<SearchParams> {
  if (!p) return {};
  return {
    sort: p.sort,
    maxTransfers: p.max_transfers,
    preferModes: p.prefer_modes,
    maxPrice: p.max_price ? String(Number(p.max_price)) : null,
  };
}

let cache: { userId: string; prefs: Preferences } | null = null;

/** Saved preferences of the signed-in user; null while loading, when signed out, or on error. */
export function usePreferences(): [Preferences | null, (p: Preferences) => void] {
  const [me] = useMe();
  const userId = me.status === "ready" ? me.me.user.id : null;
  const [state, setState] = useState<{ userId: string; prefs: Preferences } | null>(null);

  useEffect(() => {
    if (!userId) return;
    if (cache?.userId === userId) return;
    let cancelled = false;
    clientApi<Preferences>("/api/v1/me/preferences")
      .then((prefs) => {
        cache = { userId, prefs };
        if (!cancelled) setState(cache);
      })
      .catch(() => undefined); // preferences are optional: searches simply use built-in defaults
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const current = userId ? (state?.userId === userId ? state : cache?.userId === userId ? cache : null) : null;
  const update = (prefs: Preferences) => {
    if (!userId) return;
    cache = { userId, prefs };
    setState(cache);
  };
  return [current?.prefs ?? null, update];
}
