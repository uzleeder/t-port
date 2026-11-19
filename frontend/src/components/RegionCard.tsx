import Image from "next/image";
import Link from "next/link";
import { Icon } from "./Icons";
import { PLACE_IMAGE } from "@/lib/explore";
import { regionHref, regionPlaces, type UzRegion } from "@/lib/regions";

/** Region tile: the region's destination picture shown whole, its name and its two places. */
export function RegionCard({ region: r, sizes }: { region: UzRegion; sizes: string }) {
  const places = regionPlaces(r.key);
  const cover = places.find((p) => p.kind === "destination") ?? places[0];
  return (
    <Link
      href={regionHref(r.key)}
      className="group flex h-full flex-col overflow-hidden rounded-3xl bg-surface shadow-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
    >
      <span className="relative block p-2 pb-0">
        <Image
          src={cover.image}
          alt=""
          width={PLACE_IMAGE.width}
          height={PLACE_IMAGE.height}
          sizes={sizes}
          className="h-auto w-full rounded-[1.25rem]"
        />
        <span className="absolute left-4 top-4 rounded-full bg-black/55 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur">
          AI illustration
        </span>
      </span>
      <span className="flex flex-1 items-start gap-3 p-4">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-blue/15 text-sky ring-1 ring-blue/30">
          <Icon name={r.icon} className="h-5 w-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold leading-tight">{r.name}</span>
          <span lang="uz" className="block text-xs text-muted">
            {r.nameUz}
          </span>
          <span className="mt-1.5 block text-sm text-muted">{places.map((p) => p.name).join(" · ")}</span>
        </span>
        <span
          aria-hidden="true"
          className="grid h-8 w-8 shrink-0 place-items-center rounded-full ring-1 ring-line transition group-hover:bg-blue group-hover:text-white group-hover:ring-blue"
        >
          <Icon name="arrowRight" className="h-4 w-4" />
        </span>
      </span>
    </Link>
  );
}
