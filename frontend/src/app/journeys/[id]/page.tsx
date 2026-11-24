import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { Suspense } from "react";
import { FreshnessBadge, PRICE_TYPE_TEXT, PriceTypeBadge } from "@/components/Badges";
import { PlacePhoto } from "@/components/PlacePhoto";
import { AuraLink } from "@/components/AuraLink";
import { Icon, type IconName } from "@/components/Icons";
import { ModeIcon } from "@/components/ModeIcon";
import { DemoNotice, StateMessage } from "@/components/Notices";
import { PageBanner } from "@/components/PageBanner";
import { SaveJourneyButton } from "@/components/SaveJourneyButton";
import { ShareButton } from "@/components/ShareButton";
import { ApiError } from "@/lib/api";
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
import { requestTime, serverApi } from "@/lib/server-api";
import type { Journey, JourneyDetail, Leg, SearchResponse, TransferCheck } from "@/lib/types";

export const metadata: Metadata = { title: "Journey details" };

export default function JourneyPage({ params }: PageProps<"/journeys/[id]">) {
  return (
    <div className="mx-auto max-w-[80rem] px-3 py-4 sm:px-6 lg:px-0 lg:py-0">
      <Suspense
        fallback={<div role="status" className="h-96 animate-pulse rounded-3xl bg-surface" aria-label="Loading journey" />}
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
  const operators = [...new Set(journey.legs.map((l) => l.operator))].join(" + ");
  const providers = [
    ...new Map(journey.legs.flatMap((l) => (l.provider ? [[l.provider.id, l.provider] as const] : []))).values(),
  ];
  const mode = journey.modes.length === 1 ? journey.modes[0] : null;
  const direct = journey.transfers === 0;
  const oldest = journey.legs.map((l) => l.retrieved_at).sort()[0];
  const insight = date ? await compareWithSameDay(journey, origin.id, destination.id, date) : null;

  const highlights: string[] = [
    direct ? "Direct journey — no changes" : `${journey.transfers} change(s), each connection time checked`,
    journey.freshness === "fresh" ? `Data current (updated ${timeAgo(oldest, now) ?? "recently"})` : "Some data may be outdated — check before travelling",
    PRICE_TYPE_TEXT[journey.price_type].label,
    journey.booking_url ? "Bookable on the operator's own site" : "Not bookable through T-Port",
    `Source: ${providers.map((p) => p.name).join(", ") || "unknown"}`,
  ];

  return (
    <article className="space-y-5">
      <PageBanner
        title="Journey Details"
        subtitle="Full information about your selected trip"
        back={{ href: `/search?${backQs}`, label: "Back to results" }}
      />

      <header className="flex flex-wrap items-center gap-5 rounded-3xl bg-surface p-4 shadow-soft">
        <div className="relative h-28 w-44 shrink-0 overflow-hidden rounded-2xl">
          <PlacePhoto id={destination.id} sizes="176px" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap gap-2">
            {journey.modes.map((m) => (
              <span key={m} className="flex items-center gap-1.5 rounded-full bg-blue/20 px-3 py-1 text-sm font-medium text-sky ring-1 ring-blue/40">
                <ModeIcon mode={m} className="h-4 w-4" /> {MODE_LABEL[m]}
              </span>
            ))}
            <span className="rounded-full bg-gold/15 px-3 py-1 text-sm font-semibold text-gold ring-1 ring-gold/50">
              {direct ? "Direct trip" : `${journey.transfers} change${journey.transfers > 1 ? "s" : ""}`}
            </span>
            {journey.is_demo && (
              <span className="rounded-full px-3 py-1 text-sm font-semibold text-gold ring-1 ring-gold/50">Demo data</span>
            )}
          </div>
          <h2 className="mt-2 flex flex-wrap items-center gap-2 text-2xl font-bold sm:text-3xl">
            {origin.name} <Icon name="arrowRight" className="h-6 w-6 text-muted" /> {destination.name}
          </h2>
          <p className="mt-1 text-muted">
            {operators} · Service {journey.legs.map((l) => l.service_code).join(" + ")}
          </p>
          <AuraLink place={destination.name} region={destination.region} className="mt-2" />
        </div>
      </header>

      {journey.is_demo && <DemoNotice />}

      <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Stat icon="clock" label="Duration">{formatDuration(journey.total_minutes)}</Stat>
        <Stat icon="route" label="Transfers" gold={direct}>
          {direct ? "0 (Direct)" : journey.transfers}
        </Stat>
        <Stat icon={mode ? "plane" : "route"} label="Transport type">
          {journey.modes.map((m) => MODE_LABEL[m]).join(" + ")}
        </Stat>
        <Stat icon="coin" label="Price type">{PRICE_TYPE_TEXT[journey.price_type].label}</Stat>
        <Stat icon="calendar" label="Travel date">{date ? formatDateLong(date) : "Flexible"}</Stat>
      </dl>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1fr)_24rem] xl:items-start">
        <div className="space-y-5">
          <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
            <Card icon="route" title="Route timeline">
              <ol className="space-y-3" aria-label="Journey legs">
                {journey.legs.map((leg, i) => (
                  <li key={i} className="space-y-3">
                    <Stop
                      seed={leg.origin.id}
                      time={leg.departure_local ? localTime(leg.departure_local) : "Flexible"}
                      place={leg.origin.name}
                      aside={
                        <span className="hidden items-center gap-2 rounded-2xl bg-card px-3 py-2 text-xs sm:flex">
                          <ModeIcon mode={leg.mode} className="h-5 w-5 text-sky" />
                          <span>
                            <span className="block font-semibold text-ink">{leg.operator}</span>
                            Service {leg.service_code}
                          </span>
                        </span>
                      }
                    />
                    <p className="ml-6 inline-flex items-center gap-2 rounded-full bg-blue/15 px-4 py-1.5 text-sm ring-1 ring-blue/40">
                      <ModeIcon mode={leg.mode} className="h-4 w-4 text-sky" /> On the way ·{" "}
                      <span className="font-semibold text-sky">{formatDuration(leg.duration_minutes)}</span>
                    </p>
                    {i === journey.legs.length - 1 ? (
                      <Stop
                        seed={leg.destination.id}
                        time={leg.arrival_local ? localTime(leg.arrival_local) : "Flexible"}
                        place={leg.destination.name}
                        plus={dayOffset(first.departure_local, leg.arrival_local)}
                      />
                    ) : (
                      journey.transfer_checks?.[i] && <TransferNote check={journey.transfer_checks[i]} />
                    )}
                  </li>
                ))}
              </ol>
            </Card>

            <Card icon="sparkle" title="Trip highlights" gold>
              <ul className="space-y-3 text-sm">
                {highlights.map((h) => (
                  <li key={h} className="flex items-start gap-3">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-success text-white">
                      <Icon name="check" className="h-3.5 w-3.5" strokeWidth={3} />
                    </span>
                    {h}
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          {insight && (
            <section
              aria-label="T-AI insight"
              className="flex flex-wrap items-center gap-4 rounded-3xl bg-gradient-to-r from-violet/25 via-blue/15 to-transparent p-5 shadow-soft ring-1 ring-violet/40"
            >
              <p className="flex items-center gap-2 text-lg font-semibold">
                <Icon name="sparkle" className="h-6 w-6 text-gold" /> T-AI Insight
              </p>
              <p className="min-w-0 flex-1 border-line text-sm sm:border-l sm:pl-4">{insight}</p>
            </section>
          )}

          {journey.notes.length > 0 && (
            <ul className="list-inside list-disc px-1 text-sm text-muted">
              {journey.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}

          <Card icon="clock" title="Data & sources">
            <ul className="space-y-3">
              {journey.legs.map((leg, i) => (
                <LegSource key={i} leg={leg} index={i} now={now} />
              ))}
            </ul>
          </Card>
        </div>

        <aside className="space-y-4 xl:sticky xl:top-24" aria-label="Price and booking">
          <PriceCard journey={journey} />
          <section className="rounded-3xl bg-surface p-5 shadow-soft">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Icon name="shield" className="h-5 w-5 text-sky" /> Provider information
            </h2>
            <ul className="mt-3 space-y-2">
              {providers.map((p) => (
                <li key={p.id} className="rounded-2xl bg-card p-4">
                  <p className="flex items-center gap-2 font-semibold">
                    {p.name}
                    {p.is_demo && <span className="rounded-full bg-gold/15 px-2 py-0.5 text-xs text-gold">Demo</span>}
                  </p>
                  <p className="mt-1 text-sm text-muted">{p.attribution}</p>
                </li>
              ))}
            </ul>
          </section>
          <div className="flex flex-wrap items-center gap-2">
            <SaveJourneyButton journeyId={journey.id} />
            <ShareButton title={`${origin.name} → ${destination.name} · T-Port`} />
          </div>
        </aside>
      </div>
    </article>
  );
}

/** One honest sentence comparing this journey with the other options for the same day. */
async function compareWithSameDay(journey: Journey, o: string, d: string, date: string): Promise<string | null> {
  let res: SearchResponse;
  try {
    res = await serverApi<SearchResponse>(
      `/api/v1/journeys/search?origin=${o}&destination=${d}&date=${date}&max_transfers=2&page_size=50`,
    );
  } catch {
    return null;
  }
  const others = res.items;
  if (others.length < 2) return null;
  const fastest = Math.min(...others.map((j) => j.total_minutes));
  const cheapest = Math.min(...others.map((j) => Number(j.price)));
  const price = Number(journey.price);
  const parts: string[] = [];
  if (journey.total_minutes <= fastest) parts.push(`the fastest of ${others.length} options for this day`);
  else parts.push(`${formatDuration(journey.total_minutes - fastest)} slower than the fastest of ${others.length} options`);
  if (price <= cheapest) parts.push("the cheapest listed fare");
  else parts.push(`${formatMoney(price - cheapest, journey.currency)} more than the cheapest`);
  const direct = journey.transfers === 0 ? ", with no changes" : "";
  return `This journey is ${parts.join(" and ")}${direct}. Compared using the same data sources${res.contains_demo_data ? " (demonstration data)" : ""}.`;
}

function Card({ icon, title, children, gold = false }: { icon: IconName; title: string; children: ReactNode; gold?: boolean }) {
  return (
    <section className="rounded-3xl bg-surface p-5 shadow-soft">
      <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
        <Icon name={icon} className={`h-5 w-5 ${gold ? "text-gold" : "text-sky"}`} /> {title}
      </h2>
      {children}
    </section>
  );
}

function Stat({ icon, label, children, gold = false }: { icon: IconName; label: string; children: ReactNode; gold?: boolean }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-surface p-4 shadow-soft">
      <Icon name={icon} className="h-7 w-7 shrink-0 text-sky" />
      <div className="min-w-0">
        <dt className="text-xs text-muted">{label}</dt>
        <dd className={`truncate font-bold ${gold ? "text-gold" : ""}`}>{children}</dd>
      </div>
    </div>
  );
}

function Stop({ seed, time, place, aside, plus = 0 }: { seed: string; time: string; place: string; aside?: ReactNode; plus?: number }) {
  return (
    <div className="flex items-center gap-3">
      <span aria-hidden="true" className="h-3.5 w-3.5 shrink-0 rounded-full bg-sky ring-4 ring-sky/25" />
      <span aria-hidden="true" className="relative hidden h-14 w-20 shrink-0 overflow-hidden rounded-xl sm:block">
        <PlacePhoto id={seed} decorative sizes="80px" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-xl font-bold text-gold tabular-nums">
          {time}
          {plus > 0 && <sup className="ml-0.5 text-xs">+{plus}</sup>}
        </span>
        <span className="block font-semibold">{place}</span>
      </span>
      {aside}
    </div>
  );
}

function PriceCard({ journey }: { journey: Journey }) {
  return (
    <section aria-labelledby="price-h" className="rounded-3xl bg-surface p-5 shadow-soft">
      <h2 id="price-h" className="flex items-center gap-2 text-lg font-semibold">
        <Icon name="coin" className="h-5 w-5 text-sky" /> Price summary
      </h2>
      <table className="mt-4 w-full text-sm">
        <caption className="sr-only">Fares per leg</caption>
        <thead className="sr-only">
          <tr>
            <th>Fare</th>
            <th>Price</th>
          </tr>
        </thead>
        <tbody>
          {journey.legs.flatMap((leg, i) =>
            leg.fares.map((f) => (
              <tr key={`${i}-${f.name}`}>
                <td className="rounded-l-xl bg-card px-3 py-3">
                  {journey.legs.length > 1 && <span className="text-muted">Leg {i + 1} · </span>}
                  {f.name}
                </td>
                <td className="rounded-r-xl bg-card px-3 py-3 text-right font-semibold text-gold tabular-nums">
                  {f.price_max ? formatPriceRange(f.price, f.price_max, f.currency) : formatMoney(f.price, f.currency)}
                  {f.is_estimate && <span className="ml-1 text-xs font-normal text-muted">(estimate)</span>}
                </td>
              </tr>
            )),
          )}
          <tr>
            <td className="px-3 pt-4 text-base font-semibold">Total price</td>
            <td className="px-3 pt-4 text-right text-2xl font-bold text-gold tabular-nums">
              {formatPriceRange(journey.price, journey.price_max, journey.currency)}
            </td>
          </tr>
        </tbody>
      </table>
      <p className="mt-1 px-3 text-xs text-muted">{PRICE_TYPE_TEXT[journey.price_type].help}</p>
      <div className="mt-4">
        <BookingPanel journey={journey} />
      </div>
    </section>
  );
}

function BookingPanel({ journey }: { journey: Journey }) {
  if (journey.booking_url) {
    return (
      <div className="space-y-3">
        <Link
          href={`/book/${encodeURIComponent(journey.id)}`}
          prefetch={false}
          className="btn-gold flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-4 text-lg font-bold"
        >
          <Icon name="arrowUpRight" /> Go to provider <Icon name="chevronLeft" className="ml-auto h-5 w-5 rotate-180" />
        </Link>
        <p className="flex items-start gap-2 rounded-2xl bg-card px-4 py-3 text-sm text-muted">
          <Icon name="shield" className="mt-0.5 h-4 w-4 shrink-0" />
          You&apos;ll be redirected to the operator&apos;s official website to complete your booking. T-Port does
          not process payments.
        </p>
      </div>
    );
  }
  return (
    <p className="rounded-2xl bg-card px-4 py-3 text-sm text-muted">
      {journey.legs.length > 1 ? (
        <>
          <strong className="text-ink">Each leg is booked separately.</strong>{" "}
          <Link href={`/book/${encodeURIComponent(journey.id)}`} prefetch={false} className="font-medium text-sky underline">
            See booking options for each leg
          </Link>
        </>
      ) : (
        <>
          <strong className="text-ink">Booking not available.</strong>{" "}
          {journey.booking_note ??
            (journey.is_demo ? "Demo journeys cannot be booked." : "This provider has not authorised booking redirects.")}
        </>
      )}
    </p>
  );
}

function LegSource({ leg, index, now }: { leg: Leg; index: number; now: number }) {
  return (
    <li className="rounded-2xl bg-card p-4 text-xs text-muted">
      <p className="mb-2 text-sm font-medium text-ink">
        Leg {index + 1} · {MODE_LABEL[leg.mode]} · {leg.operator}
      </p>
      <span className="mb-2 flex flex-wrap gap-2">
        <FreshnessBadge level={leg.timetable_freshness} label="Timetable" />
        <FreshnessBadge level={leg.price_freshness} label="Price" />
        <PriceTypeBadge type={leg.price_type} />
      </span>
      Source: <span className="text-ink">{leg.provider?.name ?? "Unknown source"}</span>
      {leg.provider?.attribution && <> ({leg.provider.attribution})</>} · updated {timeAgo(leg.retrieved_at, now)} ·
      Retrieved {formatTimestamp(leg.retrieved_at)} · Source updated {formatTimestamp(leg.source_updated_at)} (Tashkent
      time)
    </li>
  );
}

function TransferNote({ check }: { check: TransferCheck }) {
  return (
    <div className="ml-6 rounded-2xl bg-gold/10 px-4 py-2 text-sm text-gold" role="note">
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
