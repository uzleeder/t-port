"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "../Icons";
import { LanguageSelect } from "../LanguageSelect";
import { TAILogo } from "../TAILogo";
import { T } from "../T";
import type { Key } from "@/lib/i18n";

const LINKS: [string, Key][] = [
  ["/", "nav.home"],
  ["/#explore", "nav.explore"],
  ["/#how-it-works", "nav.how"],
  ["/planner", "nav.ai"],
  ["/#about", "nav.about"],
];

/** Landing-page navigation: links and language on tablets and up; a compact menu on phones. */
export function LandingNav() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <ul className="hidden items-center gap-0.5 lg:flex">
        {LINKS.map(([href, k], i) => (
          <li key={href}>
            <Link
              href={href}
              aria-current={i === 0 ? "page" : undefined}
              className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-2 text-sm font-medium text-ink/80 transition hover:bg-surface-2 hover:text-ink aria-[current=page]:text-ink"
            >
              {href === "/planner" && <TAILogo size={18} still />}<T k={k} />
            </Link>
          </li>
        ))}
      </ul>
      <div className="hidden lg:block">
        <LanguageSelect compact />
      </div>

      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-surface-2 text-ink ring-1 ring-line lg:hidden"
      >
        <Icon name={open ? "close" : "menu"} className="h-5 w-5" />
        <span className="sr-only">{open ? <T k="nav.close" /> : <T k="nav.menu" />}</span>
      </button>
      <div
        id={panelId}
        hidden={!open}
        className="absolute inset-x-3 top-[calc(100%+0.5rem)] rounded-3xl bg-navy/95 p-3 shadow-float ring-1 ring-line backdrop-blur-xl sm:left-auto sm:w-80 lg:hidden"
      >
        <ul className="grid gap-1">
          {LINKS.map(([href, k]) => (
            <li key={href}>
              <Link
                href={href}
                onClick={() => setOpen(false)}
                className="flex items-center justify-between rounded-2xl px-4 py-3 text-base font-medium hover:bg-surface-2"
              >
                {href === "/planner" && <TAILogo size={18} still />}<T k={k} />
                <Icon name="arrowRight" className="h-4 w-4 text-muted" />
              </Link>
            </li>
          ))}
        </ul>
        <div className="mt-2 border-t border-line px-2 pt-3">
          <LanguageSelect />
        </div>
      </div>
    </>
  );
}
