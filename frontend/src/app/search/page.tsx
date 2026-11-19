import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";
import { CompareCount, CompareTray } from "@/components/Compare";
import { Icon } from "@/components/Icons";
import { PageBanner } from "@/components/PageBanner";
import { SearchSummary } from "@/components/SearchSummary";
import { JourneyRow } from "@/components/JourneyRow";
import { DemoNotice, LabelsHelp, StateMessage } from "@/components/Notices";
import { RetryButton } from "@/components/RetryButton";
import { ResultsControls, ResultsTabs } from "@/components/ResultsControls";
import { SearchForm } from "@/components/SearchForm";
import { ApiError } from "@/lib/api";
import { requestTime, serverApi } from "@/lib/server-api";
import {
  buildSearchQuery,
  timeAgo,
  formatDateLong,
  formatTimestamp,
  parseSearchParams,
  type SearchParams,
} from "@/lib/format";
import type { Location, SearchResponse } from "@/lib/types";

export const metadata: Metadata = { title: "Search journeys" };

export default function SearchPage({ searchParams }: PageProps<"/search">) {
  return (
    <div className="mx-auto max-w-[80rem] space-y-5 px-3 py-4 sm:px-6 lg:px-0 lg:py-0">
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
  // Fault simulation is honoured by the API only where it is enabled (never in production).
  const simulate = typeof raw.simulate === "string" ? `&simulate=${encodeURIComponent(raw.simulate)}` : "";
  const now = await requestTime();
  try {
    data = await serverApi<SearchResponse>(
      `/api/v1/journeys/search?${buildSearchQuery(params)}&page_size=20${simulate}`,
    );
  } catch (e) {
    error = e instanceof ApiError ? e : new ApiError(500, "unknown", "Search failed.");
  }

  const origin = data?.query.origin ?? (await lookup(params.origin));
  const destination = data?.query.destination ?? (await lookup(params.destination));

  return (
    <div className="space-y-6">
      <PageBanner
        title="Search"
        accent="Results"
        subtitleAs="h2"
        subtitle={`Compare travel options from ${origin?.name ?? params.origin} to ${destination?.name ?? params.destination}`}
      />
      <SearchSummary
        from={origin?.name ?? params.origin}
        to={destination?.name ?? params.destination}
        date={formatDateLong(params.date)}
      >
        <SearchForm
          compact
          key={buildSearchQuery(params)}
          initialOrigin={origin}
          initialDestination={destination}
          initialDate={params.date}
          initialModes={params.modes}
        />
      </SearchSummary>
      {error ? <SearchError error={error} /> : data && <ResultsBody data={data} params={params} now={now} />}
      <CompareTray />
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
      {(error.status >= 500 || error.status === 0 || error.status === 429) && (
        <div className="mt-4">
          <RetryButton />
        </div>
      )}
    </StateMessage>
  );
}

function hasFilters(p: SearchParams): boolean {
  return Boolean(p.arriveBefore || p.maxPrice || p.departAfter || p.departBefore || p.maxTransfers === 0);
}

function ResultsBody({ data, params, now }: { data: SearchResponse; params: SearchParams; now: number }) {
  const failed = data.sources.filter((s) => !s.ok);
  const { summary, query } = data;
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  const counts = summary.count_by_mode as Record<string, number>;
  const highlight = (id: string) =>
    [
      id === summary.cheapest_id && "Cheapest",
      id === summary.fastest_id && "Fastest",
      id === summary.earliest_id && "Earliest",
    ].filter(Boolean) as string[];
  const okSources = data.sources.filter((s) => s.ok);
  const allFresh = okSources.length > 0 && okSources.every((s) => s.freshness === "fresh");
  const good = allFresh && !data.contains_demo_data; // green only for current, real data
  const newest = okSources.map((s) => s.retrieved_at).filter(Boolean).sort().at(-1) ?? null;

  return (
    <>

      <div
        role="status"
        className={`flex flex-wrap items-center gap-x-6 gap-y-2 rounded-2xl px-4 py-3 text-sm ring-1 ${
          good ? "bg-success/5 ring-success/30" : "bg-gold/5 ring-gold/30"
        }`}
      >
        <span className="flex items-center gap-2 font-semibold">
          <span className={`h-2.5 w-2.5 rounded-full ${good ? "bg-success" : "bg-gold"}`} />
          {data.contains_demo_data ? "Demo data" : allFresh ? "Data current" : "Some data may be outdated"}
        </span>
        <span className="text-muted">
          {okSources.length} source{okSources.length === 1 ? "" : "s"} responded
          {failed.length ? `, ${failed.length} unavailable` : ""}
        </span>
        <span className="text-muted">Prices and times shown exactly as each source reports them</span>
        {newest && <span className="ml-auto text-muted">Last updated {timeAgo(newest, now) ?? formatTimestamp(newest)}</span>}
      </div>

      {data.contains_demo_data && <DemoNotice />}
      {failed.length > 0 && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl border border-danger/50 px-4 py-3 text-sm">
          <p className="flex-1 text-danger">
            <strong>Some sources didn&apos;t respond:</strong> {failed.map((s) => s.provider.name).join(", ")}.
            Results from them are missing, so this list may be incomplete.
          </p>
          <RetryButton label="Retry search" />
        </div>
      )}
      {data.warnings
        .filter((w) => !w.includes("temporarily unavailable"))
        .map((w) => (
          <p key={w} role="status" className="rounded-2xl bg-gold/10 px-4 py-2 text-sm text-gold">
            {w}
          </p>
        ))}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[16rem_minmax(0,1fr)] xl:items-start">
        <ResultsControls params={params} counts={counts} />
        <div className="space-y-4">
          <ResultsTabs params={params} counts={counts} total={data.total} />
          <LabelsHelp />
          {data.total === 0 ? (
            <StateMessage title={hasFilters(params) ? "No journeys match your filters" : "No journeys found"}>
              <p>
                The current dataset has no{" "}
                {query.modes.length ? `${query.modes.join(" / ")} ` : ""}services from{" "}
                {query.origin.name} to {query.destination.name} on {formatDateLong(query.date)}
                {hasFilters(params) ? " that fit the changes, arrival time or budget you set" : ""}.
                Try another date, include more transport modes, allow more changes, or relax a filter.
              </p>
            </StateMessage>
          ) : (
            <ol className="space-y-4 pt-2" aria-label="Journeys">
              {data.items.map((j, i) => (
                <li key={j.id}>
                  <JourneyRow
                    journey={j}
                    highlights={highlight(j.id)}
                    now={now}
                    recommended={i === 0 && data.page === 1 && query.sort === "recommended"}
                  />
                </li>
              ))}
            </ol>
          )}
          {totalPages > 1 && (
            <nav aria-label="Pagination" className="flex items-center justify-center gap-4 text-sm">
              {data.page > 1 && (
                <a
                  className="rounded-full border border-line bg-card px-3 py-2 hover:border-blue"
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
                  className="rounded-full border border-line bg-card px-3 py-2 hover:border-blue"
                  href={`/search?${buildSearchQuery({ ...params, page: data.page + 1 })}`}
                >
                  Next
                </a>
              )}
            </nav>
          )}

          <div className="flex flex-wrap items-center gap-4 rounded-3xl bg-surface p-5 shadow-soft">
            <Icon name="route" className="h-9 w-9 text-gold" />
            <div className="min-w-0 flex-1">
              <p className="text-lg font-semibold">Compare &amp; choose</p>
              <p className="text-sm text-muted">Tick Compare on up to 4 options to compare price, time and changes.</p>
            </div>
            <CompareCount label="Compare selected" big />
          </div>
          <section aria-labelledby="sources" className="rounded-3xl bg-surface p-5 text-sm text-muted shadow-soft">
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
        </div>
      </div>
    </>
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
