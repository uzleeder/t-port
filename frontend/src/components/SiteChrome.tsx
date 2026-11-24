import Link from "next/link";
import { Suspense } from "react";
import { AccountNav } from "./AccountNav";
import { HeaderNav, HeaderTagline } from "./BottomNav";
import { HeaderScroll } from "./HeaderScroll";
import { LanguageSelect } from "./LanguageSelect";
import { T } from "./T";
import type { Key } from "@/lib/i18n";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 px-3 pt-3 sm:px-6">
      <nav
        aria-label="Main"
        className="relative mx-auto flex max-w-[94rem] items-center gap-3 rounded-full bg-surface py-2 pl-2 pr-2 shadow-soft"
      >
        <HeaderScroll />
        <Logo />
        <Suspense fallback={null}>
          <HeaderTagline />
        </Suspense>
        <div className="ml-auto flex items-center gap-2">
          {/* The active link depends on the current path, which is only known at request time. */}
          <Suspense fallback={null}>
            <HeaderNav />
          </Suspense>
          <ThemeToggle />
          <AccountNav />
        </div>
      </nav>
    </header>
  );
}

const FOOTER_PRODUCT: [string, Key][] = [
  ["/search", "footer.search"],
  ["/explore", "footer.explore"],
  ["/planner", "footer.ai"],
  ["/compare", "footer.compare"],
  ["/dashboard", "footer.trips"],
];
const FOOTER_COMPANY: [string, Key][] = [
  ["/#about", "footer.about"],
  ["/#how-it-works", "footer.help"],
  ["/privacy", "footer.privacy"],
  ["/credits", "footer.credits"],
];
const FOOTER_MODES: Key[] = ["search.train", "search.bus", "search.flight", "search.taxi"];

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-line">
      <div className="mx-auto grid max-w-[94rem] gap-10 px-5 py-12 sm:grid-cols-2 sm:px-10 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div className="space-y-4">
          <Logo />
          <p className="max-w-xs text-sm text-muted">
            <T k="slogan" />
          </p>
          <LanguageSelect />
        </div>
        <FooterList title="footer.product" items={FOOTER_PRODUCT} />
        <div>
          <h2 className="text-sm font-semibold">
            <T k="footer.modes" />
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-muted">
            {FOOTER_MODES.map((k) => (
              <li key={k}>
                <T k={k} />
              </li>
            ))}
          </ul>
        </div>
        <FooterList title="footer.company" items={FOOTER_COMPANY} />
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-[94rem] flex-col gap-1 px-5 py-5 text-xs text-muted sm:flex-row sm:flex-wrap sm:justify-between sm:px-10">
          <p>
            <T k="footer.rights" /> <T k="footer.by" /> <T k="vision.title" />
          </p>
          <p>
            <T k="footer.pilot" />
          </p>
        </div>
      </div>
    </footer>
  );
}

function FooterList({ title, items }: { title: Key; items: [string, Key][] }) {
  return (
    <div>
      <h2 className="text-sm font-semibold">
        <T k={title} />
      </h2>
      <ul className="mt-3 space-y-2 text-sm">
        {items.map(([href, k]) => (
          <li key={href}>
            <Link href={href} className="text-muted hover:text-ink">
              <T k={k} />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
