import { T } from "../T";
import { RotatingGlobe } from "./RotatingGlobe";
import type { Key } from "@/lib/i18n";

const ROADMAP: [Key, Key, Key, "now" | "planned" | "vision"][] = [
  ["vision.r1", "vision.r1d", "vision.r1s", "now"],
  ["vision.r2", "vision.r2d", "vision.r2s", "planned"],
  ["vision.r3", "vision.r3d", "vision.r3s", "vision"],
];

const STATUS_TONE = {
  now: { dot: "bg-success shadow-[0_0_12px_var(--color-success)]", pill: "bg-success/15 text-success" },
  planned: { dot: "bg-gold", pill: "bg-gold/15 text-gold" },
  vision: { dot: "bg-sky/70", pill: "l-card l-muted" },
};

/** Vision and about: a dotted globe with Uzbekistan's connections and the (clearly planned) roadmap. */
export function GlobalVision() {
  return (
    <section id="about" aria-labelledby="vision-h" className="l-section l-text bleed relative scroll-mt-20 overflow-hidden py-24 sm:py-32">
      <div className="relative mx-auto grid max-w-[94rem] items-center gap-14 px-5 sm:px-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-20">
        <div className="reveal">
          <p className="l-gold text-xs font-semibold uppercase tracking-[0.32em]">
            <T k="vision.eyebrow" />
          </p>
          <h2 id="vision-h" className="mt-3 text-3xl font-extrabold tracking-tight sm:text-5xl">
            <T k="vision.title" />
          </h2>
          <p className="mt-5 max-w-xl text-base leading-relaxed l-sub sm:text-lg">
            <T k="vision.p1" />
          </p>
          <p className="mt-3 max-w-xl leading-relaxed l-muted">
            <T k="vision.p2" />
          </p>

          <ol className="relative mt-10 max-w-xl space-y-7 pl-9">
            <span aria-hidden="true" className="absolute bottom-3 left-[0.4rem] top-3 w-px bg-gradient-to-b from-success/70 via-gold/50 to-sky/20" />
            {ROADMAP.map(([name, desc, status, kind]) => (
              <li key={name} className="relative">
                <span aria-hidden="true" className={`absolute -left-9 top-1.5 h-3.5 w-3.5 rounded-full ring-4 ring-[color:var(--l-section-solid)] ${STATUS_TONE[kind].dot}`} />
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="text-lg font-semibold">
                    <T k={name} />
                  </span>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_TONE[kind].pill}`}>
                    <T k={status} />
                  </span>
                </div>
                <p className="mt-0.5 text-sm l-muted">
                  <T k={desc} />
                </p>
              </li>
            ))}
          </ol>
          <p className="l-muted mt-8 max-w-xl border-t border-line pt-5 text-sm">
            <T k="vision.note" /> <T k="vision.by" />
          </p>
        </div>
        <RotatingGlobe label={<T k="vision.r1" />} />
      </div>
    </section>
  );
}
