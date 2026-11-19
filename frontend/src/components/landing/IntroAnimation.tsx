"use client";

import { useEffect } from "react";
import { TPortMark } from "../Logo";
import { T } from "../T";

function finish() {
  delete document.documentElement.dataset.intro;
}

/**
 * Opening sequence for first-time visitors: a blue light crosses the screen, the T-PORT emblem
 * appears with an orbital ring, then the wordmark and slogan, then the page (about 2.3 s).
 * Whether it plays is decided before first paint (app/layout.tsx); it is only CSS, so the page is
 * fully usable without it. Skip with the button or Escape.
 */
export function IntroAnimation() {
  useEffect(() => {
    if (document.documentElement.dataset.intro !== "play") return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && finish();
    window.addEventListener("keydown", onKey);
    const done = setTimeout(finish, 2600); // in case animationend never fires (background tab)
    return () => {
      window.removeEventListener("keydown", onKey);
      clearTimeout(done);
    };
  }, []);

  return (
    <div
      className="tport-intro"
      onAnimationEnd={(e) => e.animationName === "intro-out" && e.target === e.currentTarget && finish()}
    >
      <span className="beam" aria-hidden="true" />
      <div className="flex flex-col items-center px-6 text-center" aria-hidden="true">
        <span
          className="emblem relative grid h-28 w-28 place-items-center rounded-full bg-black shadow-[0_0_60px_rgb(0_122_255/0.35)]"
          style={{ ["--logo-sw-1" as string]: "#fff", ["--logo-sw-2" as string]: "#f2f8ff", ["--logo-sw-3" as string]: "#bfddff" }}
        >
          <TPortMark className="h-16 w-16" />
          <svg viewBox="0 0 200 200" className="absolute -inset-6 h-[calc(100%+3rem)] w-[calc(100%+3rem)] overflow-visible">
            <ellipse
              className="ring"
              pathLength={100}
              cx="100"
              cy="100"
              rx="96"
              ry="38"
              transform="rotate(-18 100 100)"
              fill="none"
              stroke="url(#intro-ring)"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
            <defs>
              <linearGradient id="intro-ring" x1="0" x2="1">
                <stop offset="0" stopColor="#62cfff" stopOpacity="0" />
                <stop offset="0.5" stopColor="#62cfff" />
                <stop offset="1" stopColor="#d6b36a" />
              </linearGradient>
            </defs>
          </svg>
        </span>
        <span className="word mt-8 bg-gradient-to-r from-[#1fa8ff] to-[#1f5fff] bg-clip-text text-4xl font-extrabold tracking-[0.18em] text-transparent">
          T-PORT
        </span>
        <span className="tag l-sub mt-3 max-w-md text-base">
          <T k="slogan" />
        </span>
      </div>
      <button
        type="button"
        onClick={finish}
        className="l-btn-ghost absolute bottom-6 right-6 rounded-full px-4 py-2 text-sm font-medium"
      >
        <T k="intro.skip" />
      </button>
    </div>
  );
}
