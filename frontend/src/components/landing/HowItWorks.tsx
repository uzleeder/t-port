import { Icon, type IconName } from "../Icons";
import { T } from "../T";
import type { Key } from "@/lib/i18n";

const STEPS: [string, IconName, Key, Key][] = [
  ["01", "search", "how.s1", "how.s1d"],
  ["02", "route", "how.s2", "how.s2d"],
  ["03", "sparkle", "how.s3", "how.s3d"],
  ["04", "arrowUpRight", "how.s4", "how.s4d"],
];

/** Four steps on one connected track: horizontal on wide screens, vertical on phones and tablets. */
export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-h" className="scroll-mt-28">
      <div className="reveal mx-auto max-w-3xl text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.32em] text-sky">
          <T k="how.eyebrow" />
        </p>
        <h2 id="how-h" className="mt-3 text-3xl font-extrabold tracking-tight sm:text-5xl">
          <T k="how.title" />
        </h2>
      </div>

      <ol className="mx-auto mt-14 grid max-w-6xl gap-0 lg:grid-cols-4 lg:gap-6">
        {STEPS.map(([n, icon, title, body], i) => {
          const last = i === STEPS.length - 1;
          return (
            <li key={n} className="reveal relative flex gap-5 pb-10 lg:flex-col lg:gap-6 lg:pb-0">
              {/* track to the next step */}
              {!last && (
                <span
                  aria-hidden="true"
                  className="absolute left-6 top-12 h-[calc(100%-3rem)] w-px bg-gradient-to-b from-sky/60 to-sky/10 lg:left-[3.25rem] lg:top-6 lg:h-px lg:w-[calc(100%-3.25rem+1.5rem)] lg:bg-gradient-to-r"
                />
              )}
              <span className="relative z-10 grid h-12 w-12 shrink-0 place-items-center rounded-full bg-navy text-sm font-bold tabular-nums text-sky ring-1 ring-sky/40 shadow-[0_0_24px_rgb(0_122_255/0.25)]">
                {n}
              </span>
              <div className="lift flex-1 rounded-3xl bg-surface p-6 shadow-soft">
                <span className="grid h-10 w-10 place-items-center rounded-2xl bg-blue/15 text-sky ring-1 ring-blue/30">
                  <Icon name={icon} className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-lg font-bold">
                  <T k={title} />
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">
                  <T k={body} />
                </p>
              </div>
            </li>
          );
        })}
      </ol>

      <p className="reveal mx-auto mt-10 flex w-fit max-w-3xl items-start gap-3 rounded-2xl bg-surface px-5 py-3.5 text-sm leading-relaxed text-muted shadow-soft">
        <Icon name="shield" className="mt-0.5 h-4 w-4 shrink-0 text-gold" />
        <span>
          <T k="how.note" />
        </span>
      </p>
    </section>
  );
}
