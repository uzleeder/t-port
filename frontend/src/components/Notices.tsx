import Link from "next/link";

export function DemoNotice() {
  return (
    <div
      role="note"
      className="rounded-xl border border-gold/50 bg-gold/5 px-4 py-3 text-sm text-gold"
    >
      <strong>Demonstration data.</strong> Schedules, fares and operators shown are simulated and
      are not real travel information. T-Port is a planning tool and does not sell tickets.
    </div>
  );
}

export function StateMessage({
  title,
  children,
  tone = "neutral",
  action,
}: {
  title: string;
  children?: React.ReactNode;
  tone?: "neutral" | "error";
  action?: { href: string; label: string };
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`rounded-2xl border border-dashed px-6 py-10 text-center ${
        tone === "error" ? "border-danger/60" : "border-line"
      } bg-surface`}
    >
      <h2 className={`text-lg font-semibold ${tone === "error" ? "text-danger" : ""}`}>{title}</h2>
      {children && <div className="mx-auto mt-2 max-w-prose text-muted">{children}</div>}
      {action && (
        <Link
          href={action.href}
          className="mt-4 inline-block rounded-xl border border-line px-4 py-2 text-sm hover:border-blue"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}
