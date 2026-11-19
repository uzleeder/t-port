import type { Metadata } from "next";
import { Profile } from "@/components/Profile";

export const metadata: Metadata = { title: "Profile & settings" };

export default function ProfilePage() {
  return (
    <div className="mx-auto max-w-[80rem] px-3 py-4 sm:px-6 lg:px-0 lg:py-0">
      <Profile />
    </div>
  );
}
