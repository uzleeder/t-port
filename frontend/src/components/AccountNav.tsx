"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { clientApi } from "@/lib/api";
import { notifySessionChanged, useMe } from "@/lib/session";
import { Avatar, displayName } from "./Avatar";
import { T } from "./T";

export function AccountNav() {
  const [state, retry] = useMe();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  if (state.status === "loading") {
    return <span className="inline-block h-9 w-24 animate-pulse rounded-full bg-surface" aria-hidden="true" />;
  }
  if (state.status === "error") {
    return (
      <button type="button" onClick={retry} title={state.message}
        className="rounded-full border border-line px-3 py-1.5 text-sm text-muted hover:border-blue hover:text-ink">
        Account unavailable · Retry
      </button>
    );
  }
  if (state.status !== "ready") {
    return (
      <div className="flex items-center gap-2 text-sm">
        <Link href="/login" className="whitespace-nowrap rounded-full px-2 py-1.5 text-muted hover:text-ink sm:px-3">
          <T k="nav.signIn" />
        </Link>
        <Link href="/register" className="whitespace-nowrap rounded-full bg-blue px-3 py-2 font-medium text-white hover:bg-blue-hover sm:px-4">
          <T k="nav.getStarted" />
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

  const name = displayName(state.me.user);
  return (
    <div className="flex items-center gap-2 text-sm">
      <Link href="/dashboard" className="flex shrink-0 items-center gap-2 rounded-full bg-surface p-1 text-ink shadow-soft hover:bg-card sm:pr-3">
        <Avatar user={state.me.user} size={28} />
        <span className="sr-only">Dashboard for </span>
        <span className="hidden max-w-[9rem] truncate sm:inline">{name}</span>
        {state.me.saved_count > 0 && (
          <span className="hidden rounded-full bg-amber/25 px-2 py-0.5 text-xs text-gold sm:inline">
            {state.me.saved_count} saved
          </span>
        )}
      </Link>
      <button
        type="button"
        onClick={logout}
        disabled={busy}
        className="rounded-full border border-line px-3 py-1.5 text-muted hover:border-blue hover:text-ink disabled:opacity-60"
      >
        {busy ? "Signing out…" : "Sign out"}
      </button>
    </div>
  );
}
