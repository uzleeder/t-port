"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, clientApi } from "@/lib/api";
import { notifySessionChanged, useMe } from "@/lib/session";
import type { Page } from "@/lib/types";

type State = "idle" | "saving" | "saved" | "error";

export function SaveJourneyButton({ journeyId }: { journeyId: string }) {
  const [me, retry] = useMe();
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState<string | null>(null);

  // Show "Saved" if this journey is already in the user's list.
  useEffect(() => {
    if (me.status !== "ready" || me.me.saved_count === 0) return;
    let cancelled = false;
    clientApi<Page<{ journey_id: string }>>("/api/v1/saved?limit=100")
      .then((p) => !cancelled && p.items.some((s) => s.journey_id === journeyId) && setState("saved"))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [me, journeyId]);

  if (me.status === "loading") return null;
  if (me.status === "error") {
    return (
      <button type="button" onClick={retry}
        className="rounded-xl border border-line px-4 py-2 text-sm text-muted hover:border-blue">
        {me.message} Retry
      </button>
    );
  }
  if (me.status !== "ready") {
    return (
      <Link href={`/login?next=${encodeURIComponent(`/journeys/${journeyId}`)}`}
        className="rounded-xl border border-line px-4 py-2 text-sm hover:border-blue">
        Sign in to save
      </Link>
    );
  }

  async function save() {
    setState("saving");
    setMessage(null);
    try {
      await clientApi("/api/v1/saved", { method: "POST", body: JSON.stringify({ journey_id: journeyId }) });
      setState("saved");
      notifySessionChanged();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setState("saved");
        return;
      }
      setState("error");
      setMessage(e instanceof ApiError ? e.message : "Could not save.");
    }
  }

  return (
    <div className="flex items-center gap-3">
      {message && <span role="alert" className="text-sm text-danger">{message}</span>}
      {state === "saved" ? (
        <Link href="/dashboard" className="rounded-xl border border-gold/60 px-4 py-2 text-sm text-gold">
          ✓ Saved · View dashboard
        </Link>
      ) : (
        <button type="button" onClick={save} disabled={state === "saving"}
          className="rounded-xl border border-blue px-4 py-2 text-sm font-medium hover:bg-blue/15 disabled:opacity-60">
          {state === "saving" ? "Saving…" : "Save journey"}
        </button>
      )}
    </div>
  );
}
