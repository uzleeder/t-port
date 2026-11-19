"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { ApiError, clientApi } from "./api";

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
  /** The user's own profile photo (changes when the photo does), or null. */
  avatar_url: string | null;
}

export interface Me {
  user: User;
  saved_count: number;
  recent_searches: {
    origin_id: string;
    destination_id: string;
    travel_date: string;
    modes: string[];
    created_at: string;
  }[];
  session_expires_at: string;
}

export type MeState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "error"; message: string } // couldn't check: NOT the same as signed out
  | { status: "ready"; me: Me };

// One shared /me request per session "version": header, save button and dashboard all reuse it.
let version = 0;
let inflight: { version: number; promise: Promise<MeState> } | null = null;
const listeners = new Set<() => void>();

/** Call after login, logout, saving or deleting so every consumer refetches once. */
export function notifySessionChanged() {
  version += 1;
  inflight = null;
  listeners.forEach((l) => l());
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

function fetchMe(): Promise<MeState> {
  if (inflight && inflight.version === version) return inflight.promise;
  const promise = clientApi<Me>("/api/v1/me")
    .then((me): MeState => ({ status: "ready", me }))
    .catch((e): MeState => {
      if (e instanceof ApiError && e.status === 401) return { status: "anonymous" };
      inflight = null; // allow a retry
      return {
        status: "error",
        message: e instanceof ApiError && e.status === 429
          ? "Too many requests. Please wait a moment."
          : "Couldn't check your sign-in status.",
      };
    });
  inflight = { version, promise };
  return promise;
}

/**
 * Current account state; `retry` refetches after an error. With `keepPrevious`, a signed-in view
 * keeps showing the last known account while it refreshes (no flash of "loading" after an edit).
 */
export function useMe({ keepPrevious = false }: { keepPrevious?: boolean } = {}): [MeState, () => void] {
  const v = useSyncExternalStore(subscribe, () => version, () => 0);
  const [state, setState] = useState<{ v: number; s: MeState }>({ v: -1, s: { status: "loading" } });

  useEffect(() => {
    let cancelled = false;
    fetchMe().then((s) => !cancelled && setState({ v, s }));
    return () => {
      cancelled = true;
    };
  }, [v]);

  if (state.v === v) return [state.s, notifySessionChanged];
  return [keepPrevious && state.s.status === "ready" ? state.s : { status: "loading" }, notifySessionChanged];
}
