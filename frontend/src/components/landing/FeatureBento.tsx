import Link from "next/link";
import { Icon, type IconName } from "../Icons";
import { T } from "../T";
import type { Key } from "@/lib/i18n";

const FEATURES: [IconName, Key, Key][] = [
  ["route", "why.f1", "why.f1d"],
  ["ai", "why.f2", "why.f2d"],
  ["coin", "why.f3", "why.f3d"],
  ["shield", "why.f4", "why.f4d"],
  ["bookmark", "why.f5", "why.f5d"],
  ["compass", "why.f6", "why.f6d"],
];

/** Why T-PORT: heading and intro on the left, six features in a clean grid on the right. */
export function FeatureBento() {
  return (
    <section aria-labelledby="why-h" className="grid gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.6fr)] lg:gap-16">
      <div className="reveal lg:sticky lg:top-28 lg:self-start">
        <p className="text-xs font-semibold uppercase tracking-[0.32em] text-sky">
          <T k="why.eyebrow" />
        </p>
        <h2 id="why-h" className="mt-3 text-3xl font-extrabold tracking-tight sm:text-5xl">
          <T k="why.title" />
        </h2>
        <p className="mt-4 max-w-md text-base leading-relaxed text-muted sm:text-lg">
          <T k="why.sub" />
        </p>
        <Link href="/search" className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-sky hover:underline">
          <T k="search.submit" /> <Icon name="arrowRight" className="h-4 w-4" />
        </Link>
      </div>

      <ul className="reveal grid overflow-hidden rounded-3xl bg-surface shadow-soft sm:grid-cols-2">
        {FEATURES.map(([icon, title, body], i) => (
          <li
            key={title}
            className={`group flex gap-4 p-6 transition-colors hover:bg-surface-2 sm:p-7 ${i > 0 ? "border-t border-line" : ""} ${
              i === 1 ? "sm:border-t-0" : ""
            } ${i % 2 === 1 ? "sm:border-l sm:border-line" : ""}`}
          >
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-sky/10 text-sky ring-1 ring-sky/25 transition group-hover:bg-sky/15">
              <Icon name={icon} className="h-5 w-5" />
            </span>
            <span>
              <h3 className="text-base font-bold leading-snug">
                <T k={title} />
              </h3>
              <p className="mt-1 text-sm leading-relaxed text-muted">
                <T k={body} />
              </p>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
