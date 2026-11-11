"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DemoBadge } from "./Badges";
import { StateMessage } from "./Notices";
import { ApiError, clientApi } from "@/lib/api";
import { formatDateLong, formatDuration, formatPriceRange, formatTimestamp, localTime } from "@/lib/format";
import { notifySessionChanged, useMe } from "@/lib/session";
import type { Journey, Page } from "@/lib/types";

interface Saved {
  id: string;
  journey_id: string;
  origin_id: string;
  destination_id: string;
  travel_date: string | null;
  note: string | null;
  snapshot: Journey & { origin_name: string; destination_name: string };
  snapshot_taken_at: string;
  created_at: string;
}

const PAGE = 10;

export function Dashboard() {
  const [me] = useMe();
  const [saved, setSaved] = useState<Page<Saved> | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [today, setToday] = useState<string>("");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- client clock, read once after mount
    setToday(new Date(Date.now() + 5 * 3_600_000).toISOString().slice(0, 10));
  }, []);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (me.status !== "ready") return;
    let cancelled = false;
    clientApi<Page<Saved>>(`/api/v1/saved?limit=${PAGE}&offset=${offset}`)
      .then((page) => {
        if (cancelled) return;
        setSaved(page);
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Could not load saved journeys.");
      });
    return () => {
      cancelled = true;
    };
  }, [me.status, offset, reloadKey]);

  async function remove(id: string) {
    try {
      await clientApi(`/api/v1/saved/${id}`, { method: "DELETE" });
      setConfirming(null);
      notifySessionChanged();
      if (saved && saved.items.length === 1 && offset > 0) setOffset(offset - PAGE);
      else setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not remove the journey.");
    }
  }

  if (me.status === "loading") {
    return <div role="status" aria-label="Loading" className="h-64 animate-pulse rounded-2xl bg-surface" />;
  }
  if (me.status === "anonymous") {
    return (
      <StateMessage title="Sign in to see your dashboard" action={{ href: "/login?next=/dashboard", label: "Sign in" }}>
        <p>Your saved journeys and recent searches appear here.</p>
      </StateMessage>
    );
  }
  if (me.status === "error") {
    return <StateMessage tone="error" title="Dashboard unavailable"><p>{me.message}</p></StateMessage>;
  }

  const { user, recent_searches } = me.me;
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-bold sm:text-3xl">
          Welcome{user.display_name ? `, ${user.display_name}` : ""}
        </h1>
        <p className="mt-1 text-muted">{user.email}</p>
      </header>

      <section aria-labelledby="saved-h">
        <h2 id="saved-h" className="text-xl font-semibold">
          Saved journeys {saved && <span className="text-muted">({saved.total})</span>}
        </h2>
        <p className="mt-1 text-sm text-muted">
          Prices and times below are what you saw when saving. Open a journey to see current data.
        </p>
        {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
        {!saved && !error && <div className="mt-4 h-24 animate-pulse rounded-2xl bg-surface" />}
        {saved && saved.total === 0 && (
          <div className="mt-4">
            <StateMessage title="No saved journeys yet" action={{ href: "/search", label: "Find a journey" }}>
              <p>Open any journey and choose “Save journey”.</p>
            </StateMessage>
          </div>
        )}
        <ul className="mt-4 space-y-3">
          {saved?.items.map((s) => {
            const j = s.snapshot;
            const past = !!(s.travel_date && today && s.travel_date < today);
            return (
              <li key={s.id} className="rounded-2xl border border-line bg-surface p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">
                      {j.origin_name} → {j.destination_name}
                      {past && <span className="ml-2 text-xs text-muted">(past)</span>}
                    </p>
                    <p className="text-sm text-muted">
                      {s.travel_date ? formatDateLong(s.travel_date) : "Flexible date"} ·{" "}
                      {localTime(j.legs[0]?.departure_local ?? null)} · {formatDuration(j.total_minutes)} ·{" "}
                      {j.modes.join(" + ")}
                    </p>
                    {s.note && <p className="mt-1 text-sm">“{s.note}”</p>}
                    <p className="mt-1 text-xs text-muted">
                      {formatPriceRange(j.price, j.price_max, j.currency)} when saved on{" "}
                      {formatTimestamp(s.snapshot_taken_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {j.is_demo && <DemoBadge />}
                    {!past && (
                      <Link href={`/journeys/${encodeURIComponent(s.journey_id)}`}
                        className="rounded-lg border border-line px-3 py-1.5 text-sm hover:border-blue">
                        View current
                      </Link>
                    )}
                    {confirming === s.id ? (
                      <>
                        <button type="button" onClick={() => remove(s.id)}
                          className="rounded-lg bg-danger/20 px-3 py-1.5 text-sm text-danger hover:bg-danger/30">
                          Confirm remove
                        </button>
                        <button type="button" onClick={() => setConfirming(null)}
                          className="rounded-lg px-3 py-1.5 text-sm text-muted hover:text-ink">
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button type="button" onClick={() => setConfirming(s.id)}
                        className="rounded-lg px-3 py-1.5 text-sm text-muted hover:text-danger"
                        aria-label={`Remove saved journey ${j.origin_name} to ${j.destination_name}`}>
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
        {saved && saved.total > PAGE && (
          <nav aria-label="Saved journeys pages" className="mt-4 flex items-center justify-center gap-4 text-sm">
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}
              className="rounded-lg border border-line px-3 py-2 disabled:opacity-40">Previous</button>
            <span className="text-muted">
              {offset + 1}–{Math.min(offset + PAGE, saved.total)} of {saved.total}
            </span>
            <button type="button" disabled={offset + PAGE >= saved.total} onClick={() => setOffset(offset + PAGE)}
              className="rounded-lg border border-line px-3 py-2 disabled:opacity-40">Next</button>
          </nav>
        )}
      </section>

      <section aria-labelledby="recent-h">
        <h2 id="recent-h" className="text-xl font-semibold">Recent searches</h2>
        {recent_searches.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Searches you make while signed in appear here.</p>
        ) : (
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {recent_searches.map((r) => {
              const stale = !!(today && r.travel_date < today);
              const qs = `origin=${r.origin_id}&destination=${r.destination_id}${stale ? "" : `&date=${r.travel_date}`}${r.modes.length ? `&modes=${r.modes.join(",")}` : ""}`;
              return (
                <li key={r.created_at + r.origin_id}>
                  <Link href={`/search?${qs}`}
                    className="block rounded-xl border border-line bg-surface px-4 py-3 text-sm hover:border-blue">
                    <span className="capitalize">{r.origin_id}</span> → <span className="capitalize">{r.destination_id}</span>
                    <span className="block text-xs text-muted">
                      {stale ? "Search again for tomorrow" : formatDateLong(r.travel_date)}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <DeleteAccount />
    </div>
  );
}

function DeleteAccount() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const password = String(new FormData(e.currentTarget).get("password") ?? "");
    setPending(true);
    setError(null);
    try {
      await clientApi("/api/v1/me", { method: "DELETE", body: JSON.stringify({ password }) });
      notifySessionChanged();
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the account.");
      setPending(false);
    }
  }

  return (
    <section aria-labelledby="danger-h" className="rounded-2xl border border-danger/40 p-4">
      <h2 id="danger-h" className="font-semibold">Delete account</h2>
      <p className="mt-1 text-sm text-muted">
        Permanently removes your account, sessions and saved journeys. This cannot be undone.
      </p>
      {!open ? (
        <button type="button" onClick={() => setOpen(true)}
          className="mt-3 rounded-lg border border-danger/60 px-3 py-1.5 text-sm text-danger hover:bg-danger/10">
          Delete my account…
        </button>
      ) : (
        <form method="post" onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor="delete-pw" className="mb-1 block text-xs text-muted">Confirm with your password</label>
            <input id="delete-pw" name="password" type="password" required autoComplete="current-password"
              className="rounded-lg border border-line bg-navy px-3 py-2 text-ink focus:border-blue" />
          </div>
          <button type="submit" disabled={pending}
            className="rounded-lg bg-danger/20 px-3 py-2 text-sm text-danger hover:bg-danger/30 disabled:opacity-60">
            {pending ? "Deleting…" : "Permanently delete"}
          </button>
          <button type="button" onClick={() => { setOpen(false); setError(null); }}
            className="rounded-lg px-3 py-2 text-sm text-muted hover:text-ink">
            Cancel
          </button>
          {error && <p role="alert" className="w-full text-sm text-danger">{error}</p>}
        </form>
      )}
    </section>
  );
}
