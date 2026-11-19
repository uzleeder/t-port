import { Icon } from "./Icons";
import { auraRegionUrl } from "@/lib/aura";

/** "More photos of X on AURA" — an outbound link only; nothing from AURA is embedded. */
export function AuraLink({ place, region, className = "" }: { place: string; region: string; className?: string }) {
  const href = auraRegionUrl(region);
  if (!href) return null;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-block text-sm font-medium text-sky hover:underline ${className}`}
    >
      More photos of {place} on{" "}
      <span className="whitespace-nowrap">
        AURA <Icon name="arrowUpRight" className="inline h-3.5 w-3.5 align-[-2px]" />
      </span>
      <span className="sr-only">(opens aura.uz in a new tab, in Uzbek)</span>
    </a>
  );
}
