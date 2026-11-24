import Link from "next/link";
import { Icon } from "../Icons";
import { T } from "../T";

/** Closing call to action over a dusk horizon: mountains, an Uzbek skyline, a train and a plane. */
export function FinalCTA() {
  return (
    <section aria-labelledby="cta-h" className="l-horizon l-text bleed relative isolate overflow-hidden pt-24 sm:pt-32">
      <div className="relative mx-auto max-w-3xl px-5 text-center">
        <h2 id="cta-h" className="reveal text-3xl font-extrabold tracking-tight sm:text-5xl">
          <T k="cta.title" />
        </h2>
        <p className="l-sub reveal mt-4 text-base sm:text-lg">
          <T k="cta.sub" />
        </p>
        <div className="reveal mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="/register"
            className="inline-flex items-center gap-2 rounded-full bg-blue px-7 py-3.5 font-semibold text-white transition hover:bg-blue-hover"
          >
            <T k="cta.primary" /> <Icon name="arrowRight" className="h-4 w-4" />
          </Link>
          <Link
            href="/explore"
            className="l-btn-ghost inline-flex items-center gap-2 rounded-full px-7 py-3.5 font-semibold"
          >
            <T k="cta.secondary" />
          </Link>
        </div>
      </div>
      <Horizon />
    </section>
  );
}

function Horizon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 1440 340" preserveAspectRatio="xMidYMax slice" className="mt-10 block h-40 w-full sm:h-64 lg:aspect-[1440/340] lg:h-auto">
      <defs>
        <radialGradient id="h-sun" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" style={{ stopColor: "var(--h-sun-a)", stopOpacity: 0.95 }} />
          <stop offset="0.35" style={{ stopColor: "var(--h-sun-b)", stopOpacity: 0.45 }} />
          <stop offset="1" style={{ stopColor: "var(--h-sun-b)", stopOpacity: 0 }} />
        </radialGradient>
        <linearGradient id="h-far" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" style={{ stopColor: "var(--h-far-a)" }} />
          <stop offset="1" style={{ stopColor: "var(--h-far-b)" }} />
        </linearGradient>
        <linearGradient id="h-near" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" style={{ stopColor: "var(--h-near-a)" }} />
          <stop offset="1" style={{ stopColor: "var(--h-near-b)" }} />
        </linearGradient>
        <linearGradient id="h-flight" x1="0" x2="1">
          <stop offset="0" style={{ stopColor: "var(--h-path)", stopOpacity: 0 }} />
          <stop offset="1" style={{ stopColor: "var(--h-path)", stopOpacity: 0.7 }} />
        </linearGradient>
      </defs>

      {/* sun glow and flight path */}
      <circle cx="940" cy="236" r="180" fill="url(#h-sun)" opacity="0.6" />
      <path d="M300 172 Q 700 10 1070 112" fill="none" stroke="url(#h-flight)" strokeWidth="1.6" strokeDasharray="2 8" strokeLinecap="round" />
      <g transform="translate(1070 112) rotate(18) translate(-20 -10)" style={{ fill: "var(--h-plane)" }}>
        <path d="M2 10Q2 8 6 8H31Q38 8 40 10Q38 12 31 12H6Q2 12 2 10Z" />
        <path d="M17 8.5 24 0H28.5L24.5 8.5ZM17 11.5 24 20H28.5L24.5 11.5Z" />
        <path d="M4 8.5 2 3.5H5.5L9.5 8.5ZM4 11.5 2 16.5H5.5L9.5 11.5Z" />
      </g>

      {/* mountains */}
      <path
        d="M0 228 C90 204 150 176 230 186 S360 150 440 168 S600 196 690 172 S830 132 930 156 S1090 190 1180 166 S1340 140 1440 160 V340 H0Z"
        fill="url(#h-far)"
        opacity="0.9"
      />
      <path d="M0 262 C160 240 260 252 380 238 S620 232 760 246 S1020 236 1160 244 S1360 236 1440 242 V340 H0Z" fill="url(#h-near)" />

      {/* skyline */}
      <g style={{ fill: "var(--h-sil)" }}>
        {/* Tashkent: towers and the TV tower */}
        <path d="M86 284V196h28v88ZM120 284V168l14-10 14 10v116ZM154 284v-74h26v74Z" />
        <path d="M226 284 230 150h4l4 134Z" />
        <ellipse cx="232" cy="186" rx="13" ry="7" />
        <ellipse cx="232" cy="164" rx="7" ry="4" />
        <path d="M231 150V110h2v40Z" />
        {/* Registan-like madrasa: portal with pointed arch, flanking minarets, ribbed dome */}
        <path d="M352 284v-70h190v70Z" />
        <path d="M414 284V168h66v116Z" />
        <path d="M362 214v-62l6-8 6 8v62ZM520 214v-62l6-8 6 8v62Z" />
        <path d="M486 214v-14h40v14Z" />
        <path d="M486 200a20 22 0 0 1 40 0Z" />
        {/* Kalon-like minaret with lantern */}
        <path d="M682 284 690 148h16l8 136Z" />
        <path d="M686 148v-14h24v14Z" />
        <path d="M688 134a10 9 0 0 1 20 0Z" />
        {/* domed mosque and low houses */}
        <path d="M716 284v-46h76v46Z" />
        <path d="M734 238v-10h40v10Z" />
        <path d="M734 228a20 24 0 0 1 40 0Z" />
        <path d="M300 284v-28h44v28ZM560 284v-32h52v32Z" />
      </g>
      {/* lit arches */}
      <g style={{ fill: "var(--h-lit)" }} fillOpacity="0.4">
        <path d="M438 284v-54a9 14 0 0 1 18 0v54Z" />
        <path d="M374 236h10v14h-10ZM510 236h10v14h-10ZM746 256h12v14h-12Z" />
      </g>

      {/* ground, rail and train */}
      <path d="M0 284h1440v56H0Z" style={{ fill: "var(--h-ground)" }} />
      <path d="M780 282h400" style={{ stroke: "var(--h-train-line)" }} strokeOpacity="0.4" strokeWidth="1.5" />
      <g transform="translate(-140 0)">
        <path d="M948 280v-24q0-8 8-8h236q34 2 52 26l4 6Z" style={{ fill: "var(--h-train)", stroke: "var(--h-train-line)" }} strokeOpacity="0.6" strokeWidth="1.4" />
        <path d="M966 262h200" style={{ stroke: "var(--h-train-line)" }} strokeOpacity="0.75" strokeWidth="5" strokeDasharray="22 7" strokeLinecap="round" />
        <path d="M1196 258l22 0q10 2 16 10" fill="none" style={{ stroke: "var(--h-train-line)" }} strokeOpacity="0.75" strokeWidth="3" strokeLinecap="round" />
      </g>
    </svg>
  );
}
