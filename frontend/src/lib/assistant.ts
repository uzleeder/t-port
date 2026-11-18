import type { SearchResponse } from "./types";

export interface InterpretResponse {
  engine: string;
  fallback_used: boolean;
  intent: {
    origin_id: string | null;
    destination_id: string | null;
    travel_date: string | null;
    modes: string[];
    budget_preference: string;
    max_price: string | null;
    time_preference: string;
    sort: string;
    depart_after: string | null;
    depart_before: string | null;
    arrive_before: string | null;
    max_transfers: number;
    transfer_preference: string;
    prefer_modes: string[];
    compare_modes: boolean;
  };
  needs_clarification: boolean;
  clarification: string | null;
  search_query: string | null;
  explanation: string | null;
  results: SearchResponse | null;
  disclaimer: string;
}

/** Short, factual chips describing how the request was understood (validated values only). */
export function understoodAs(intent: InterpretResponse["intent"]): string[] {
  const chips: string[] = [];
  if (intent.modes.length) chips.push(intent.modes.join(" or "));
  if (intent.prefer_modes.length) chips.push(`prefer ${intent.prefer_modes.join(" or ")}`);
  if (intent.arrive_before) chips.push(`arrive by ${intent.arrive_before}`);
  if (intent.depart_after) chips.push(`leave after ${intent.depart_after}`);
  if (intent.depart_before) chips.push(`leave before ${intent.depart_before}`);
  if (intent.max_transfers === 0) chips.push("direct only");
  else if (intent.transfer_preference === "fewest") chips.push("fewest changes");
  else if (intent.max_transfers === 2) chips.push("up to 2 changes");
  if (intent.max_price) chips.push(`max ${Number(intent.max_price).toLocaleString("en-US")} UZS`);
  if (intent.compare_modes) chips.push("compare modes");
  return chips;
}
