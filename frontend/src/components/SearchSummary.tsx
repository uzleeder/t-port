"use client";

import { useState, type ReactNode } from "react";
import { Icon } from "./Icons";

/** From / To / Date summary with "Edit search", which reveals the full form passed as children. */
export function SearchSummary({
  from,
  to,
  date,
  children,
}: {
  from: string;
  to: string;
  date: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 rounded-3xl bg-surface p-3 shadow-soft">
        <Field icon="compass" label="From" value={from} />
        <Icon name="route" className="hidden h-5 w-5 text-sky sm:block" />
        <Field icon="compass" label="To" value={to} />
        <Field icon="calendar" label="Travel date" value={date} />
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          className="ml-auto flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold ring-1 ring-blue/60 hover:bg-blue/15"
        >
          <Icon name="search" className="h-4 w-4" /> {open ? "Close" : "Edit search"}
        </button>
      </div>
      {open && children}
    </div>
  );
}

function Field({ icon, label, value }: { icon: "compass" | "calendar"; label: string; value: string }) {
  return (
    <div className="flex min-w-[9rem] flex-1 items-center gap-3 rounded-2xl bg-card px-4 py-2.5">
      <Icon name={icon} className="h-5 w-5 shrink-0 text-sky" />
      <span className="min-w-0 leading-tight">
        <span className="block text-xs text-muted">{label}</span>
        <span className="block truncate font-semibold">{value}</span>
      </span>
    </div>
  );
}
