"use client";

import Link from "next/link";
import { Icon } from "./Icons";
import { formatDateLong } from "@/lib/format";
import { useMe } from "@/lib/session";

/** "Your recent trips": the signed-in user's latest searches (nothing is shown when signed out). */
export function RecentSearches() {
  const [me] = useMe();
  if (me.status !== "ready" || me.me.recent_searches.length === 0) return null;
  return (
    <section aria-labelledby="recent-home-h" className="rounded-3xl bg-surface p-5 shadow-soft">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 id="recent-home-h" className="flex items-center gap-2 text-lg font-semibold">
          <Icon name="clock" className="h-5 w-5 text-blue" /> Your recent searches
        </h2>
        <Link href="/dashboard" className="flex items-center gap-1 text-sm font-medium text-blue hover:underline">
          See all <Icon name="arrowRight" className="h-4 w-4" />
        </Link>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {me.me.recent_searches.slice(0, 3).map((r) => (
          <li key={r.created_at + r.origin_id}>
            <Link
              href={`/search?origin=${r.origin_id}&destination=${r.destination_id}`}
              className="flex items-center gap-3 rounded-2xl bg-card px-3 py-2.5 hover:bg-surface-2"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue/10 text-blue">
                <Icon name="route" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold capitalize">
                  {r.origin_id} → {r.destination_id}
                </span>
                <span className="block text-xs text-muted">{formatDateLong(r.travel_date)}</span>
              </span>
              <Icon name="chevronLeft" className="h-4 w-4 rotate-180 text-muted" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
