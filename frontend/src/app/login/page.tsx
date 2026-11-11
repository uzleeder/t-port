import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthFormWithNext, AuthShell } from "@/components/AuthShell";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage({ searchParams }: PageProps<"/login">) {
  return (
    <AuthShell title="Sign in" subtitle="Access your saved journeys and recent searches.">
      <Suspense fallback={<div className="h-64 animate-pulse rounded-xl bg-navy" />}>
        <AuthFormWithNext searchParams={searchParams} mode="login" />
      </Suspense>
    </AuthShell>
  );
}
