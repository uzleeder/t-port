"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { PlacePhoto } from "./PlacePhoto";
import { CompareToggle, CompareTray } from "./Compare";
import { Icon, type IconName } from "./Icons";
import { ModeIcon } from "./ModeIcon";
import { StateMessage } from "./Notices";
import { PageBanner } from "./PageBanner";
import { ApiError, clientApi } from "@/lib/api";
import { formatDateLong, formatDuration, formatPriceRange, formatTimestamp, localTime, MODE_LABEL, timeAgo } from "@/lib/format";
import { notifySessionChanged, useMe } from "@/lib/session";
import type { Journey, Page } from "@/lib/types";

type Tab = "saved" | "past" | "history";

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

const PAGE = 50;
const SNAPSHOT_STALE_MS = 60 * 60 * 1000; // older snapshots get a "may have changed" notice

/** "My Trips": saved journeys and search history. */
export function Dashboard() {
  const [me] = useMe();
  const [saved, setSaved] = useState<Page<Saved> | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [today, setToday] = useState<string>("");
  const [nowMs, setNowMs] = useState<number | undefined>(undefined);
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState<Tab>("saved");

  useEffect(() => {
    const now = Date.now();
    /* eslint-disable react-hooks/set-state-in-effect -- client clock, read once after mount */
    setToday(new Date(now + 5 * 3_600_000).toISOString().slice(0, 10));
    setNowMs(now);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

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
    return <div role="status" aria-label="Loading" className="h-64 animate-pulse rounded-3xl bg-surface" />;
  }
  if (me.status === "anonymous") {
    return (
      <StateMessage title="Sign in to see your trips" action={{ href: "/login?next=/dashboard", label: "Sign in" }}>
        <p>Your saved journeys and recent searches appear here.</p>
      </StateMessage>
    );
  }
  if (me.status === "error") {
    return (
      <StateMessage tone="error" title="My Trips unavailable">
        <p>{me.message}</p>
      </StateMessage>
    );
  }

  const { recent_searches } = me.me;
  const all = saved?.items ?? [];
  const isPast = (x: Saved) => !!(x.travel_date && today && x.travel_date < today);
  const upcomingItems = all.filter((x) => !isPast(x));
  const pastItems = all.filter(isPast);
  const shown = tab === "past" ? pastItems : upcomingItems;
  const stats: [IconName, string, string | number][] = [
    ["bookmark", "Saved trips", saved?.total ?? me.me.saved_count],
    ["calendar", "Upcoming", saved ? upcomingItems.length : "—"],
    ["clock", "Past trips", saved ? pastItems.length : "—"],
    ["search", "Recent searches", recent_searches.length],
  ];
  const tabs: [Tab, string, IconName, number | string][] = [
    ["saved", "Saved trips", "bookmark", saved ? upcomingItems.length : "…"],
    ["past", "Past trips", "clock", saved ? pastItems.length : "…"],
    ["history", "History", "search", recent_searches.length],
  ];

  return (
    <div className="space-y-6">
      <PageBanner
        icon="bookmark"
        title="My Trips"
        subtitle="Your personal travel hub. Save, compare and revisit your journeys anytime."
      />

      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map(([icon, label, value]) => (
          <div key={label} className="flex items-center gap-4 rounded-3xl bg-surface p-5 shadow-soft">
            <Icon name={icon} className="h-8 w-8 shrink-0 text-gold" />
            <div className="min-w-0">
              <dt className="text-sm text-muted">{label}</dt>
              <dd className="text-2xl font-bold">{value}</dd>
            </div>
          </div>
        ))}
      </dl>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1fr)_20rem] xl:items-start">
        <div className="space-y-4 rounded-3xl bg-surface p-4 shadow-soft sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div role="tablist" aria-label="My Trips views" className="flex flex-wrap gap-2">
              {tabs.map(([key, label, icon, count]) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={tab === key}
                  onClick={() => setTab(key)}
                  className={`flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-medium transition ${
                    tab === key ? "bg-blue text-white" : "text-muted ring-1 ring-line hover:text-ink"
                  }`}
                >
                  <Icon name={icon} className="h-4 w-4" /> {label} ({count})
                </button>
              ))}
            </div>
            <Link href="/search" className="btn-gold flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold">
              <Icon name="search" className="h-4 w-4" /> Plan a new trip
            </Link>
          </div>

          {tab === "history" ? (
            <section aria-labelledby="recent-h">
              <h2 id="recent-h" className="sr-only">
                History
              </h2>
              {recent_searches.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted">Searches you make while signed in appear here.</p>
              ) : (
                <ul className="divide-y divide-line/60">
                  {recent_searches.map((r) => {
                    const stale = !!(today && r.travel_date < today);
                    const qs = `origin=${r.origin_id}&destination=${r.destination_id}${stale ? "" : `&date=${r.travel_date}`}${r.modes.length ? `&modes=${r.modes.join(",")}` : ""}`;
                    return (
                      <li key={r.created_at + r.origin_id} className="flex flex-wrap items-center gap-3 py-3">
                        <Icon name="route" className="h-5 w-5 text-sky" />
                        <span className="min-w-[10rem] flex-1 font-medium capitalize">
                          {r.origin_id} → {r.destination_id}
                        </span>
                        <span className="text-sm text-muted">{r.modes.length ? r.modes.join(" · ") : "All modes"}</span>
                        <span className="w-36 text-sm text-muted">{formatDateLong(r.travel_date)}</span>
                        <Link
                          href={`/search?${qs}`}
                          className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm ring-1 ring-line hover:ring-blue"
                        >
                          <Icon name="arrowUpRight" className="h-4 w-4" /> {stale ? "Search again" : "Reopen"}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          ) : (
            <section aria-labelledby="saved-h">
              <h2 id="saved-h" className="text-lg font-semibold">
                {tab === "past" ? "Past saved journeys" : "Saved journeys"}{" "}
                {saved && <span className="text-muted">({saved.total})</span>}
              </h2>
              <p className="mt-1 text-sm text-muted">
                Prices and times are what you saw when saving. View a trip to see current data.
              </p>
              {error && (
                <p role="alert" className="mt-3 text-sm text-danger">
                  {error}
                </p>
              )}
              {!saved && !error && <div className="mt-4 h-24 animate-pulse rounded-2xl bg-card" />}
              {saved && saved.total === 0 && (
                <div className="mt-4">
                  <StateMessage title="No saved journeys yet" action={{ href: "/search", label: "Find a journey" }}>
                    <p>Open any journey and choose “Save journey”.</p>
                  </StateMessage>
                </div>
              )}
              {saved && saved.total > 0 && shown.length === 0 && (
                <p className="py-6 text-center text-sm text-muted">
                  {tab === "past" ? "No past trips among your saved journeys." : "All your saved journeys are in the past."}
                </p>
              )}
              <ul className="mt-4 space-y-3">
                {shown.map((s) => (
                  <TripRow
                    key={s.id}
                    s={s}
                    past={isPast(s)}
                    nowMs={nowMs}
                    confirming={confirming === s.id}
                    onAsk={() => setConfirming(s.id)}
                    onCancel={() => setConfirming(null)}
                    onRemove={() => remove(s.id)}
                  />
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside className="space-y-4" aria-label="Recent searches">
          <section className="rounded-3xl bg-surface p-5 shadow-soft">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 font-semibold">
                <Icon name="clock" className="h-5 w-5 text-gold" /> Recent searches
              </h2>
              <button type="button" onClick={() => setTab("history")} className="text-sm text-sky hover:underline">
                See all
              </button>
            </div>
            <ul className="mt-3 space-y-2">
              {recent_searches.slice(0, 4).map((r) => (
                <li key={r.created_at + r.origin_id}>
                  <Link
                    href={`/search?origin=${r.origin_id}&destination=${r.destination_id}`}
                    className="flex items-center gap-3 rounded-2xl bg-card px-3 py-2.5 hover:ring-1 hover:ring-blue"
                  >
                    <Icon name="route" className="h-5 w-5 text-sky" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold capitalize">
                        {r.origin_id} → {r.destination_id}
                      </span>
                      <span className="block text-xs text-muted">{formatDateLong(r.travel_date)}</span>
                    </span>
                  </Link>
                </li>
              ))}
              {recent_searches.length === 0 && <li className="text-sm text-muted">No searches yet.</li>}
            </ul>
          </section>
          <CompareTray />
        </aside>
      </div>
    </div>
  );
}

function TripRow({
  s,
  past,
  nowMs,
  confirming,
  onAsk,
  onCancel,
  onRemove,
}: {
  s: Saved;
  past: boolean;
  nowMs: number | undefined;
  confirming: boolean;
  onAsk: () => void;
  onCancel: () => void;
  onRemove: () => void;
}) {
  const j = s.snapshot;
  const age = nowMs === undefined ? 0 : nowMs - new Date(s.snapshot_taken_at).getTime();
  const status = past
    ? { label: "Trip date passed", tone: "text-muted ring-line" }
    : age > 24 * SNAPSHOT_STALE_MS
      ? { label: "Price may be outdated", tone: "text-danger ring-danger/40" }
      : age > SNAPSHOT_STALE_MS
        ? { label: "Check current price", tone: "text-gold ring-gold/50" }
        : { label: "Price fresh", tone: "text-success ring-success/40" };
  const operators = [...new Set(j.legs.map((l) => l.operator))].join(" + ");
  return (
    <li className="grid gap-4 rounded-3xl bg-card p-3 md:grid-cols-[12rem_minmax(0,1fr)_auto] md:items-center">
      <div aria-hidden="true" className="relative hidden h-28 overflow-hidden rounded-2xl md:block">
        <PlacePhoto id={s.destination_id} decorative sizes="192px" />
        <span className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
      </div>
      <div className="min-w-0 px-1">
        <p className="text-lg font-semibold">
          {j.origin_name} → {j.destination_name}
        </p>
        <p className="mt-0.5 text-sm text-muted">{s.travel_date ? formatDateLong(s.travel_date) : "Flexible date"}</p>
        <p className="mt-2 flex flex-wrap items-center gap-3 text-sm">
          {j.modes.map((m) => (
            <span key={m} className="flex items-center gap-1.5 text-sky">
              <ModeIcon mode={m} className="h-4 w-4" /> {MODE_LABEL[m]}
            </span>
          ))}
          <span className="text-muted">{operators}</span>
          <span className="flex items-center gap-1 text-muted">
            <Icon name="clock" className="h-4 w-4" /> {formatDuration(j.total_minutes)} · departs{" "}
            {localTime(j.legs[0]?.departure_local ?? null)}
          </span>
          {j.is_demo && <span className="rounded-full bg-gold/15 px-2 py-0.5 text-xs text-gold">Demo data</span>}
        </p>
        {s.note && <p className="mt-1 text-sm">“{s.note}”</p>}
      </div>
      <div className="flex flex-col items-start gap-2 md:items-end">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${status.tone}`}>
          {status.label} · saved {timeAgo(s.snapshot_taken_at, nowMs) ?? formatTimestamp(s.snapshot_taken_at)}
        </span>
        <p className="text-xl font-bold text-gold tabular-nums">{formatPriceRange(j.price, j.price_max, j.currency)}</p>
        <div className="flex flex-wrap items-center gap-2">
          {!past && (
            <Link
              href={`/journeys/${encodeURIComponent(s.journey_id)}`}
              className="flex items-center gap-1.5 rounded-full bg-blue px-4 py-2 text-sm font-semibold text-white"
            >
              View trip <Icon name="arrowRight" className="h-4 w-4" />
            </Link>
          )}
          {!past && <CompareToggle id={s.journey_id} label={`${j.origin_name} to ${j.destination_name}`} />}
          {confirming ? (
            <>
              <button type="button" onClick={onRemove} className="rounded-full bg-danger/20 px-3 py-2 text-sm text-danger hover:bg-danger/30">
                Confirm remove
              </button>
              <button type="button" onClick={onCancel} className="rounded-full px-3 py-2 text-sm text-muted hover:text-ink">
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={onAsk}
              className="rounded-full px-3 py-2 text-sm text-muted ring-1 ring-line hover:text-danger hover:ring-danger/50"
              aria-label={`Remove saved journey ${j.origin_name} to ${j.destination_name}`}
            >
              Remove
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

/** Permanently deletes the account after re-entering the password. */
export function DeleteAccount() {
  const router = useRouter();
  const id = useId();
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
    <section aria-labelledby={`${id}-h`} className="rounded-3xl border border-danger/40 bg-surface p-5 shadow-soft">
      <h2 id={`${id}-h`} className="flex items-center gap-2 font-semibold">
        <Icon name="shield" className="h-5 w-5 text-danger" /> Delete account
      </h2>
      <p className="mt-1 text-sm text-muted">
        Permanently removes your account, photo, sessions, saved journeys and preferences. This cannot be undone.
      </p>
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="mt-3 rounded-full border border-danger/60 px-4 py-2 text-sm text-danger hover:bg-danger/10"
        >
          Delete my account…
        </button>
      ) : (
        <form method="post" onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor={`${id}-pw`} className="mb-1 block text-xs text-muted">
              Confirm with your password
            </label>
            <input
              id={`${id}-pw`}
              name="password"
              type="password"
              required
              autoComplete="current-password"
              className="rounded-xl border border-line bg-card px-3 py-2 text-ink focus:border-blue"
            />
          </div>
          <button
            type="submit"
            disabled={pending}
            className="rounded-full bg-danger/20 px-4 py-2 text-sm text-danger hover:bg-danger/30 disabled:opacity-60"
          >
            {pending ? "Deleting…" : "Permanently delete"}
          </button>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              setError(null);
            }}
            className="rounded-full px-3 py-2 text-sm text-muted hover:text-ink"
          >
            Cancel
          </button>
          {error && (
            <p role="alert" className="w-full text-sm text-danger">
              {error}
            </p>
          )}
        </form>
      )}
    </section>
  );
}
