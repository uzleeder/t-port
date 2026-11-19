import Link from "next/link";
import { useId } from "react";

/*
 * T-Port brand mark, redrawn as vector from the supplied artwork:
 * cyan->blue top bar, blue stem, white crescent swoosh, white paper-plane arrow.
 * Drawn in a 660x525 design grid; viewBox crops to the mark.
 */
const BAR = "M114 64 Q118 58 126 58 L468 58 L503 98 L60 152 Q48 154 53 144 Z";
const STEM = "M218 252 L382 166 L369 438 Q367 451 355 456 L224 492 Q216 494 216 485 Z";
const SWOOSH =
  "M217 338 C213 262 238 207 298 181 C360 155 428 136 492 116 C420 147 342 171 292 206 C254 233 233 280 226 342 Z";
const PLANE = "M486 57 L604 78 L503 136 L527 95 Z";

function MarkShapes({ id }: { id: string }) {
  return (
    <>
      <defs>
        <linearGradient id={`${id}-bar`} x1="50" y1="0" x2="505" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#2FD0FF" />
          <stop offset="0.55" stopColor="#2A9DFF" />
          <stop offset="1" stopColor="#2B6CF6" />
        </linearGradient>
        <linearGradient id={`${id}-stem`} x1="0" y1="170" x2="0" y2="495" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#2E8BFF" />
          <stop offset="1" stopColor="#1D55DE" />
        </linearGradient>
        <linearGradient id={`${id}-swoosh`} x1="490" y1="116" x2="220" y2="340" gradientUnits="userSpaceOnUse">
          {/* The white swoosh and arrow turn navy on light backgrounds (see --logo-* in globals.css). */}
          <stop offset="0" style={{ stopColor: "var(--logo-sw-1, #ffffff)" }} />
          <stop offset="0.7" style={{ stopColor: "var(--logo-sw-2, #f2f8ff)" }} />
          <stop offset="1" style={{ stopColor: "var(--logo-sw-3, #bfddff)" }} />
        </linearGradient>
      </defs>
      <path d={BAR} fill={`url(#${id}-bar)`} />
      <path d={STEM} fill={`url(#${id}-stem)`} />
      <path d={SWOOSH} fill={`url(#${id}-swoosh)`} />
      <path d={PLANE} style={{ fill: "var(--logo-sw-1, #ffffff)" }} />
    </>
  );
}

export function TPortMark({ className = "h-8 w-8" }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg viewBox="40 40 580 470" className={className} style={{ aspectRatio: "580 / 470" }} aria-hidden="true">
      <MarkShapes id={id} />
    </svg>
  );
}

/**
 * Hero version: the mark with an orbital trail. A light comet travels an ellipse that passes
 * behind the mark on the far side and in front of it on the near side (same comet drawn twice,
 * the front copy clipped to the near half). The group sways gently in 3D. All motion stops
 * under prefers-reduced-motion (see globals.css).
 */
export function OrbitMark({ className = "h-24 w-24" }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  const orbit = "M30 285 A300 92 0 1 1 630 285 A300 92 0 1 1 30 285";
  return (
    <span className={`tport-orbit-stage inline-block ${className}`} aria-hidden="true">
      <svg viewBox="0 20 660 540" className="tport-orbit-sway h-full w-full overflow-visible">
        <defs>
          <filter id={`${id}-comet`} x="-20%" y="-50%" width="140%" height="200%">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <clipPath id={`${id}-near`}>
            <rect x="0" y="285" width="660" height="160" />
          </clipPath>
          <filter id={`${id}-glow`} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="14" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <g transform="rotate(-14 330 285)">
          <path d={orbit} fill="none" stroke="#377DFF" strokeOpacity="0.25" strokeWidth="3" />
          <path d={orbit} pathLength={100} className="tport-comet" fill="none"
            stroke="#CFEBFF" strokeWidth="7" strokeLinecap="round" filter={`url(#${id}-comet)`} />
        </g>
        <g filter={`url(#${id}-glow)`}>
          <MarkShapes id={id} />
        </g>
        <g transform="rotate(-14 330 285)" clipPath={`url(#${id}-near)`}>
          <path d={orbit} fill="none" stroke="#377DFF" strokeOpacity="0.45" strokeWidth="3" />
          <path d={orbit} pathLength={100} className="tport-comet" fill="none"
            stroke="#CFEBFF" strokeWidth="7" strokeLinecap="round" filter={`url(#${id}-comet)`} />
        </g>
      </svg>
    </span>
  );
}

export function Logo({ size = "md" }: { size?: "md" | "lg" }) {
  const lg = size === "lg";
  return (
    <Link
      href="/"
      aria-label="T-Port home"
      className={`flex shrink-0 items-center whitespace-nowrap rounded-full ${lg ? "gap-3" : "gap-2 pl-1.5"}`}
    >
      {/* Built-in lockup: the mark sits directly beside the wordmark, with no badge behind it. */}
      <TPortMark className={lg ? "h-12 w-auto" : "h-8 w-auto"} />
      <span
        className={`bg-gradient-to-r from-[#1fa8ff] to-[#1f5fff] bg-clip-text font-extrabold tracking-[0.06em] text-transparent ${
          lg ? "text-3xl" : "text-[1.35rem] leading-none max-[439px]:sr-only"
        }`}
      >
        T-PORT
      </span>
    </Link>
  );
}
