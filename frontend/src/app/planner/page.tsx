import type { Metadata } from "next";
import { DemoNotice } from "@/components/Notices";
import { PageBanner } from "@/components/PageBanner";
import { Planner } from "@/components/Planner";

export const metadata: Metadata = { title: "T-AI travel assistant" };

export default function PlannerPage() {
  return (
    <div className="mx-auto max-w-[80rem] space-y-5 px-3 py-4 sm:px-6 lg:px-0 lg:py-0">
      <PageBanner
        icon="ai"
        title="T-AI"
        accent="Travel Assistant"
        subtitle="Plans your trips and knows Uzbekistan's 14 regions and 28 places to visit."
      />
      <DemoNotice />
      <Planner />
    </div>
  );
}
