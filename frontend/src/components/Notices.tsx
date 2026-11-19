import Link from "next/link";

export function DemoNotice() {
  return (
    <div
      role="note"
      className="rounded-2xl bg-amber/15 px-4 py-3 text-sm text-gold"
    >
      <strong>Demonstration data.</strong> Schedules, fares and operators shown are simulated and
      are not real travel information. T-Port is a planning tool and does not sell tickets.
    </div>
  );
}

/** Explains the reliability labels used on journey cards. */
export function LabelsHelp() {
  return (
    <details className="rounded-2xl bg-surface px-4 py-2.5 text-sm text-muted shadow-soft">
      <summary className="cursor-pointer text-ink">How to read prices and labels</summary>
      <dl className="mt-2 grid gap-x-4 gap-y-1 sm:grid-cols-[auto_1fr]">
        <dt className="text-ink">Confirmed price</dt>
        <dd>A current price reported live by the provider.</dd>
        <dt className="text-ink">Indicative price</dt>
        <dd>A published fare or an earlier price; the operator&apos;s final price may differ.</dd>
        <dt className="text-ink">Estimate</dt>
        <dd>A range, e.g. for taxis. Agree the fare before you travel.</dd>
        <dt className="text-ink">Demo data</dt>
        <dd>Simulated for this pilot. Not real schedules or fares, and never bookable.</dd>
        <dt className="text-ink">Data may be outdated</dt>
        <dd>The source hasn&apos;t been refreshed recently. Check with the operator before travelling.</dd>
        <dt className="text-ink">Update time unknown</dt>
        <dd>The source didn&apos;t say when it last changed. Treat it like outdated data.</dd>
      </dl>
    </details>
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
      className={`rounded-3xl px-6 py-10 text-center shadow-soft ${
        tone === "error" ? "border border-danger/40" : ""
      } bg-surface`}
    >
      <h2 className={`text-lg font-semibold ${tone === "error" ? "text-danger" : ""}`}>{title}</h2>
      {children && <div className="mx-auto mt-2 max-w-prose text-muted">{children}</div>}
      {action && (
        <Link
          href={action.href}
          className="mt-4 inline-block rounded-full bg-blue px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-hover"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}
