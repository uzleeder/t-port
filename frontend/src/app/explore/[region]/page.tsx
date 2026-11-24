import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AuraLink } from "@/components/AuraLink";
import { Icon } from "@/components/Icons";
import { PageBanner } from "@/components/PageBanner";
import { PLACE_IMAGE, placeSearchHref, type ExplorePlace } from "@/lib/explore";
import { UZ_REGIONS, regionByKey, regionHref, regionPlaces } from "@/lib/regions";

export function generateStaticParams() {
  return UZ_REGIONS.map((r) => ({ region: r.key }));
}

export async function generateMetadata({ params }: PageProps<"/explore/[region]">): Promise<Metadata> {
  const r = regionByKey((await params).region);
  return { title: r ? `${r.name} · Explore` : "Explore" };
}

export default async function RegionPage({ params }: PageProps<"/explore/[region]">) {
  const { region: key } = await params;
  const r = regionByKey(key);
  if (!r) notFound();
  const places = regionPlaces(r.key);
  const i = UZ_REGIONS.findIndex((x) => x.key === r.key);
  const prev = UZ_REGIONS[(i - 1 + UZ_REGIONS.length) % UZ_REGIONS.length];
  const next = UZ_REGIONS[(i + 1) % UZ_REGIONS.length];

  return (
    <div className="mx-auto max-w-[80rem] space-y-6 px-3 py-4 sm:px-6 lg:px-0 lg:py-0">
      <PageBanner
        title={r.name}
        subtitle={r.nameUz}
        icon={r.icon}
        back={{ href: "/explore", label: "Back to Explore" }}
      />

      {places.map((p) => (
        <PlaceDetail key={p.key} place={p} regionLabel={r.region} />
      ))}

      <nav aria-label="Other regions" className="flex flex-wrap justify-between gap-3">
        <Link href={regionHref(prev.key)} className="inline-flex items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm shadow-soft hover:text-sky">
          <Icon name="chevronLeft" className="h-4 w-4" /> {prev.name}
        </Link>
        <Link href="/explore" className="inline-flex items-center rounded-full bg-surface px-4 py-2 text-sm shadow-soft hover:text-sky">
          All regions
        </Link>
        <Link href={regionHref(next.key)} className="inline-flex items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm shadow-soft hover:text-sky">
          {next.name} <Icon name="arrowRight" className="h-4 w-4" />
        </Link>
      </nav>
    </div>
  );
}

function PlaceDetail({ place: p, regionLabel }: { place: ExplorePlace; regionLabel: string }) {
  // "Bukhara · Old City" is in Bukhara; "Tashkent Region · Bostanliq" is not in Tashkent.
  const nearest = !p.area.split(" · ").includes(p.cityName);
  return (
    <article id={p.key} aria-labelledby={`${p.key}-h`} className="scroll-mt-24 rounded-3xl bg-surface p-3 shadow-soft sm:p-4">
      <div className="grid items-start gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <figure className="relative">
          <Image
            src={p.image}
            alt={`Illustration of ${p.name}`}
            width={PLACE_IMAGE.width}
            height={PLACE_IMAGE.height}
            sizes="(min-width: 1280px) 38rem, (min-width: 768px) 45vw, 100vw"
            className="h-auto w-full rounded-[1.5rem]"
          />
          <figcaption className="absolute left-3 top-3 rounded-full bg-black/55 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur">
            AI illustration
          </figcaption>
        </figure>
        <div className="space-y-4 px-1 pb-2 md:pt-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-sky">
              {p.kind === "landmark" ? "Landmark" : "Destination"} · {p.category}
            </p>
            <h2 id={`${p.key}-h`} className="mt-1 text-2xl font-bold sm:text-3xl">
              {p.name}
            </h2>
            <p className="text-sm text-muted">
              {p.nameUz !== p.name && <span lang="uz">{p.nameUz} · </span>}
              {p.area}
            </p>
          </div>
          <Para title="History & significance">{p.history}</Para>
          <Para title="What to see">{p.see}</Para>
          <Para title="Plan your visit">{p.tip}</Para>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
            <Link
              href={placeSearchHref(p)}
              className="inline-flex items-center gap-1.5 rounded-full bg-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-hover"
            >
              Journeys to {p.cityName}
              <Icon name="arrowRight" className="h-4 w-4" />
            </Link>
            <Link
              href={`/planner?ask=${encodeURIComponent(`Tell me about ${p.name}`)}`}
              className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium ring-1 ring-violet/50 hover:bg-violet/10"
            >
              <Icon name="ai" className="h-4 w-4 text-gold" /> Ask T-AI
            </Link>
            <AuraLink place={regionLabel.replace(/^Republic of /, "").replace(/ (Region|City)$/, "")} region={regionLabel} />
          </div>
          {nearest && (
            <p className="text-xs text-muted">
              {p.cityName} is the nearest city T-Port finds journeys to; plan the last part of the trip separately.
            </p>
          )}
          <div className="border-t border-line pt-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Sources</h3>
            <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {p.sources.map((s) => (
                <li key={s.url}>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-sky underline">
                    {s.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </article>
  );
}

function Para({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-0.5 text-sm leading-relaxed text-muted">{children}</p>
    </section>
  );
}
