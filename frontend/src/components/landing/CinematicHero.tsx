import Image from "next/image";
import Link from "next/link";
import { Icon } from "../Icons";
import { T } from "../T";

/*
 * Artistic montage of the place-card illustrations, blended left to right into one panorama:
 * Charvak mountains, modern Tashkent, Samarkand's Registan, Bukhara's Kalon minaret, Khiva's walls.
 * Phones show the middle three. It is an illustration, not a real view of one place.
 */
const PIECES: { src: string; className: string; position?: string }[] = [
  { src: "/images/explore/tashkent-region-landmark.webp", className: "hidden lg:block" },
  { src: "/images/explore/tashkent-city-landmark.webp", className: "hidden md:block" },
  { src: "/images/explore/samarkand-landmark.webp", className: "", position: "object-[50%_70%]" },
  { src: "/images/explore/bukhara-landmark.webp", className: "" },
  { src: "/images/explore/khorezm-destination.webp", className: "hidden sm:block" },
];

export function CinematicHero() {
  return (
    <section
      aria-labelledby="hero-h"
      className="bleed relative isolate -mt-[4.25rem] flex min-h-[min(100svh,54rem)] flex-col justify-end overflow-hidden lg:-mt-[5.75rem] lg:min-h-[100svh]"
    >
      {/* montage */}
      <div aria-hidden="true" className="montage parallax l-fade-bg absolute inset-0 -z-20 flex">
        {PIECES.map((p, i) => (
          <div key={p.src} className={`montage-piece relative shrink-0 ${p.className}`}>
            <Image
              src={p.src}
              alt=""
              fill
              sizes="(min-width: 1024px) 120vh, 110vh"
              loading={i === 2 ? "eager" : i === 3 ? "eager" : "lazy"}
              fetchPriority={i === 2 ? "high" : "auto"}
              className={`object-cover ${p.position ?? ""}`}
            />
          </div>
        ))}
      </div>
      {/* overlays for contrast */}
      <div aria-hidden="true" className="l-fade-y absolute inset-0 -z-10" />
      <div aria-hidden="true" className="l-fade-x absolute inset-0 -z-10" />
      <TransportLines />

      <div className="mx-auto w-full max-w-[94rem] px-5 pb-40 pt-32 sm:px-10 sm:pb-48 lg:pb-60">
        <div className="l-text max-w-4xl">
          <p className="l-eyebrow text-xs font-semibold uppercase tracking-[0.32em]">
            <T k="hero.eyebrow" />
          </p>
          <h1 id="hero-h" className="mt-5 text-[2.6rem] font-extrabold leading-[1.04] tracking-tight sm:text-6xl xl:text-7xl">
            <span className="block">
              <T k="hero.line1" />
            </span>
            <span className="l-grad-text block pb-1">
              <T k="hero.line2" />
            </span>
          </h1>
          <p className="l-sub mt-6 max-w-xl text-base leading-relaxed sm:text-lg">
            <T k="hero.desc" />
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="#explore"
              className="inline-flex items-center gap-2 rounded-full bg-blue px-6 py-3.5 font-semibold text-white transition hover:bg-blue-hover"
            >
              <T k="hero.cta" /> <Icon name="arrowRight" className="h-4 w-4" />
            </Link>
            <Link
              href="/planner"
              className="l-btn-ghost inline-flex items-center gap-2 rounded-full px-6 py-3.5 font-semibold"
            >
              <T k="hero.ai" /> <Icon name="ai" className="l-gold h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>

      <p className="l-muted absolute right-5 top-24 hidden text-[11px] sm:block lg:top-28">
        <T k="hero.art" />
      </p>
      <a
        href="#search"
        className="l-muted absolute bottom-[10.5rem] left-1/2 hidden -translate-x-1/2 flex-col items-center gap-1 text-xs md:flex lg:bottom-[13.5rem]"
      >
        <span className="grid h-9 w-6 justify-center rounded-full pt-1.5 ring-1 ring-current">
          <span className="h-2 w-1 rounded-full bg-current motion-safe:animate-bounce" />
        </span>
        <span className="sr-only">
          <T k="hero.scroll" />
        </span>
      </a>
    </section>
  );
}

/** Faint line art: a flight path with a plane, and a train and a bus on the road below. */
function TransportLines() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 1440 400"
      preserveAspectRatio="xMidYMax slice"
      className="l-lines pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-[55%] w-full"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
    >
      {/* flight path on the right, clear of the headline and buttons, ending in a plane */}
      <path d="M790 232 C 900 150, 1040 120, 1150 135" strokeDasharray="2 9" />
      <g transform="translate(1150 135) rotate(8) translate(-14 -20)" fill="currentColor" stroke="none">
        <path d="M4 20Q4 18.4 6 18.4H31Q37 18.4 39 20Q37 21.6 31 21.6H6Q4 21.6 4 20Z" />
        <path d="M17 18.6 24.5 6H28.5L24.8 18.6ZM17 21.4 24.5 34H28.5L24.8 21.4Z" />
        <path d="M5.5 18.6 3.5 12.5H6.8L10.5 18.6ZM5.5 21.4 3.5 27.5H6.8L10.5 21.4Z" />
      </g>
      <path d="M0 352h1440" />
      <g transform="translate(860 318)">
        <path d="M0 30h170M10 30V8q0-8 8-8h132q14 0 20 18l2 12" />
        <path d="M30 8h18v10H30zM60 8h18v10H60zM90 8h18v10H90zM120 8h18v10h-18z" />
        <circle cx="35" cy="33" r="3" />
        <circle cx="140" cy="33" r="3" />
      </g>
      <g transform="translate(330 322)">
        <path d="M0 26V6q0-6 6-6h76q8 0 10 8l4 18zM8 6h16v9H8zM30 6h16v9H30zM52 6h16v9H52z" />
        <circle cx="20" cy="28" r="4" />
        <circle cx="76" cy="28" r="4" />
      </g>
    </svg>
  );
}
