"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "./Icons";
import { LandingNav } from "./landing/LandingNav";

interface NavItem {
  href: string;
  label: string;
  short: string;
  icon: IconName;
  match: (p: string) => boolean;
  mobile: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", short: "Home", icon: "home", match: (p) => p === "/", mobile: true },
  {
    href: "/search",
    label: "Search Routes",
    short: "Search",
    icon: "search",
    match: (p) => p.startsWith("/search") || p.startsWith("/journeys") || p.startsWith("/book"),
    mobile: true,
  },
  { href: "/planner", label: "T-AI", short: "T-AI", icon: "ai", match: (p) => p.startsWith("/planner"), mobile: true },
  { href: "/explore", label: "Explore", short: "Explore", icon: "compass", match: (p) => p.startsWith("/explore"), mobile: false },
  { href: "/compare", label: "Compare", short: "Compare", icon: "route", match: (p) => p.startsWith("/compare"), mobile: false },
  { href: "/dashboard", label: "My Trips", short: "Trips", icon: "bookmark", match: (p) => p.startsWith("/dashboard"), mobile: true },
  { href: "/profile", label: "Profile", short: "Profile", icon: "user", match: (p) => p.startsWith("/profile"), mobile: true },
];

/** Header pills: always on the home page (md+); on app pages only between md and lg (the sidebar takes over). */
export function HeaderNav() {
  const pathname = usePathname();
  if (pathname === "/") return <LandingNav />;
  return (
    <ul className="hidden items-center gap-1 rounded-full bg-surface p-1 shadow-soft md:flex lg:hidden">
      {NAV_ITEMS.map((item) => {
        const active = item.match(pathname);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-2 text-sm font-medium transition ${
                active ? "bg-blue text-white" : "text-ink/80 hover:bg-surface-2 hover:text-ink"
              }`}
            >
              <Icon name={item.icon} className="h-4 w-4" />
              {item.short}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/** Left sidebar on app pages from `lg` up (not on the home page, which has the hero layout). */
export function AppSidebar() {
  const pathname = usePathname();
  if (pathname === "/") return null;
  return (
    <aside className="sticky top-24 hidden h-[calc(100vh-7rem)] w-60 shrink-0 flex-col gap-4 lg:flex" aria-label="Sections">
      <nav aria-label="App sections" className="rounded-3xl bg-surface p-2 shadow-soft">
        <ul className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const active = item.match(pathname);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition ${
                    active ? "bg-blue text-white" : "text-ink/85 hover:bg-surface-2"
                  }`}
                >
                  <Icon name={item.icon} className="h-5 w-5" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="mt-auto rounded-3xl border border-gold/40 bg-surface p-4 shadow-soft">
        <p className="flex items-center gap-2 font-semibold">
          <Icon name="ai" className="h-5 w-5" /> Powered by T-AI
        </p>
        <ul className="mt-3 space-y-1.5 text-xs text-muted">
          {["Best routes across modes", "Knows all 14 regions", "Sources shown, nothing invented"].map((t) => (
            <li key={t} className="flex items-center gap-2">
              <Icon name="check" className="h-4 w-4 text-gold" /> {t}
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

/** Tab bar on phones (hidden from `md` up). */
export function BottomNav() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="App"
      className="fixed inset-x-0 bottom-0 z-30 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:hidden"
    >
      <ul className="mx-auto flex max-w-md items-stretch justify-between rounded-3xl bg-card p-1.5 shadow-float">
        {NAV_ITEMS.filter((i) => i.mobile).map((item) => {
          const active = item.match(pathname);
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center gap-0.5 rounded-2xl py-1.5 text-[0.7rem] font-medium transition ${
                  active ? "bg-blue text-white" : "text-muted hover:text-ink"
                }`}
              >
                <Icon name={item.icon} className="h-5 w-5" />
                {item.short}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** The header's "Global AI Transit & Travel" line: from lg on app pages; only on wide screens on the busier landing nav. */
export function HeaderTagline() {
  const home = usePathname() === "/";
  return (
    <span className={`hidden border-l border-line pl-3 text-xs leading-tight text-muted ${home ? "2xl:block" : "lg:block"}`}>
      <span className="block font-semibold text-ink">Global AI Transit &amp; Travel</span>
      One Destination. Every Way to Get There.
    </span>
  );
}
