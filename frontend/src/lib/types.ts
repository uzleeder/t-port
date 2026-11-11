// Mirrors the FastAPI response schemas (see /docs on the API).

export type Mode = "train" | "bus" | "flight" | "taxi";
export const ALL_MODES: Mode[] = ["train", "bus", "flight", "taxi"];
export type SortKey = "recommended" | "price" | "duration" | "departure";
export type FreshnessLevel = "fresh" | "stale" | "unknown" | "expired";
export type PriceType = "confirmed" | "indicative" | "estimated" | "demo";

export interface Location {
  id: string;
  name: string;
  country_code: string;
  region: string;
  timezone: string;
  latitude: number | null;
  longitude: number | null;
  aliases: string[];
}

export interface Station {
  id: string;
  name: string;
  kind: string;
  code: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Fare {
  name: string;
  price: string;
  price_max: string | null;
  currency: string;
  is_estimate: boolean;
}

export interface Leg {
  mode: Mode;
  operator: string;
  service_code: string;
  schedule_type: "scheduled" | "on_demand";
  origin: Station;
  destination: Station;
  departure_utc: string | null;
  arrival_utc: string | null;
  departure_local: string | null;
  arrival_local: string | null;
  duration_minutes: number;
  fares: Fare[];
  freshness: FreshnessLevel;
  timetable_freshness: FreshnessLevel;
  price_freshness: FreshnessLevel;
  price_type: PriceType;
  provider: Provider | null;
  retrieved_at: string;
  source_updated_at: string | null;
}

export interface Journey {
  id: string;
  modes: Mode[];
  transfers: number;
  price: string;
  price_max: string | null;
  currency: string;
  is_price_estimate: boolean;
  travel_minutes: number;
  total_minutes: number;
  departure_utc: string | null;
  arrival_utc: string | null;
  freshness: FreshnessLevel;
  is_demo: boolean;
  booking_url: string | null;
  notes: string[];
  legs: Leg[];
  transfer_checks?: TransferCheck[];
  price_type: PriceType;
  booking_note: string | null;
}

export interface TransferCheck {
  at_location_id: string;
  from_station: string;
  to_station: string;
  station_change: boolean;
  connection_minutes: number;
  minimum_minutes: number;
  guaranteed: boolean;
}

export interface Provider {
  id: string;
  name: string;
  is_demo: boolean;
  attribution: string;
}

export interface Source {
  provider: Provider;
  ok: boolean;
  retrieved_at: string | null;
  freshness: FreshnessLevel | null;
  error: string | null;
}

export interface SearchResponse {
  query: {
    origin: Location;
    destination: Location;
    date: string;
    modes: Mode[];
    sort: SortKey;
    max_price: string | null;
  };
  items: Journey[];
  total: number;
  page: number;
  page_size: number;
  summary: {
    cheapest_id: string | null;
    fastest_id: string | null;
    earliest_id: string | null;
    min_price: string | null;
    max_price: string | null;
    count_by_mode: Record<string, number>;
  };
  sources: Source[];
  excluded: {
    missing_offers: number;
    expired_data: number;
    already_departed: number;
    over_budget: number;
    outside_time_window: number;
  };
  warnings: string[];
  contains_demo_data: boolean;
}

export interface JourneyDetail {
  journey: Journey;
  origin: Location;
  destination: Location;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: { field?: string; message: string }[] };
}
