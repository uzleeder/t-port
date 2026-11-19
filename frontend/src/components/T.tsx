import { fill, I18N, LANGS, type Key, type Tr } from "@/lib/i18n";

/**
 * Translated text. Renders every language; CSS (globals.css, "i18n") shows only the one matching
 * <html lang>, so it works in server components and switches without re-rendering.
 */
export function T({ k, tr, vars }: { k?: Key; tr?: Tr; vars?: Record<string, string | number> }) {
  const text = tr ?? (k ? I18N[k] : null);
  if (!text) return null;
  return (
    <>
      {LANGS.map((l) => (
        <span key={l} data-l={l} lang={l}>
          {fill(text[l], vars)}
        </span>
      ))}
    </>
  );
}
