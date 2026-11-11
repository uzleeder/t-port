"use client";

import { useEffect, useId, useRef, useState } from "react";
import { clientApi } from "@/lib/api";
import type { Location, Page } from "@/lib/types";

interface Props {
  label: string;
  name: string;
  value: Location | null;
  onChange: (loc: Location | null) => void;
  placeholder?: string;
}

/** Accessible autocomplete (WAI-ARIA combobox pattern) backed by /api/v1/locations. */
export function LocationCombobox({ label, name, value, onChange, placeholder }: Props) {
  const id = useId();
  const listId = `${id}-list`;
  const [query, setQuery] = useState(value?.name ?? "");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Location[]>([]);
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep the visible text in sync when the parent changes the value (e.g. swap).
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    setQuery(value?.name ?? "");
  }

  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      try {
        const qs = new URLSearchParams({ limit: "8" });
        if (query.trim() && query !== value?.name) qs.set("q", query.trim());
        const page = await clientApi<Page<Location>>(`/api/v1/locations?${qs}`, {
          signal: ctrl.signal,
        });
        setItems(page.items);
        setActive(0);
        setError(null);
      } catch (e) {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : "Lookup failed");
      }
    }, 150);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [query, open, value?.name]);

  function choose(loc: Location) {
    onChange(loc);
    setQuery(loc.name);
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, Math.max(items.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && open && items[active]) {
      e.preventDefault();
      choose(items[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="relative">
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-muted">
        {label}
      </label>
      <input
        id={id}
        name={`${name}-text`}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && items[active] ? `${listId}-${items[active].id}` : undefined}
        autoComplete="off"
        placeholder={placeholder}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          if (value) onChange(null);
        }}
        onFocus={(e) => {
          e.target.select();
          setOpen(true);
        }}
        onBlur={() => {
          blurTimer.current = setTimeout(() => setOpen(false), 120);
        }}
        onKeyDown={onKeyDown}
        className="w-full rounded-xl border border-line bg-navy px-3 py-3 text-ink placeholder:text-muted/60 focus:border-blue"
      />
      <input type="hidden" name={name} value={value?.id ?? ""} />
      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-label={`${label} suggestions`}
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-xl border border-line bg-surface-2 py-1 shadow-xl shadow-black/40"
          onMouseDown={() => blurTimer.current && clearTimeout(blurTimer.current)}
        >
          {error && <li className="px-3 py-2 text-sm text-danger">{error}</li>}
          {!error && items.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted">No matching city in the current dataset.</li>
          )}
          {items.map((loc, i) => (
            <li
              key={loc.id}
              id={`${listId}-${loc.id}`}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(loc)}
              className={`cursor-pointer px-3 py-2 ${i === active ? "bg-blue/20" : ""}`}
            >
              <span className="font-medium">{loc.name}</span>
              <span className="ml-2 text-xs text-muted">{loc.region}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
