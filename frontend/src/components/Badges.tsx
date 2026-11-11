import type { FreshnessLevel, PriceType } from "@/lib/types";

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
  unknown: "Update time unknown",
  expired: "Data expired",
};

export function FreshnessBadge({ level, label }: { level: FreshnessLevel; label?: string }) {
  const tone = level === "fresh" ? "success" : "danger";
  return (
    <Badge tone={tone}>
      <span aria-hidden="true">●</span> {label ? `${label}: ` : ""}
      {FRESHNESS_TEXT[level]}
    </Badge>
  );
}

export const PRICE_TYPE_TEXT: Record<PriceType, { label: string; help: string }> = {
  confirmed: { label: "Confirmed price", help: "A current price reported live by the provider." },
  indicative: {
    label: "Indicative price",
    help: "A published fare or an earlier price. The operator's final price may differ.",
  },
  estimated: { label: "Estimate", help: "An estimated range, e.g. for taxis. Agree the fare before travel." },
  demo: { label: "Demo price", help: "Simulated. Not a real fare." },
};

export function PriceTypeBadge({ type }: { type: PriceType }) {
  const tone = type === "confirmed" ? "success" : type === "demo" ? "gold" : "neutral";
  return (
    <Badge tone={tone}>
      <abbr title={PRICE_TYPE_TEXT[type].help} className="no-underline">
        {PRICE_TYPE_TEXT[type].label}
      </abbr>
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
