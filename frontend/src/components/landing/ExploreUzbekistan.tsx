import Image from "next/image";
import Link from "next/link";
import { Icon } from "../Icons";
import { T } from "../T";
import { REGION_TEXT } from "@/lib/i18n";
import { PLACE_IMAGE } from "@/lib/explore";
import { regionHref, regionPlaces, UZ_REGIONS } from "@/lib/regions";

/** The 14 regions, each with its destination illustration (shown whole) and its two verified places. */
export function ExploreUzbekistan() {
  return (
    <section id="explore" aria-labelledby="explore-h" className="scroll-mt-28">
      <div className="reveal mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="explore-h" className="text-3xl font-extrabold tracking-tight sm:text-5xl">
            <T k="explore.title" />
          </h2>
          <p className="mt-3 max-w-xl text-base text-muted sm:text-lg">
            <T k="explore.sub" />
          </p>
        </div>
        <Link href="/explore" className="inline-flex items-center gap-1.5 text-sm font-semibold text-gold hover:underline">
          <T k="explore.all" /> <Icon name="arrowRight" className="h-4 w-4" />
        </Link>
      </div>
      <ul className="grid grid-cols-1 gap-4 min-[480px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {UZ_REGIONS.map((r) => {
          const text = REGION_TEXT[r.key];
          const cover = regionPlaces(r.key).find((p) => p.kind === "destination")!;
          return (
            <li key={r.key} className="reveal">
              <Link
                href={regionHref(r.key)}
                className="lift group relative block overflow-hidden rounded-3xl shadow-soft ring-1 ring-line focus-visible:outline-2 focus-visible:outline-sky"
              >
                <Image
                  src={cover.image}
                  alt=""
                  width={PLACE_IMAGE.width}
                  height={PLACE_IMAGE.height}
                  sizes="(min-width: 1280px) 22rem, (min-width: 1024px) 30vw, (min-width: 480px) 46vw, 92vw"
                  className="h-auto w-full transition duration-700 group-hover:scale-[1.04]"
                />
                <span aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-[#050b18] via-[#050b18]/40 to-transparent" />
                <span className="absolute left-3 top-3 rounded-full bg-black/50 px-2.5 py-1 text-[11px] font-medium text-white backdrop-blur">
                  <T k="explore.illus" />
                </span>
                <span className="absolute inset-x-0 bottom-0 flex items-end gap-3 p-4 text-white">
                  <span className="min-w-0 flex-1">
                    <span className="block text-lg font-bold leading-tight">
                      <T tr={text.name} />
                    </span>
                    <span className="mt-1 block text-sm leading-snug text-white/80">
                      <T tr={text.desc} />
                    </span>
                  </span>
                  <span
                    aria-hidden="true"
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white/15 ring-1 ring-white/40 backdrop-blur transition group-hover:bg-blue"
                  >
                    <Icon name="arrowUpRight" className="h-4 w-4" />
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
