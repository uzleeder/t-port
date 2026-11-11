import type { FreshnessLevel } from "@/lib/types";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "blue" | "gold" | "danger" | "success";
}) {
  const tones = {
    neutral: "border-line text-muted",
    blue: "border-blue/60 text-ink bg-blue/10",
    gold: "border-gold/60 text-gold",
    danger: "border-danger/60 text-danger",
    success: "border-success/50 text-success",
  } as const;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

const FRESHNESS_TEXT: Record<FreshnessLevel, string> = {
  fresh: "Data current",
  stale: "Data may be outdated",
  expired: "Data expired",
};

export function FreshnessBadge({ level }: { level: FreshnessLevel }) {
  const tone = level === "fresh" ? "success" : "danger";
  return (
    <Badge tone={tone}>
      <span aria-hidden="true">●</span> {FRESHNESS_TEXT[level]}
    </Badge>
  );
}

export function DemoBadge() {
  return (
    <Badge tone="gold">
      <abbr title="Simulated data — not real schedules or fares" className="no-underline">
        Demo data
      </abbr>
    </Badge>
  );
}
