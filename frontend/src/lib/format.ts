import { ALL_MODES, type Mode, type SortKey } from "./types";

const MARKET_UTC_OFFSET_HOURS = 5; // Asia/Tashkent, no DST

export function formatMoney(amount: string | number, currency: string): string {
  const n = typeof amount === "string" ? Number(amount) : amount;
  if (!Number.isFinite(n)) return "—";
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n)} ${currency}`;
}

export function formatPriceRange(
  price: string,
  priceMax: string | null,
  currency: string,
): string {
  if (priceMax && priceMax !== price) {
    const hi = new Intl.NumberFormat("en-US").format(Number(priceMax));
    return `${formatMoney(price, currency).replace(` ${currency}`, "")}–${hi} ${currency}`;
  }
  return formatMoney(price, currency);
}

export function formatDuration(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes < 0) return "—";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  return `${h}h ${String(m).padStart(2, "0")}m`;
}

/** "2026-11-12T08:00:00+05:00" -> "08:00" (keeps the local wall time). */
export function localTime(iso: string | null): string {
  if (!iso) return "Flexible";
  const match = /T(\d{2}:\d{2})/.exec(iso);
  return match ? match[1] : "—";
}

/** Day offset between two local ISO timestamps (for "+1" overnight markers). */
export function dayOffset(fromIso: string | null, toIso: string | null): number {
  if (!fromIso || !toIso) return 0;
  const a = Date.UTC(...ymd(fromIso));
  const b = Date.UTC(...ymd(toIso));
  return Math.round((b - a) / 86_400_000);
}

function ymd(iso: string): [number, number, number] {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return [y, m - 1, d];
}

export function formatDateLong(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(y, m - 1, d)));
}

export function formatTimestamp(iso: string | null): string {
  if (!iso) return "unknown";
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Tashkent",
  }).format(new Date(iso));
}

/** Today's date in the market time zone as YYYY-MM-DD. */
export function marketToday(now: Date = new Date(), offsetDays = 0): string {
  const shifted = new Date(
    now.getTime() + MARKET_UTC_OFFSET_HOURS * 3_600_000 + offsetDays * 86_400_000,
  );
  return shifted.toISOString().slice(0, 10);
}

export const MODE_LABEL: Record<Mode, string> = {
  train: "Train",
  bus: "Bus",
  flight: "Flight",
  taxi: "Taxi",
};

export const SORT_LABEL: Record<SortKey, string> = {
  recommended: "Recommended",
  price: "Lowest price",
  duration: "Shortest duration",
  departure: "Earliest departure",
};

export interface SearchParams {
  origin: string;
  destination: string;
  date: string;
  modes: Mode[]; // empty = all
  sort: SortKey;
  page: number;
}

type RawParams = Record<string, string | string[] | undefined>;

function first(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
}

/** Parses /search URL params. A missing date (or "tomorrow"/"today") resolves in market time. */
export function parseSearchParams(raw: RawParams, now: Date = new Date()): SearchParams | null {
  const origin = first(raw.origin).toLowerCase();
  const destination = first(raw.destination).toLowerCase();
  const dateRaw = first(raw.date).toLowerCase();
  const date =
    dateRaw === "" || dateRaw === "tomorrow"
      ? marketToday(now, 1)
      : dateRaw === "today"
        ? marketToday(now)
        : dateRaw;
  if (!origin || !destination || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  const modes = first(raw.modes)
    .split(",")
    .map((m) => m.trim().toLowerCase())
    .filter((m): m is Mode => (ALL_MODES as string[]).includes(m));
  const sortRaw = first(raw.sort) as SortKey;
  const sort: SortKey = sortRaw in SORT_LABEL ? sortRaw : "recommended";
  const page = Math.max(1, Math.min(1000, Number.parseInt(first(raw.page) || "1", 10) || 1));
  return { origin, destination, date, modes: [...new Set(modes)], sort, page };
}

/** Builds the query string shared by the /search page URL and the API call. */
export function buildSearchQuery(p: Partial<SearchParams>): string {
  const qs = new URLSearchParams();
  if (p.origin) qs.set("origin", p.origin);
  if (p.destination) qs.set("destination", p.destination);
  if (p.date) qs.set("date", p.date);
  if (p.modes && p.modes.length > 0 && p.modes.length < ALL_MODES.length) {
    qs.set("modes", [...p.modes].sort().join(","));
  }
  if (p.sort && p.sort !== "recommended") qs.set("sort", p.sort);
  if (p.page && p.page > 1) qs.set("page", String(p.page));
  return qs.toString();
}

/** Only same-site relative paths are allowed as post-login redirects (prevents open redirects). */
export function safeNextPath(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return null;
  if (/[\r\n\t]/.test(next) || next.length > 512) return null;
  return next;
}

/** "3 min ago" style age; null without a reference time (keeps renders deterministic). */
export function timeAgo(iso: string | null | undefined, now: number | undefined): string | null {
  if (!iso || now === undefined) return null;
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}
