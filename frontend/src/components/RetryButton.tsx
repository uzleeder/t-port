"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

/** Re-runs the current server render (e.g. a search after a provider failure). */
export function RetryButton({ label = "Try again" }: { label?: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <button
      type="button"
      onClick={() => start(() => router.refresh())}
      disabled={pending}
      className="rounded-lg border border-line px-3 py-1.5 text-sm text-ink hover:border-blue disabled:opacity-60"
    >
      {pending ? "Retrying…" : label}
    </button>
  );
}
