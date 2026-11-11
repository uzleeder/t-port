import Link from "next/link";
import { Badge, DemoBadge, FreshnessBadge, PRICE_TYPE_TEXT, PriceTypeBadge } from "./Badges";
import { ModeIcon } from "./ModeIcon";
import { dayOffset, formatDuration, formatPriceRange, localTime, MODE_LABEL, timeAgo } from "@/lib/format";
import type { Journey } from "@/lib/types";

export function JourneyCard({
  journey,
  highlights = [],
  now,
}: {
  journey: Journey;
  highlights?: string[];
  /** Reference time for "updated X ago" (pass from the server render; omitted = not shown). */
  now?: number;
}) {
  const first = journey.legs[0];
  const last = journey.legs[journey.legs.length - 1];
  const plus = dayOffset(first.departure_local, last.arrival_local);
  const operators = [...new Set(journey.legs.map((l) => l.operator))].join(" + ");
  const scheduled = first.departure_local !== null;
  const sources = [...new Set(journey.legs.map((l) => l.provider?.name ?? "Unknown source"))].join(" + ");
  const updated = timeAgo(journey.legs.map((l) => l.retrieved_at).sort()[0], now);

  return (
    <article className="group relative rounded-2xl border border-line bg-surface p-4 transition hover:border-blue/60 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xl font-bold tabular-nums sm:text-2xl">
            {scheduled ? (
              <>
                {localTime(first.departure_local)}
                <span className="mx-2 text-muted" aria-hidden="true">
                  →
                </span>
                <span className="sr-only"> to </span>
                {localTime(last.arrival_local)}
                {plus > 0 && (
                  <sup className="ml-1 text-xs text-gold" title="Arrives on a later day">
                    +{plus}
                  </sup>
                )}
              </>
            ) : (
              "Flexible departure"
            )}
          </p>
          <p className="mt-1 text-sm text-muted">
            {formatDuration(journey.total_minutes)} ·{" "}
            {journey.transfers === 0
              ? "Direct"
              : `${journey.transfers} transfer${journey.transfers > 1 ? "s" : ""}`}{" "}
            · {operators}
          </p>
          <p className="mt-1 truncate text-sm text-muted">
            {first.origin.name} → {last.destination.name}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xl font-bold text-gold tabular-nums sm:text-2xl">
            {formatPriceRange(journey.price, journey.price_max, journey.currency)}
          </p>
          <p className="text-xs text-muted">{PRICE_TYPE_TEXT[journey.price_type].label}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {journey.legs.map((leg, i) => (
          <Badge key={i} tone="blue">
            <ModeIcon mode={leg.mode} className="h-3.5 w-3.5" />
            {MODE_LABEL[leg.mode]}
          </Badge>
        ))}
        {highlights.map((h) => (
          <Badge key={h} tone="gold">
            {h}
          </Badge>
        ))}
        {journey.is_demo && <DemoBadge />}
        {journey.freshness !== "fresh" && <FreshnessBadge level={journey.freshness} />}
        {!journey.is_demo && journey.price_type !== "demo" && <PriceTypeBadge type={journey.price_type} />}
        <Link
          href={`/journeys/${encodeURIComponent(journey.id)}`}
          className="ml-auto text-sm font-medium text-blue after:absolute after:inset-0 after:content-[''] hover:underline"
        >
          View details<span className="sr-only">: {operators}</span>
        </Link>
      </div>
      <p className="mt-2 text-xs text-muted">
        Source: {sources}
        {updated && <> · updated {updated}</>} ·{" "}
        {journey.booking_url ? "Book on the operator's site" : "Not bookable through T-Port"}
      </p>
    </article>
  );
}
