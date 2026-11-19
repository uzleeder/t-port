import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { PageBanner } from "@/components/PageBanner";
import { PHOTOS } from "@/lib/photos";
import { AURA_HOME, AURA_REGIONS } from "@/lib/aura";

export const metadata: Metadata = { title: "Photo credits" };

export default function CreditsPage() {
  return (
    <div className="mx-auto max-w-[80rem] space-y-5 px-3 py-4 sm:px-6 lg:px-0 lg:py-0">
      <PageBanner
        icon="sparkle"
        title="Photo credits"
        subtitle="The photos on T-Port are openly licensed. Thank you to the photographers."
      />
      <p className="rounded-2xl bg-surface p-4 text-sm text-muted shadow-soft">
        All photos come from Wikimedia Commons. T-Port shows them resized and cropped; no other changes were
        made. Photos under a CC BY-SA licence remain available under that same licence. Photos are decorative
        and do not show T-Port partners or real-time conditions.
      </p>
      <p className="rounded-2xl bg-surface p-4 text-sm text-muted shadow-soft">
        The pictures on the{" "}
        <Link href="/explore" className="text-sky underline">
          Explore
        </Link>{" "}
        page are AI-generated illustrations made for T-Port, not photos, and are labelled as such.
      </p>
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {PHOTOS.map((p) => (
          <li key={p.key} className="overflow-hidden rounded-3xl bg-surface shadow-soft">
            <div className="relative h-44">
              <Image src={p.src} alt={p.place} fill sizes="(min-width: 1280px) 30vw, (min-width: 640px) 45vw, 100vw" className="object-cover" />
            </div>
            <div className="space-y-1 p-4 text-sm">
              <p className="font-semibold">{p.place}</p>
              <p className="text-muted">
                Photo by {p.author} ·{" "}
                <a href={p.licenseUrl} rel="license noopener noreferrer" target="_blank" className="text-sky underline">
                  {p.license}
                </a>
              </p>
              <a href={p.source} rel="noopener noreferrer" target="_blank" className="text-sky underline">
                Source on Wikimedia Commons
              </a>
            </div>
          </li>
        ))}
      </ul>
      <section aria-labelledby="aura-h" className="rounded-3xl bg-surface p-5 shadow-soft">
        <h2 id="aura-h" className="text-lg font-semibold">More photos of Uzbekistan</h2>
        <p className="mt-1 text-sm text-muted">
          <a href={AURA_HOME} target="_blank" rel="noopener noreferrer" className="text-sky underline">
            AURA
          </a>{" "}
          is Uzbekistan&apos;s state photo and video archive (in Uzbek). These links open its gallery for each region.
          AURA&apos;s photos belong to AURA and are not shown on T-Port.
        </p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {AURA_REGIONS.map((r) => (
            <li key={r.href}>
              <a
                href={r.href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex rounded-full bg-surface-2 px-3 py-1.5 text-sm ring-1 ring-line hover:text-sky"
              >
                {r.label}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
