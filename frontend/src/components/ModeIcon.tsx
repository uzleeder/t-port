import type { Mode } from "@/lib/types";

const PATHS: Record<Mode, string> = {
  train:
    "M7 3h10a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3Zm-3 8h16M8 21l2-3m6 3-2-3M8 15h.01M16 15h.01",
  bus: "M6 3h12a2 2 0 0 1 2 2v12H4V5a2 2 0 0 1 2-2Zm-2 8h16M7 17v3m10-3v3M8 14h.01M16 14h.01",
  flight:
    "M10.5 3.5 12 3l1.5.5V10l7 4v2l-7-2v4l2 1.5V21L12 20l-3.5 1v-1.5l2-1.5v-4l-7 2v-2l7-4z",
  taxi: "M5 11l1.5-4.5A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.9 1.5L19 11m-14 0h14a1 1 0 0 1 1 1v4H4v-4a1 1 0 0 1 1-1Zm1 5v2m12-2v2M9 3h6M7.5 13.5h.01m9 0h.01",
};

export function ModeIcon({ mode, className = "h-5 w-5" }: { mode: Mode; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={PATHS[mode]} />
    </svg>
  );
}
