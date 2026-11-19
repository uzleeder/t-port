"use client";

import { useState } from "react";
import { Icon } from "./Icons";

/** Shares the current page with the system share sheet, or copies its link. */
export function ShareButton({ title }: { title: string }) {
  const [copied, setCopied] = useState(false);

  async function share() {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Share sheet dismissed or clipboard blocked: nothing to do.
    }
  }

  return (
    <button
      type="button"
      onClick={share}
      className="flex h-11 w-11 items-center justify-center rounded-full bg-card shadow-soft hover:bg-surface-2"
    >
      <Icon name={copied ? "check" : "share"} />
      <span className="sr-only">{copied ? "Link copied" : "Share this journey"}</span>
    </button>
  );
}
