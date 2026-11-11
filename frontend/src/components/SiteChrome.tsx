import Link from "next/link";
import { Logo } from "./Logo";
import { AccountNav } from "./AccountNav";

export function SiteHeader() {
  return (
    <header className="border-b border-line/60 bg-navy/80 backdrop-blur">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 sm:px-6"
      >
        <Logo />
        <Link href="/search" className="hidden text-sm text-muted hover:text-ink sm:inline">
          Search
        </Link>
        <div className="ml-auto">
          <AccountNav />
        </div>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-line/60">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-sm text-muted sm:flex-row sm:justify-between sm:px-6">
        <p>
          <span className="font-semibold text-ink">T-Port</span> · One Destination. Every Way to
          Get There.
        </p>
        <p>Phase 1 pilot · Uzbekistan · Planning information only — no ticket sales.</p>
      </div>
    </footer>
  );
}
