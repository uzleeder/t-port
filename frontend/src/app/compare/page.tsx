import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { Suspense } from "react";
import { Badge, DemoBadge, FreshnessBadge, PRICE_TYPE_TEXT } from "@/components/Badges";
import { ModeIcon } from "@/components/ModeIcon";
import { DemoNotice, StateMessage } from "@/components/Notices";
import { ApiError } from "@/lib/api";
import { MAX_COMPARE } from "@/lib/compare-store";
import { dayOffset, formatDateLong, formatDuration, formatPriceRange, localTime, MODE_LABEL } from "@/lib/format";
import { serverApi } from "@/lib/server-api";
import type { CompareResponse, Journey } from "@/lib/types";

export const metadata: Metadata = { title: "Compare journeys" };

export default function ComparePage({ searchParams }: PageProps<"/compare">) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <Suspense
        fallback={<div role="status" className="h-96 animate-pulse rounded-2xl bg-surface" aria-label="Loading comparison" />}
      >
        <Comparison searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

type Best = CompareResponse["best"];

const BEST_LABEL: [keyof Best, string][] = [
  ["cheapest", "Cheapest"],
  ["fastest", "Fastest"],
  ["fewest_transfers", "Fewest changes"],
  ["earliest_departure", "Leaves first"],
  ["earliest_arrival", "Arrives first"],
];

interface Row {
  label: string;
  best?: keyof Best;
  cell: (j: Journey) => ReactNode;
}

const ROWS: Row[] = [
  {
    label: "Modes",
    cell: (j) => (
      <span className="flex flex-wrap gap-1.5">
        {j.modes.map((m) => (
          <Badge key={m} tone="blue">
            <ModeIcon mode={m} className="h-3.5 w-3.5" /> {MODE_LABEL[m]}
          </Badge>
        ))}
      </span>
    ),
  },
  { label: "Operators", cell: (j) => [...new Set(j.legs.map((l) => l.operator))].join(" + ") },
  { label: "Departs", best: "earliest_departure", cell: (j) => localTime(j.legs[0].departure_local) },
  {
    label: "Arrives",
    best: "earliest_arrival",
    cell: (j) => {
      const last = j.legs[j.legs.length - 1];
      const plus = dayOffset(j.legs[0].departure_local, last.arrival_local);
      return (
        <>
          {localTime(last.arrival_local)}
          {plus > 0 && <span className="ml-1 text-xs text-gold">+{plus} day</span>}
        </>
      );
    },
  },
  { label: "Total time", best: "fastest", cell: (j) => formatDuration(j.total_minutes) },
  {
    label: "Changes",
    best: "fewest_transfers",
    cell: (j) =>
      j.transfers === 0
        ? "Direct"
        : `${j.transfers} (${j.legs
            .slice(0, -1)
            .map((l) => l.destination.name)
            .join(", ")})`,
  },
  {
    label: "Price",
    best: "cheapest",
    cell: (j) => (
      <>
        <span className="font-semibold text-gold tabular-nums">
          {formatPriceRange(j.price, j.price_max, j.currency)}
        </span>
        <span className="block text-xs text-muted">{PRICE_TYPE_TEXT[j.price_type].label}</span>
      </>
    ),
  },
  {
    label: "Data",
    cell: (j) => (
      <span className="flex flex-wrap gap-1.5">
        {j.is_demo && <DemoBadge />}
        <FreshnessBadge level={j.freshness} />
      </span>
    ),
  },
  { label: "Source", cell: (j) => [...new Set(j.legs.map((l) => l.provider?.name ?? "Unknown source"))].join(" + ") },
  {
    label: "Booking",
    cell: (j) => (j.booking_url ? "On the operator's site" : (j.booking_note ?? "Not bookable through T-Port")),
  },
];

function first(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v) ?? "";
}

async function Comparison({ searchParams }: { searchParams: PageProps<"/compare">["searchParams"] }) {
  const raw = await searchParams;
  const ids = [...new Set(first(raw.ids).split(",").map((s) => s.trim()).filter(Boolean))].slice(0, MAX_COMPARE);
  if (ids.length < 2) {
    return (
      <StateMessage title="Pick journeys to compare" action={{ href: "/search", label: "Search journeys" }}>
        <p>
          Tick <strong>Compare</strong> on 2 to {MAX_COMPARE} journeys in your search results, then open the
          comparison from the bar at the bottom of the page.
        </p>
      </StateMessage>
    );
  }

  let data: CompareResponse;
  try {
    data = await serverApi<CompareResponse>(`/api/v1/journeys/compare?ids=${encodeURIComponent(ids.join(","))}`);
  } catch (e) {
    const err = e instanceof ApiError ? e : null;
    return (
      <StateMessage tone="error" title="Could not compare these journeys" action={{ href: "/search", label: "Back to search" }}>
        <p>{err?.message ?? "Please try again."}</p>
      </StateMessage>
    );
  }

  const available = data.items.filter((i) => i.available && i.journey);
  const journeys = available.map((i) => i.journey as Journey);
  const missing = data.items.filter((i) => !i.available);
  const head = available[0];
  const date = head?.journey?.legs[0].departure_local?.slice(0, 10);
  const backQs =
    head?.origin && head.destination && date
      ? `origin=${head.origin.id}&destination=${head.destination.id}&date=${date}`
      : "";
  const winners = (id: string) => BEST_LABEL.filter(([key]) => data.best[key].includes(id)).map(([, l]) => l);
  const isBest = (row: Row, id: string) => Boolean(row.best && data.best[row.best].includes(id));

  return (
    <div className="space-y-6">
      <Link href={`/search?${backQs}`} className="text-sm text-blue hover:underline">
        ← Back to results
      </Link>
      <header>
        <h1 className="text-2xl font-bold sm:text-3xl">Compare journeys</h1>
        {head?.origin && head.destination && (
          <p className="mt-1 text-muted">
            {head.origin.name} → {head.destination.name}
            {date ? ` · ${formatDateLong(date)}` : ""}
          </p>
        )}
      </header>

      {journeys.some((j) => j.is_demo) && <DemoNotice />}
      {data.caveats.length > 0 && (
        <ul aria-label="Things to keep in mind" className="space-y-1 rounded-xl border border-gold/50 px-4 py-3 text-sm text-gold">
          {data.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
      {missing.length > 0 && (
        <div role="status" className="rounded-xl border border-danger/60 px-4 py-3 text-sm">
          {missing.map((m) => (
            <p key={m.id} className="text-danger">
              One selected journey is no longer available: {m.reason}
            </p>
          ))}
        </div>
      )}

      {journeys.length === 0 ? (
        <StateMessage title="None of these journeys are available now" action={{ href: "/search", label: "Search again" }}>
          <p>They may have departed or their data may have expired.</p>
        </StateMessage>
      ) : (
        <>
          {/* Wide screens: a real table, one column per journey. */}
          <div className="hidden overflow-x-auto rounded-2xl border border-line md:block">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">
                Side-by-side comparison of {journeys.length} journeys. Best values are marked “best”.
              </caption>
              <thead className="bg-surface-2">
                <tr>
                  <td className="w-36 px-4 py-3" />
                  {journeys.map((j, i) => (
                    <th key={j.id} scope="col" className="px-4 py-3 align-top font-semibold">
                      Option {i + 1}
                      <span className="mt-1 flex flex-wrap gap-1">
                        {winners(j.id).map((w) => (
                          <Badge key={w} tone="gold">
                            {w}
                          </Badge>
                        ))}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROWS.map((row) => (
                  <tr key={row.label} className="border-t border-line">
                    <th scope="row" className="px-4 py-3 align-top font-medium text-muted">
                      {row.label}
                    </th>
                    {journeys.map((j) => (
                      <td key={j.id} className={`px-4 py-3 align-top ${isBest(row, j.id) ? "bg-blue/10" : ""}`}>
                        {row.cell(j)}
                        {isBest(row, j.id) && <span className="ml-2 text-xs font-semibold text-success">best</span>}
                      </td>
                    ))}
                  </tr>
                ))}
                <tr className="border-t border-line">
                  <th scope="row" className="px-4 py-3 font-medium text-muted">
                    Details
                  </th>
                  {journeys.map((j, i) => (
                    <td key={j.id} className="px-4 py-3">
                      <Link href={`/journeys/${encodeURIComponent(j.id)}`} className="text-blue hover:underline">
                        View option {i + 1}
                      </Link>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>

          {/* Phones: one card per journey with the same labelled rows. */}
          <ol className="space-y-4 md:hidden" aria-label="Compared journeys">
            {journeys.map((j, i) => (
              <li key={j.id} className="rounded-2xl border border-line bg-surface p-4">
                <h2 className="font-semibold">Option {i + 1}</h2>
                <div className="mt-1 flex flex-wrap gap-1">
                  {winners(j.id).map((w) => (
                    <Badge key={w} tone="gold">
                      {w}
                    </Badge>
                  ))}
                </div>
                <dl className="mt-3 grid grid-cols-[7rem_1fr] gap-x-3 gap-y-2 text-sm">
                  {ROWS.map((row) => (
                    <div key={row.label} className="contents">
                      <dt className="text-muted">{row.label}</dt>
                      <dd>
                        {row.cell(j)}
                        {isBest(row, j.id) && <span className="ml-2 text-xs font-semibold text-success">best</span>}
                      </dd>
                    </div>
                  ))}
                </dl>
                <Link
                  href={`/journeys/${encodeURIComponent(j.id)}`}
                  className="mt-3 inline-block text-sm font-medium text-blue hover:underline"
                >
                  View option {i + 1} details
                </Link>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
