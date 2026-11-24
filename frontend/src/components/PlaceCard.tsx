import Image from "next/image";
import Link from "next/link";
import { PLACE_IMAGE, type ExplorePlace } from "@/lib/explore";
import { placeHref, regionByKey } from "@/lib/regions";

/** Compact place card for the Explore lists: whole picture, name, where it is. */
export function PlaceCard({ place: p, sizes }: { place: ExplorePlace; sizes: string }) {
  return (
    <Link
      href={placeHref(p)}
      className="group flex h-full flex-col overflow-hidden rounded-3xl bg-surface shadow-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky"
    >
      <span className="block p-2 pb-0">
        <Image
          src={p.image}
          alt=""
          width={PLACE_IMAGE.width}
          height={PLACE_IMAGE.height}
          sizes={sizes}
          className="h-auto w-full rounded-[1.25rem]"
        />
      </span>
      <span className="block p-3.5">
        <span className="block text-[11px] font-semibold uppercase tracking-wide text-sky">{p.category}</span>
        <span className="mt-0.5 block font-semibold leading-tight group-hover:underline">{p.name}</span>
        <span className="block text-xs text-muted">
          {p.area}
          <span className="sr-only">, {regionByKey(p.regionKey)?.name}</span>
        </span>
      </span>
    </Link>
  );
}
