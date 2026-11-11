import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";
import { JourneyCard } from "@/components/JourneyCard";
import { DemoNotice, StateMessage } from "@/components/Notices";
import { ResultsControls } from "@/components/ResultsControls";
import { SearchForm } from "@/components/SearchForm";
import { ApiError } from "@/lib/api";
import { serverApi } from "@/lib/server-api";
import {
  buildSearchQuery,
  formatDateLong,
  formatDuration,
  formatMoney,
  formatTimestamp,
  parseSearchParams,
  type SearchParams,
} from "@/lib/format";
import type { Location, SearchResponse } from "@/lib/types";

export const metadata: Metadata = { title: "Search journeys" };

export default function SearchPage({ searchParams }: PageProps<"/search">) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <Suspense fallback={<ResultsSkeleton />}>
        <Results searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Results({ searchParams }: { searchParams: PageProps<"/search">["searchParams"] }) {
  const raw = await searchParams;
  await connection(); // a missing date defaults to "tomorrow", which depends on the request time
  const params = parseSearchParams(raw);
  if (!params) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Search journeys</h1>
        <SearchForm />
        <DemoNotice />
      </div>
    );
  }

  let data: SearchResponse | null = null;
  let error: ApiError | null = null;
  try {
    data = await serverApi<SearchResponse>(
      `/api/v1/journeys/search?${buildSearchQuery(params)}&page_size=20`,
    );
  } catch (e) {
    error = e instanceof ApiError ? e : new ApiError(500, "unknown", "Search failed.");
  }

  const origin = data?.query.origin ?? (await lookup(params.origin));
  const destination = data?.query.destination ?? (await lookup(params.destination));

  return (
    <div className="space-y-6">
      <SearchForm
        compact
        key={buildSearchQuery(params)}
        initialOrigin={origin}
        initialDestination={destination}
        initialDate={params.date}
        initialModes={params.modes}
      />
      {error ? <SearchError error={error} /> : data && <ResultsBody data={data} params={params} />}
    </div>
  );
}

async function lookup(id: string): Promise<Location | null> {
  try {
    return await serverApi<Location>(`/api/v1/locations/${encodeURIComponent(id)}`);
  } catch {
    return null;
  }
}

function SearchError({ error }: { error: ApiError }) {
  const detail = error.details.map((d) => d.message).join(" ");
  const title =
    error.status === 404
      ? "We don't recognise that place"
      : error.status === 422
        ? "Please check your search"
        : error.status === 429
          ? "Too many searches"
          : "Search is unavailable right now";
  return (
    <StateMessage title={title} tone="error">
      <p>
        {error.message} {detail}
      </p>
    </StateMessage>
  );
}

function ResultsBody({ data, params }: { data: SearchResponse; params: SearchParams }) {
  const { summary, query } = data;
  const byId = new Map(data.items.map((j) => [j.id, j]));
  const fastest = summary.fastest_id ? byId.get(summary.fastest_id) : undefined;
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  const highlight = (id: string) =>
    [
      id === summary.cheapest_id && "Cheapest",
      id === summary.fastest_id && "Fastest",
      id === summary.earliest_id && "Earliest",
    ].filter(Boolean) as string[];

  return (
    <>
      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">
          {query.origin.name} <span className="text-muted">→</span> {query.destination.name}
        </h1>
        <p className="mt-1 text-muted">{formatDateLong(query.date)}</p>
      </div>

      {data.contains_demo_data && <DemoNotice />}
      {data.warnings.map((w) => (
        <p key={w} role="status" className="rounded-xl border border-danger/50 px-4 py-2 text-sm text-danger">
          {w}
        </p>
      ))}

      <ResultsControls params={params} />

      {data.total === 0 ? (
        <StateMessage title="No direct journeys found">
          <p>
            The current dataset has no{" "}
            {query.modes.length ? `${query.modes.join(" / ")} ` : ""}services from{" "}
            {query.origin.name} to {query.destination.name} on {formatDateLong(query.date)}.
            Try another date, include more transport modes, or travel via a nearby city.
          </p>
        </StateMessage>
      ) : (
        <>
          <dl className="grid gap-3 sm:grid-cols-3" aria-label="Comparison summary">
            <Stat label="Cheapest">
              {summary.min_price && formatMoney(summary.min_price, data.items[0]?.currency ?? "UZS")}
            </Stat>
            <Stat label="Fastest">
              {fastest
                ? formatDuration(fastest.total_minutes)
                : summary.fastest_id
                  ? "See results"
                  : "—"}
            </Stat>
            <Stat label="Options">
              {data.total} ·{" "}
              {Object.entries(summary.count_by_mode)
                .map(([m, n]) => `${n} ${m}`)
                .join(", ")}
            </Stat>
          </dl>
          <ol className="space-y-3" aria-label="Journeys">
            {data.items.map((j) => (
              <li key={j.id}>
                <JourneyCard journey={j} highlights={highlight(j.id)} />
              </li>
            ))}
          </ol>
          {totalPages > 1 && (
            <nav aria-label="Pagination" className="flex items-center justify-center gap-4 text-sm">
              {data.page > 1 && (
                <a
                  className="rounded-lg border border-line px-3 py-2 hover:border-blue"
                  href={`/search?${buildSearchQuery({ ...params, page: data.page - 1 })}`}
                >
                  Previous
                </a>
              )}
              <span className="text-muted">
                Page {data.page} of {totalPages}
              </span>
              {data.page < totalPages && (
                <a
                  className="rounded-lg border border-line px-3 py-2 hover:border-blue"
                  href={`/search?${buildSearchQuery({ ...params, page: data.page + 1 })}`}
                >
                  Next
                </a>
              )}
            </nav>
          )}
        </>
      )}

      <section aria-labelledby="sources" className="rounded-2xl border border-line p-4 text-sm text-muted">
        <h2 id="sources" className="font-semibold text-ink">
          Sources &amp; data freshness
        </h2>
        <ul className="mt-2 space-y-1">
          {data.sources.map((s) => (
            <li key={s.provider.id}>
              <span className="text-ink">{s.provider.name}</span>
              {s.provider.is_demo && " (demo)"} —{" "}
              {s.ok
                ? `retrieved ${formatTimestamp(s.retrieved_at)} (Tashkent time), ${s.freshness ?? "unknown"}`
                : "unavailable"}
              . {s.provider.attribution}
            </li>
          ))}
          {data.sources.length === 0 && <li>No data source covers this route yet.</li>}
        </ul>
        <p className="mt-2">
          Hidden from results: {data.excluded.already_departed} already departed,{" "}
          {data.excluded.missing_offers} without a fare, {data.excluded.expired_data} with
          out-of-date data.
        </p>
      </section>
    </>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3">
      <dt className="text-xs uppercase tracking-wider text-muted">{label}</dt>
      <dd className="mt-1 font-semibold">{children}</dd>
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div role="status" aria-label="Loading journeys" className="space-y-3">
      <div className="h-36 animate-pulse rounded-2xl bg-surface" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-28 animate-pulse rounded-2xl bg-surface/70" />
      ))}
      <span className="sr-only">Searching journeys…</span>
    </div>
  );
}
