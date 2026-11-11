"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { clientApi } from "@/lib/api";
import { notifySessionChanged, useMe } from "@/lib/session";

export function AccountNav() {
  const [state, retry] = useMe();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  if (state.status === "loading") {
    return <span className="inline-block h-8 w-24 animate-pulse rounded-lg bg-surface" aria-hidden="true" />;
  }
  if (state.status === "error") {
    return (
      <button type="button" onClick={retry} title={state.message}
        className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted hover:border-blue hover:text-ink">
        Account unavailable · Retry
      </button>
    );
  }
  if (state.status !== "ready") {
    return (
      <div className="flex items-center gap-2 text-sm">
        <Link href="/login" className="rounded-lg px-3 py-1.5 text-muted hover:text-ink">
          Sign in
        </Link>
        <Link href="/register" className="rounded-lg bg-blue px-3 py-1.5 font-medium text-white hover:bg-blue-hover">
          Create account
        </Link>
      </div>
    );
  }

  async function logout() {
    setBusy(true);
    try {
      await clientApi("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // Even if the server call fails, treat the user as signed out locally.
    } finally {
      notifySessionChanged();
      setBusy(false);
      router.push("/");
      router.refresh();
    }
  }

  const name = state.me.user.display_name || state.me.user.email.split("@")[0];
  return (
    <div className="flex items-center gap-2 text-sm">
      <Link href="/dashboard" className="rounded-lg px-3 py-1.5 text-muted hover:text-ink">
        <span className="sr-only">Dashboard for </span>
        {name}
        {state.me.saved_count > 0 && (
          <span className="ml-2 rounded-full bg-gold/15 px-2 py-0.5 text-xs text-gold">
            {state.me.saved_count} saved
          </span>
        )}
      </Link>
      <button
        type="button"
        onClick={logout}
        disabled={busy}
        className="rounded-lg border border-line px-3 py-1.5 text-muted hover:border-blue hover:text-ink disabled:opacity-60"
      >
        {busy ? "Signing out…" : "Sign out"}
      </button>
    </div>
  );
}
