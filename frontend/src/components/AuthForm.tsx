"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, clientApi } from "@/lib/api";
import { safeNextPath } from "@/lib/format";
import { notifySessionChanged } from "@/lib/session";

export function AuthForm({ mode, next }: { mode: "login" | "register"; next?: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);
  const isRegister = mode === "register";

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // Read from the DOM so text typed before hydration is never lost.
    const form = new FormData(e.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    const name = String(form.get("display_name") ?? "").trim();
    setError(null);
    setFieldErrors({});
    setPending(true);
    try {
      await clientApi(`/api/v1/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify(
          isRegister ? { email, password, display_name: name || null } : { email, password },
        ),
      });
      notifySessionChanged();
      router.push(safeNextPath(next) ?? "/dashboard");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        setFieldErrors(
          Object.fromEntries(err.details.filter((d) => d.field).map((d) => [d.field as string, d.message])),
        );
      } else {
        setError("Something went wrong. Please try again.");
      }
      setPending(false);
    }
  }

  const input =
    "w-full rounded-xl border border-line bg-navy px-3 py-3 text-ink placeholder:text-muted/60 focus:border-blue";

  return (
    // method="post": if JS hasn't loaded, a native submit must never put the password in the URL.
    <form method="post" onSubmit={submit} noValidate className="space-y-4"
      aria-describedby={error ? "auth-error" : undefined}>
      {isRegister && (
        <div>
          <label htmlFor="name" className="mb-1 block text-sm text-muted">
            Name <span className="text-muted/70">(optional)</span>
          </label>
          <input id="name" name="display_name" maxLength={80}
            autoComplete="name" className={input} />
        </div>
      )}
      <div>
        <label htmlFor="email" className="mb-1 block text-sm text-muted">Email</label>
        <input id="email" name="email" type="email" required
          autoComplete="email" maxLength={254} aria-invalid={!!fieldErrors.email}
          aria-describedby={fieldErrors.email ? "email-err" : undefined} className={input} />
        {fieldErrors.email && <p id="email-err" className="mt-1 text-sm text-danger">{fieldErrors.email}</p>}
      </div>
      <div>
        <label htmlFor="password" className="mb-1 block text-sm text-muted">Password</label>
        <input id="password" name="password" type="password" required maxLength={128}
          autoComplete={isRegister ? "new-password" : "current-password"}
          aria-invalid={!!fieldErrors.password}
          aria-describedby={isRegister ? "pw-hint" : fieldErrors.password ? "pw-err" : undefined}
          className={input} />
        {isRegister && !fieldErrors.password && (
          <p id="pw-hint" className="mt-1 text-xs text-muted">At least 10 characters.</p>
        )}
        {fieldErrors.password && <p id="pw-err" className="mt-1 text-sm text-danger">{fieldErrors.password}</p>}
      </div>
      {error && (
        <p id="auth-error" role="alert" className="rounded-lg border border-danger/50 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" disabled={pending}
        className="w-full rounded-xl bg-blue px-5 py-3 font-semibold text-white hover:bg-blue-hover disabled:opacity-60">
        {pending ? "Please wait…" : isRegister ? "Create account" : "Sign in"}
      </button>
      <p className="text-center text-sm text-muted">
        {isRegister ? "Already have an account? " : "New to T-Port? "}
        <Link
          href={`${isRegister ? "/login" : "/register"}${safeNextPath(next) ? `?next=${encodeURIComponent(next!)}` : ""}`}
          className="text-blue hover:underline"
        >
          {isRegister ? "Sign in" : "Create an account"}
        </Link>
      </p>
    </form>
  );
}
