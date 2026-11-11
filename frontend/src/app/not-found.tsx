import { StateMessage } from "@/components/Notices";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <StateMessage title="Page not found" action={{ href: "/", label: "Go to the homepage" }}>
        <p>The page you were looking for doesn&apos;t exist.</p>
      </StateMessage>
    </div>
  );
}
