import Link from "next/link";
import { PRICE_TYPE_TEXT } from "./Badges";
import { CompareToggle } from "./Compare";
import { Icon } from "./Icons";
import { ModeIcon } from "./ModeIcon";
import { dayOffset, formatDuration, formatPriceRange, localTime, MODE_LABEL, timeAgo } from "@/lib/format";
import type { Journey } from "@/lib/types";

/**
 * One search result as a wide row (operator · times with a duration line · price · source · action),
 * collapsing to a card in narrow containers. Every value comes from the journey; nothing is invented.
 */
export function JourneyRow({
  journey,
  highlights = [],
  now,
  recommended = false,
}: {
  journey: Journey;
  highlights?: string[];
  now?: number;
  recommended?: boolean;
}) {
  const first = journey.legs[0];
  const last = journey.legs[journey.legs.length - 1];
  const plus = dayOffset(first.departure_local, last.arrival_local);
  const operators = [...new Set(journey.legs.map((l) => l.operator))].join(" + ");
  const sources = [...new Set(journey.legs.map((l) => l.provider?.name ?? "Unknown source"))].join(" + ");
  const updated = timeAgo(journey.legs.map((l) => l.retrieved_at).sort()[0], now);
  const scheduled = first.departure_local !== null;
  const fresh = journey.freshness === "fresh";
  const changes = journey.transfers === 0 ? "Direct" : `${journey.transfers} change${journey.transfers > 1 ? "s" : ""}`;
  const mode = journey.modes.length > 1 ? null : journey.modes[0];

  return (
    <article
      className={`@container group relative rounded-3xl bg-surface p-4 shadow-soft transition hover:bg-card ${
        recommended ? "ring-2 ring-gold/80" : ""
      }`}
    >
      {recommended && (
        <span className="absolute -top-3 right-5 flex items-center gap-1 rounded-full btn-gold px-3 py-0.5 text-xs font-semibold">
          <Icon name="sparkle" className="h-3.5 w-3.5" /> Recommended
        </span>
      )}
      <div className="grid gap-4 @3xl:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_minmax(0,10rem)_minmax(0,11rem)] @3xl:items-center">
        {/* operator */}
        <div className="flex items-center gap-3">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue/15 text-sky ring-1 ring-blue/30">
            {mode ? <ModeIcon mode={mode} className="h-6 w-6" /> : <Icon name="route" className="h-6 w-6" />}
          </span>
          <div className="min-w-0">
            <p className="truncate font-semibold">{operators}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {journey.legs.map((leg, i) => (
                <span key={i} className="flex items-center gap-1 rounded-md bg-surface-2 px-1.5 py-0.5 text-[0.7rem] text-ink/90">
                  <ModeIcon mode={leg.mode} className="h-3 w-3" />
                  {MODE_LABEL[leg.mode]}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* times */}
        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3">
          <div>
            <p className="text-xl font-bold tabular-nums">{scheduled ? localTime(first.departure_local) : "Flexible"}</p>
            <p className="max-w-[8rem] truncate text-xs text-muted">{first.origin.name}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted">{formatDuration(journey.total_minutes)}</p>
            <div className="relative my-1 h-0.5 rounded-full bg-blue/60">
              <span className="absolute -left-0.5 -top-1 h-2.5 w-2.5 rounded-full bg-sky" />
              <span className="absolute -right-0.5 -top-1 h-2.5 w-2.5 rounded-full bg-sky" />
            </div>
            <span className="inline-block rounded-full bg-surface-2 px-2 py-0.5 text-[0.7rem]">{changes}</span>
          </div>
          <div className="text-right">
            <p className="text-xl font-bold tabular-nums">
              {last.arrival_local ? localTime(last.arrival_local) : "Flexible"}
              {plus > 0 && <sup className="ml-0.5 text-xs text-gold">+{plus}</sup>}
            </p>
            <p className="max-w-[8rem] truncate text-xs text-muted">{last.destination.name}</p>
          </div>
        </div>

        {/* price */}
        <div className="@3xl:text-right">
          <p className="text-xl font-bold text-gold tabular-nums">
            {formatPriceRange(journey.price, journey.price_max, journey.currency)}
          </p>
          <p className="text-xs text-muted">{PRICE_TYPE_TEXT[journey.price_type].label}</p>
        </div>

        {/* status + action */}
        <div className="flex flex-wrap items-center gap-2 @3xl:flex-col @3xl:items-end">
          <span
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.7rem] font-medium ring-1 ${
              fresh ? "text-success ring-success/40" : "text-danger ring-danger/40"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${fresh ? "bg-success" : "bg-danger"}`} />
            {fresh ? "Data current" : "Data may be outdated"}
          </span>
          <Link
            href={`/journeys/${encodeURIComponent(journey.id)}`}
            className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold after:absolute after:inset-0 after:content-[''] ${
              recommended ? "btn-gold" : "border border-blue/60 text-ink hover:bg-blue/15"
            }`}
          >
            View details<span className="sr-only">: {operators}</span>
            <Icon name="arrowRight" className="h-4 w-4" />
          </Link>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line/60 pt-3 text-xs text-muted">
        {highlights.map((h) => (
          <span key={h} className="rounded-full bg-gold/15 px-2 py-0.5 font-medium text-gold">
            {h}
          </span>
        ))}
        {journey.is_demo && (
          <span className="rounded-full bg-gold/15 px-2 py-0.5 font-medium text-gold">Demo data</span>
        )}
        <CompareToggle id={journey.id} label={`${localTime(first.departure_local)} ${operators}`} />
        <span className="ml-auto">
          Source: {sources}
          {updated && <> · updated {updated}</>} ·{" "}
          {journey.booking_url ? "Book on the operator's site" : "Not bookable through T-Port"}
        </span>
      </div>
    </article>
  );
}
