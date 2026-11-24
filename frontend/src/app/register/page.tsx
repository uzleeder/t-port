import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthFormWithNext, AuthShell } from "@/components/AuthShell";

export const metadata: Metadata = { title: "Create account" };

export default function RegisterPage({ searchParams }: PageProps<"/register">) {
  return (
    <AuthShell title="Create account" subtitle="Save journeys and pick up where you left off.">
      <Suspense fallback={<div className="h-64 animate-pulse rounded-3xl bg-surface" />}>
        <AuthFormWithNext searchParams={searchParams} mode="register" />
      </Suspense>
    </AuthShell>
  );
}
