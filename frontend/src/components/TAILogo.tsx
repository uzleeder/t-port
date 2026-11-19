"use client";

import { useId } from "react";

// The user's original artwork, clipped to the mark. No redraw or generated replacement.
const OUTLINE = "M85 85 L103 49 Q111 36 128 36 L247 36 Q267 36 277 49 L271 21 L332 43 L332 55 L280 94 L280 69 C253 80 233 90 227 111 Q222 125 225 157 L225 184 Q225 205 208 216 L159 238 L157 230 L157 147 Q157 113 188 93 L86 93 Z";

export function TAILogo({ size = 40, className = "", still = false }: { size?: number; className?: string; still?: boolean }) {
  const id = `tai${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg viewBox="78 14 262 230" width={size} height={size} aria-hidden="true"
      data-ai-mark="neural-arrow" data-still={still || undefined}
      className={`tai-logo shrink-0 ${className}`}>
      <defs><clipPath id={id}><path d={OUTLINE} /></clipPath></defs>
      <image href="/images/t-ai/neural-arrow-reference.png" width="446" height="250"
        clipPath={`url(#${id})`} className="tai-original-art" />
      <g clipPath={`url(#${id})`} className="tai-neural-motion" aria-hidden="true">
        {[
          ["M112 74 L152 64 L175 78 L204 54 L253 62 L286 57", "6s", "-2s"],
          ["M169 219 L179 165 L198 147 L210 176 L207 203", "7s", "-4s"],
          ["M174 147 L196 127 L204 104 L240 78 L286 57 L307 47", "5s", "-1s"],
        ].map(([path, duration, begin]) => (
          <g key={path}>
            <path d={path} fill="none" stroke="#c1f7ff" strokeWidth="0.6" strokeOpacity="0.22" />
            <circle r="2" fill="#e4fcff">
              <animateMotion path={path} dur={duration} begin={begin} repeatCount="indefinite" />
            </circle>
            <circle r="1.1" fill="#ffdf9b">
              <animateMotion path={path} dur={duration} begin="-3s" repeatCount="indefinite" />
            </circle>
          </g>
        ))}
      </g>
    </svg>
  );
}
