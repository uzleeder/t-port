import Link from "next/link";
import { Badge, DemoBadge, FreshnessBadge } from "./Badges";
import { ModeIcon } from "./ModeIcon";
import { dayOffset, formatDuration, formatPriceRange, localTime, MODE_LABEL } from "@/lib/format";
import type { Journey } from "@/lib/types";

export function JourneyCard({
  journey,
  highlights = [],
}: {
  journey: Journey;
  highlights?: string[];
}) {
  const first = journey.legs[0];
  const last = journey.legs[journey.legs.length - 1];
  const plus = dayOffset(first.departure_local, last.arrival_local);
  const operators = [...new Set(journey.legs.map((l) => l.operator))].join(" + ");
  const scheduled = first.departure_local !== null;

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
          <p className="text-xs text-muted">
            {journey.is_price_estimate ? "Estimated fare" : "Lowest fare"}
          </p>
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
        <Link
          href={`/journeys/${encodeURIComponent(journey.id)}`}
          className="ml-auto text-sm font-medium text-blue after:absolute after:inset-0 after:content-[''] hover:underline"
        >
          View details<span className="sr-only">: {operators}</span>
        </Link>
      </div>
    </article>
  );
}
