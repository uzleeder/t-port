"use client";

import { useId, useState } from "react";
import { ApiError, clientApi } from "@/lib/api";
import { MODE_LABEL, SORT_LABEL } from "@/lib/format";
import { type Preferences, usePreferences } from "@/lib/preferences";
import { ALL_MODES, type Mode, type SortKey } from "@/lib/types";

/** Search defaults for new searches. Stored per account; enumerated values only. */
export function PreferencesForm() {
  const id = useId();
  const [prefs, setPrefs] = usePreferences();
  const [status, setStatus] = useState<{ kind: "idle" | "saving" | "saved" | "error"; message?: string }>({
    kind: "idle",
  });

  if (!prefs) {
    return <div role="status" aria-label="Loading preferences" className="mt-4 h-24 animate-pulse rounded-2xl bg-surface" />;
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const modes = ALL_MODES.filter((m) => form.get(`mode-${m}`) === "on");
    const prefer = ALL_MODES.filter((m) => form.get(`prefer-${m}`) === "on");
    const price = String(form.get("max_price") ?? "").replace(/[\s,]/g, "");
    if (modes.length === 0) {
      setStatus({ kind: "error", message: "Keep at least one transport mode." });
      return;
    }
    const body = {
      modes: modes.length === ALL_MODES.length ? [] : modes,
      prefer_modes: prefer.filter((m) => modes.includes(m)),
      sort: String(form.get("sort")) as SortKey,
      max_transfers: Number(form.get("max_transfers")),
      max_price: price || null,
    };
    setStatus({ kind: "saving" });
    try {
      const saved = await clientApi<Preferences>("/api/v1/me/preferences", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setPrefs(saved);
      setStatus({ kind: "saved" });
    } catch (err) {
      setStatus({ kind: "error", message: err instanceof ApiError ? err.message : "Could not save preferences." });
    }
  }

  const active = (m: Mode) => prefs.modes.length === 0 || prefs.modes.includes(m);
  return (
    <form key={prefs.updated_at ?? "defaults"} onSubmit={submit} className="mt-4 space-y-4 rounded-2xl border border-line bg-surface p-4">
      <fieldset>
        <legend className="text-sm font-medium">Transport modes to search</legend>
        <div className="mt-2 flex flex-wrap gap-3">
          {ALL_MODES.map((m) => (
            <label key={m} className="flex items-center gap-2 text-sm">
              <input type="checkbox" name={`mode-${m}`} defaultChecked={active(m)} className="h-4 w-4 accent-[var(--color-blue)]" />
              {MODE_LABEL[m]}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="text-sm font-medium">Prefer (ranks them higher, never hides others)</legend>
        <div className="mt-2 flex flex-wrap gap-3">
          {ALL_MODES.map((m) => (
            <label key={m} className="flex items-center gap-2 text-sm">
              <input type="checkbox" name={`prefer-${m}`} defaultChecked={prefs.prefer_modes.includes(m)} className="h-4 w-4 accent-[var(--color-blue)]" />
              {MODE_LABEL[m]}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap gap-4">
        <label htmlFor={`${id}-sort`} className="flex flex-col gap-1 text-sm">
          Sort results by
          <select id={`${id}-sort`} name="sort" defaultValue={prefs.sort} className="rounded-lg border border-line bg-navy px-3 py-2 text-ink">
            {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
              <option key={k} value={k}>{SORT_LABEL[k]}</option>
            ))}
          </select>
        </label>
        <label htmlFor={`${id}-changes`} className="flex flex-col gap-1 text-sm">
          Changes
          <select id={`${id}-changes`} name="max_transfers" defaultValue={String(prefs.max_transfers)} className="rounded-lg border border-line bg-navy px-3 py-2 text-ink">
            <option value="0">Direct only</option>
            <option value="1">Up to 1 change</option>
            <option value="2">Up to 2 changes</option>
          </select>
        </label>
        <label htmlFor={`${id}-price`} className="flex flex-col gap-1 text-sm">
          Max price (UZS)
          <input id={`${id}-price`} name="max_price" type="number" inputMode="numeric" min={1000} step={1000}
            defaultValue={prefs.max_price ? String(Number(prefs.max_price)) : ""} placeholder="Any"
            className="w-40 rounded-lg border border-line bg-navy px-3 py-2 text-ink" />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={status.kind === "saving"}
          className="rounded-xl bg-blue px-4 py-2 text-sm font-semibold text-white hover:bg-blue-hover disabled:opacity-60">
          {status.kind === "saving" ? "Saving…" : "Save preferences"}
        </button>
        <p role="status" aria-live="polite" className={`text-sm ${status.kind === "error" ? "text-danger" : "text-muted"}`}>
          {status.kind === "saved" ? "Saved. New searches start with these settings." : status.message}
        </p>
      </div>
    </form>
  );
}
