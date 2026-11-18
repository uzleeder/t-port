import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { PRICE_TYPE_TEXT } from "@/components/Badges";
import { StateMessage } from "@/components/Notices";
import { ApiError } from "@/lib/api";
import { formatPriceRange, formatTimestamp } from "@/lib/format";
import { serverApi } from "@/lib/server-api";
import type { BookingInfo } from "@/lib/types";

export const metadata: Metadata = { title: "Book with the operator", robots: { index: false } };

export default function BookPage({ params }: PageProps<"/book/[id]">) {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <Suspense
        fallback={<div role="status" className="h-64 animate-pulse rounded-2xl bg-surface" aria-label="Loading booking details" />}
      >
        <Handoff params={params} />
      </Suspense>
    </div>
  );
}

async function Handoff({ params }: { params: PageProps<"/book/[id]">["params"] }) {
  const journeyId = decodeURIComponent((await params).id);
  const back = `/journeys/${encodeURIComponent(journeyId)}`;
  let info: BookingInfo;
  try {
    info = await serverApi<BookingInfo>(`/api/v1/journeys/${encodeURIComponent(journeyId)}/booking`);
  } catch (e) {
    const err = e instanceof ApiError ? e : null;
    return (
      <StateMessage
        tone="error"
        title={err?.status === 404 ? "Journey not available" : "Booking details unavailable"}
        action={{ href: "/search", label: "Start a new search" }}
      >
        <p>{err?.message ?? "Please try again."}</p>
      </StateMessage>
    );
  }

  if (info.leg_journey_ids.length > 0) {
    return (
      <section className="space-y-4">
        <Link href={back} className="text-sm text-blue hover:underline">← Back to the journey</Link>
        <h1 className="text-2xl font-bold">Book each leg separately</h1>
        <p className="text-muted">
          This journey combines {info.leg_journey_ids.length} services. T-Port cannot book them together, and a
          missed connection is not protected by any operator. Check each leg&apos;s booking options:
        </p>
        <ol className="list-inside list-decimal space-y-2">
          {info.leg_journey_ids.map((id, i) => (
            <li key={id}>
              <Link href={`/book/${encodeURIComponent(id)}`} prefetch={false} className="text-blue hover:underline">
                Leg {i + 1} booking options
              </Link>
            </li>
          ))}
        </ol>
      </section>
    );
  }

  if (!info.bookable || !info.provider || !info.booking_host) {
    return (
      <StateMessage title="Booking not available" action={{ href: back, label: "Back to the journey" }}>
        <p>{info.reason ?? "This journey can't be booked through T-Port."}</p>
      </StateMessage>
    );
  }

  return (
    <section aria-labelledby="handoff-h" className="space-y-5">
      <Link href={back} className="text-sm text-blue hover:underline">← Back to the journey</Link>
      <h1 id="handoff-h" className="text-2xl font-bold">You&apos;re leaving T-Port</h1>
      <p>
        Booking happens on <strong>{info.provider.name}</strong>&apos;s own website,{" "}
        <strong className="break-all">{info.booking_host}</strong>. T-Port does not sell tickets, take payments or
        see what you book.
      </p>
      <dl className="grid gap-3 rounded-2xl border border-line bg-surface p-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted">Price shown on T-Port</dt>
          <dd className="mt-1 text-lg font-semibold text-gold tabular-nums">
            {formatPriceRange(info.price, info.price_max, info.currency)}
          </dd>
          <dd className="text-xs text-muted">{PRICE_TYPE_TEXT[info.price_type].label}</dd>
        </div>
        <div>
          <dt className="text-muted">Price data retrieved</dt>
          <dd className="mt-1">{formatTimestamp(info.price_retrieved_at)}</dd>
        </div>
      </dl>
      <ul className="list-inside list-disc space-y-1 text-sm text-muted">
        <li>The operator sets the final price and availability; it may differ from what T-Port showed.</li>
        <li>Their terms, refunds and support apply. Contact the operator about your booking.</li>
        <li>T-Port passes no personal information to the operator; it only counts how many people continue.</li>
      </ul>
      <p className="text-xs text-muted">{info.provider.attribution}</p>
      <div className="flex flex-wrap items-center gap-3">
        {/* A plain link (not prefetched): following it is the only thing that counts as a hand-off. */}
        <a
          href={`/api/v1/journeys/${encodeURIComponent(journeyId)}/book`}
          rel="noopener noreferrer nofollow"
          className="rounded-xl bg-blue px-5 py-3 font-semibold text-white hover:bg-blue-hover"
        >
          Continue to {info.booking_host} ↗
        </a>
        <Link href={back} className="text-sm text-muted hover:text-ink">
          Cancel
        </Link>
      </div>
    </section>
  );
}
