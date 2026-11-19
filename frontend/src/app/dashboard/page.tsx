import type { Metadata } from "next";
import { Dashboard } from "@/components/Dashboard";

export const metadata: Metadata = { title: "My Trips" };

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-[80rem] px-3 py-4 sm:px-6 lg:px-0 lg:py-0">
      <Dashboard />
    </div>
  );
}
