import Link from "next/link";
import type { ReactNode } from "react";
import { PlacePhoto } from "./PlacePhoto";
import { HERO_PHOTO } from "@/lib/photos";
import { Icon, type IconName } from "./Icons";

/** Page title row with the skyline fading in on the right, shared by the app pages. */
export function PageBanner({
  title,
  accent,
  subtitle,
  icon,
  back,
  actions,
  subtitleAs = "p",
}: {
  title: string;
  /** Last word(s) of the title in brand blue, as in "Search Results". */
  accent?: string;
  subtitle?: ReactNode;
  icon?: IconName;
  back?: { href: string; label: string };
  actions?: ReactNode;
  subtitleAs?: "p" | "h2";
}) {
  const Sub = subtitleAs;
  return (
    <header className="relative min-h-[8.5rem] overflow-hidden rounded-3xl">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 right-0 hidden w-[55%] overflow-hidden rounded-3xl [mask-image:linear-gradient(to_right,transparent,black_40%)] md:block"
      >
        <PlacePhoto photo={HERO_PHOTO} decorative sizes="55vw" className="object-[50%_60%]" />
      </div>
      <div className="relative flex flex-wrap items-center gap-4 py-3 md:pr-[48%]">
        {back && (
          <Link
            href={back.href}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface shadow-soft hover:bg-surface-2"
          >
            <Icon name="chevronLeft" />
            <span className="sr-only">{back.label}</span>
          </Link>
        )}
        {icon && (
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-blue/15 text-sky ring-1 ring-blue/40">
            <Icon name={icon} className="h-7 w-7" />
          </span>
        )}
        <div className="min-w-0">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
            {title}
            {accent && <span className="ml-2 italic text-blue">{accent}</span>}
          </h1>
          {subtitle && <Sub className="mt-1 text-base font-normal text-muted">{subtitle}</Sub>}
        </div>
      </div>
      {actions && <div className="relative flex flex-wrap gap-2 pb-2 md:absolute md:bottom-3 md:right-3 md:pb-0">{actions}</div>}
    </header>
  );
}
