import type { Metadata } from "next";
import { PageBanner } from "@/components/PageBanner";
import { PlaceCard } from "@/components/PlaceCard";
import { RegionCard } from "@/components/RegionCard";
import { EXPLORE_PLACES, EXPLORE_SECTIONS } from "@/lib/explore";
import { UZ_REGIONS } from "@/lib/regions";

export const metadata: Metadata = { title: "Explore Uzbekistan" };

const REGION_SIZES = "(min-width: 1280px) 19rem, (min-width: 1024px) 30vw, (min-width: 640px) 45vw, 100vw";
const PLACE_SIZES = "(min-width: 1280px) 15rem, (min-width: 1024px) 22vw, (min-width: 640px) 30vw, 50vw";

export default function ExplorePage() {
  return (
    <div className="mx-auto max-w-[80rem] space-y-8 px-3 py-4 sm:px-6 lg:px-0 lg:py-0">
      <PageBanner
        icon="compass"
        title="Explore"
        accent="Uzbekistan"
        subtitle="14 regions, 28 places worth the journey, and how to get there."
      />

      <section aria-labelledby="regions-h" className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2 px-1">
          <h2 id="regions-h" className="text-xl font-semibold">
            Uzbekistan&apos;s 14 regions
          </h2>
          <p className="text-sm text-muted">Each region has a landmark and a destination to read about.</p>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {UZ_REGIONS.map((r) => (
            <li key={r.key}>
              <RegionCard region={r} sizes={REGION_SIZES} />
            </li>
          ))}
        </ul>
      </section>

      {EXPLORE_SECTIONS.map(({ kind, title }) => (
        <section key={kind} aria-labelledby={`explore-${kind}`} className="space-y-3">
          <h2 id={`explore-${kind}`} className="px-1 text-xl font-semibold">
            {title}
          </h2>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {EXPLORE_PLACES.filter((p) => p.kind === kind).map((p) => (
              <li key={p.key}>
                <PlaceCard place={p} sizes={PLACE_SIZES} />
              </li>
            ))}
          </ul>
        </section>
      ))}

      <p className="rounded-2xl bg-surface p-4 text-sm text-muted shadow-soft">
        All pictures on these pages are AI-generated illustrations made for T-Port, not photos, so real places look
        different. Place information comes from the sources listed on each place; check opening times, tickets and
        access with the place itself before you travel.
      </p>
    </div>
  );
}
