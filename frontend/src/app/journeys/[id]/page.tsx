import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Badge, DemoBadge, FreshnessBadge, PriceTypeBadge } from "@/components/Badges";
import { ModeIcon } from "@/components/ModeIcon";
import { DemoNotice, StateMessage } from "@/components/Notices";
import { SaveJourneyButton } from "@/components/SaveJourneyButton";
import { ApiError } from "@/lib/api";
import { requestTime, serverApi } from "@/lib/server-api";
import {
  dayOffset,
  formatDateLong,
  formatDuration,
  formatMoney,
  formatPriceRange,
  formatTimestamp,
  localTime,
  MODE_LABEL,
  timeAgo,
} from "@/lib/format";
import type { JourneyDetail, Leg, TransferCheck } from "@/lib/types";

export const metadata: Metadata = { title: "Journey details" };

export default function JourneyPage({ params }: PageProps<"/journeys/[id]">) {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <Suspense
        fallback={<div role="status" className="h-96 animate-pulse rounded-2xl bg-surface" aria-label="Loading journey" />}
      >
        <Detail params={params} />
      </Suspense>
    </div>
  );
}

async function Detail({ params }: { params: PageProps<"/journeys/[id]">["params"] }) {
  const { id } = await params;
  const now = await requestTime(); // "updated X ago" depends on the request time
  const journeyId = decodeURIComponent(id);
  let data: JourneyDetail;
  try {
    data = await serverApi<JourneyDetail>(`/api/v1/journeys/${encodeURIComponent(journeyId)}`);
  } catch (e) {
    const err = e instanceof ApiError ? e : null;
    return (
      <StateMessage
        tone="error"
        title={err?.status === 404 ? "Journey not available" : "Could not load this journey"}
        action={{ href: "/search", label: "Start a new search" }}
      >
        <p>{err?.message ?? "Please try again."}</p>
      </StateMessage>
    );
  }

  const { journey, origin, destination } = data;
  const first = journey.legs[0];
  const date = first.departure_local?.slice(0, 10);
  const backQs = date ? `origin=${origin.id}&destination=${destination.id}&date=${date}` : "";

  return (
    <article className="space-y-6">
      <Link href={`/search?${backQs}`} className="text-sm text-blue hover:underline">
        ← Back to results
      </Link>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold sm:text-3xl">
            {origin.name} <span className="text-muted">→</span> {destination.name}
          </h1>
          <p className="mt-1 text-muted">
            {date ? formatDateLong(date) : "Flexible date"} ·{" "}
            {journey.transfers === 0 ? "Direct" : `${journey.transfers} transfer(s)`}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {journey.modes.map((m) => (
              <Badge key={m} tone="blue">
                <ModeIcon mode={m} className="h-3.5 w-3.5" /> {MODE_LABEL[m]}
              </Badge>
            ))}
            {journey.is_demo && <DemoBadge />}
            <FreshnessBadge level={journey.freshness} />
          </div>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-gold tabular-nums">
            {formatPriceRange(journey.price, journey.price_max, journey.currency)}
          </p>
          <p className="text-sm text-muted">
            {journey.is_price_estimate ? "Estimated fare" : "Lowest available fare"}
          </p>
        </div>
      </header>

      {journey.is_demo && <DemoNotice />}

      <dl className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-line bg-surface px-4 py-3">
          <dt className="text-xs uppercase tracking-wider text-muted">Travel time (in vehicle)</dt>
          <dd className="mt-1 font-semibold">{formatDuration(journey.travel_minutes)}</dd>
        </div>
        <div className="rounded-xl border border-line bg-surface px-4 py-3">
          <dt className="text-xs uppercase tracking-wider text-muted">Total incl. transfers</dt>
          <dd className="mt-1 font-semibold">{formatDuration(journey.total_minutes)}</dd>
          <dd className="text-xs text-muted">Station to station; excludes getting to the station.</dd>
        </div>
      </dl>

      <ol className="space-y-4" aria-label="Journey legs">
        {journey.legs.map((leg, i) => (
          <li key={i}>
            <LegCard leg={leg} now={now} />
            {journey.transfer_checks?.[i] && (
              <TransferNote check={journey.transfer_checks[i]} />
            )}
          </li>
        ))}
      </ol>

      {journey.notes.length > 0 && (
        <ul className="list-inside list-disc text-sm text-muted">
          {journey.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}

      <section className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-surface p-4">
        {journey.booking_url ? (
          <Link
            href={`/book/${encodeURIComponent(journey.id)}`}
            prefetch={false}
            className="rounded-xl bg-blue px-5 py-3 font-semibold text-white hover:bg-blue-hover"
          >
            Book with the operator
          </Link>
        ) : journey.legs.length > 1 ? (
          <p className="text-sm text-muted">
            <strong className="text-ink">Each leg is booked separately.</strong>{" "}
            <Link href={`/book/${encodeURIComponent(journey.id)}`} prefetch={false} className="text-blue hover:underline">
              See booking options for each leg
            </Link>
          </p>
        ) : (
          <p className="text-sm text-muted">
            <strong className="text-ink">Booking not available.</strong>{" "}
            {journey.booking_note ??
              (journey.is_demo
                ? "Demo journeys cannot be booked."
                : "This provider has not authorised booking redirects.")}
          </p>
        )}
        <div className="ml-auto">
          <SaveJourneyButton journeyId={journey.id} />
        </div>
      </section>
    </article>
  );
}

function LegCard({ leg, now }: { leg: Leg; now: number }) {
  const plus = dayOffset(leg.departure_local, leg.arrival_local);
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 sm:p-5">
      <div className="flex items-center gap-2 text-sm text-muted">
        <ModeIcon mode={leg.mode} className="h-4 w-4 text-blue" />
        {MODE_LABEL[leg.mode]} · {leg.operator} · Service {leg.service_code}
      </div>
      <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
        <span className="font-bold tabular-nums">{localTime(leg.departure_local)}</span>
        <span>
          {leg.origin.name}
          {leg.origin.code && <span className="text-muted"> ({leg.origin.code})</span>}
        </span>
        <span className="text-xs text-muted">{formatDuration(leg.duration_minutes)}</span>
        <span className="border-l-2 border-dashed border-line pl-3 text-xs text-muted">
          {leg.schedule_type === "on_demand"
            ? "On-demand — arrange the departure time directly."
            : "Scheduled service"}
        </span>
        <span className="font-bold tabular-nums">
          {leg.arrival_local ? localTime(leg.arrival_local) : "—"}
          {plus > 0 && <sup className="ml-1 text-xs text-gold">+{plus}</sup>}
        </span>
        <span>
          {leg.destination.name}
          {leg.destination.code && <span className="text-muted"> ({leg.destination.code})</span>}
        </span>
      </div>
      <table className="mt-4 w-full text-sm">
        <caption className="sr-only">Fares</caption>
        <thead>
          <tr className="text-left text-xs uppercase tracking-wider text-muted">
            <th className="py-1 font-medium">Fare</th>
            <th className="py-1 text-right font-medium">Price</th>
          </tr>
        </thead>
        <tbody>
          {leg.fares.map((f) => (
            <tr key={f.name} className="border-t border-line">
              <td className="py-2">{f.name}</td>
              <td className="py-2 text-right tabular-nums">
                {f.price_max
                  ? formatPriceRange(f.price, f.price_max, f.currency)
                  : formatMoney(f.price, f.currency)}
                {f.is_estimate && <span className="ml-1 text-xs text-muted">(estimate)</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-muted">
        <span className="mb-2 flex flex-wrap gap-2">
          <FreshnessBadge level={leg.timetable_freshness} label="Timetable" />
          <FreshnessBadge level={leg.price_freshness} label="Price" />
          <PriceTypeBadge type={leg.price_type} />
        </span>
        Source: <span className="text-ink">{leg.provider?.name ?? "Unknown source"}</span>
        {leg.provider?.attribution && <> ({leg.provider.attribution})</>} · updated{" "}
        {timeAgo(leg.retrieved_at, now)} ·
        Retrieved {formatTimestamp(leg.retrieved_at)} · Source updated{" "}
        {formatTimestamp(leg.source_updated_at)} (Tashkent time)
      </p>
    </div>
  );
}

function TransferNote({ check }: { check: TransferCheck }) {
  return (
    <div className="my-2 ml-6 rounded-xl border border-gold/60 px-4 py-2 text-sm text-gold" role="note">
      <strong>Transfer:</strong> {formatDuration(check.connection_minutes)} between arriving at{" "}
      {check.from_station} and departing{" "}
      {check.station_change ? `from ${check.to_station}` : "from the same station"} (minimum applied:{" "}
      {formatDuration(check.minimum_minutes)}).{" "}
      {check.station_change && "Travel time between stations isn't in the data. "}
      {check.guaranteed
        ? "Protected connection."
        : "Not guaranteed — separate tickets, and a delay on the first leg is not covered."}
    </div>
  );
}
