/** Small stroke icon set used by the app chrome and cards (24×24 grid, currentColor). */

import { TAILogo } from "./TAILogo";

const PATHS = {
  home: "M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H5a1 1 0 0 1-1-1z",
  compass: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm3.5-12.5-2 5-5 2 2-5z",
  bookmark: "M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1Z",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0",
  sparkle:
    "M12 3.5 13.6 9a2 2 0 0 0 1.4 1.4l5.5 1.6-5.5 1.6a2 2 0 0 0-1.4 1.4L12 20.5 10.4 15A2 2 0 0 0 9 13.6L3.5 12 9 10.4A2 2 0 0 0 10.4 9zM19 3v3m-1.5-1.5h3",
  arrowUpRight: "M7 17 17 7M8 7h9v9",
  arrowRight: "M5 12h14m-6-6 6 6-6 6",
  chevronLeft: "M15 5l-7 7 7 7",
  chevronDown: "M6 9l6 6 6-6",
  share: "M12 15V4m0 0L8 8m4-4 4 4M5 13v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5",
  calendar: "M7 3v3m10-3v3M4.5 8.5h15M6 5h12a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z",
  plane:
    "M10.6 3.6c.4-.8 2.4-.8 2.8 0 .3.6.4 1.6.4 3V9l7 4.2v2.1l-7-2.1v3.9l2.2 1.7V21L12 20.1 8 21v-2.2l2.2-1.7v-3.9l-7 2.1v-2.1l7-4.2V6.6c0-1.4.1-2.4.4-3Z",
  coin: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm2.5-11.5c-.4-.9-1.4-1.5-2.5-1.5-1.4 0-2.5.8-2.5 2s1.1 1.7 2.5 2 2.5.8 2.5 2-1.1 2-2.5 2c-1.1 0-2.1-.6-2.5-1.5M12 6.5v11",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v4.5l3 2",
  route: "M6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm12-10a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM8 17h7.5a3.5 3.5 0 0 0 0-7h-7a3.5 3.5 0 0 1 0-7H16",
  shield: "M12 3 5 6v6c0 4.2 2.9 7.6 7 9 4.1-1.4 7-4.8 7-9V6z",
  check: "M5 12.5 10 17 19 7.5",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm9 2-4-4",
  send: "M21 3 10.5 13.5M21 3l-6.5 18-4-7.5L3 9.5z",
  city: "M3 21h18M5 21V10h4v11m0 0V4h6v17m0 0v-8h4v8",
  mountain: "M3 19 9.5 8.5l3.5 5.5 2.5-3.5L21 19z",
  dome: "M4 20h16M6 20v-6a6 6 0 0 1 12 0v6M12 8V4.5M10 20v-3a2 2 0 0 1 4 0v3",
  tower: "M10 21V9.5L9 7h6l-1 2.5V21M8 21h8M12 7V3.5M10 13h4M10 17h4",
  fortress: "M4 21V8h2.5v2H9V8h2v2h2V8h2v2h2.5V8H20v13M3 21h18M10 21v-3.5a2 2 0 0 1 4 0V21",
  leaf: "M5 19C5 11 10 6 19 5c0 9-5 14-13 14m-1 0 7-7",
  flower:
    "M12 14a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Zm0-5c0-2.5 1.2-4.5 2.8-4.5S17 6.4 15 9m-3 0c0-2.5-1.2-4.5-2.8-4.5S7 6.4 9 9m.6 3.2c-2.4.8-4.6.3-5.1-1.2s1.3-3 3.7-2.6m6.2 3.8c2.4.8 4.6.3 5.1-1.2s-1.3-3-3.7-2.6M12 14v7m0-3c1.5-1.8 3.5-2.2 5-1.5m-5 1.5c-1.5-1.8-3.5-2.2-5-1.5",
  waves: "M3 8.5c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0M3 13.5c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0M3 18.5c2-1.5 4-1.5 6 0s4 1.5 6 0 4-1.5 6 0",
  swap: "M7 7h13m0 0-3.5-3.5M20 7l-3.5 3.5M17 17H4m0 0 3.5-3.5M4 17l3.5 3.5",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-9-9h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3Z",
  camera:
    "M4 8.5A1.5 1.5 0 0 1 5.5 7h2l1.5-2h6l1.5 2h2A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5zM12 16.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z",
  pencil: "M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4",
  menu: "M4 7h16M4 12h16M4 17h16",
  close: "M6 6l12 12M18 6 6 18",
  grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0-14v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
} as const;

export type IconName = keyof typeof PATHS | "ai";

export function Icon({
  name,
  className = "h-5 w-5",
  strokeWidth = 1.8,
}: {
  name: IconName;
  className?: string;
  strokeWidth?: number;
}) {
  if (name === "ai") return <TAILogo size={24} className={className} still />;
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
