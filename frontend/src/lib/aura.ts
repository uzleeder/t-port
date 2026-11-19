/**
 * Links to AURA (aura.uz), Uzbekistan's state photo and video archive. T-Port only links to it:
 * AURA does not publish a licence for reuse, so none of its photos are shown on T-Port itself.
 * `https://aura.uz/content?region=N` opens AURA's gallery for one region (checked 2026-11-18).
 */

export const AURA_HOME = "https://aura.uz/";

/** AURA's region ids, by the region names T-Port's locations use (English and Uzbek). */
const REGIONS: [id: number, label: string, names: string[]][] = [
  [10, "Tashkent", ["tashkent city", "toshkent shahri"]],
  [11, "Tashkent Region", ["tashkent region", "toshkent viloyati"]],
  [7, "Samarkand Region", ["samarkand region", "samarqand viloyati"]],
  [2, "Bukhara Region", ["bukhara region", "buxoro viloyati"]],
  [13, "Khorezm Region", ["khorezm region", "xorazm viloyati"]],
  [14, "Karakalpakstan", ["republic of karakalpakstan", "qoraqalpogiston respublikasi"]],
  [5, "Navoiy Region", ["navoiy region", "navoiy viloyati"]],
  [4, "Kashkadarya Region", ["kashkadarya region", "qashqadaryo viloyati"]],
  [8, "Surkhandarya Region", ["surkhandarya region", "surxondaryo viloyati"]],
  [3, "Jizzakh Region", ["jizzakh region", "jizzax viloyati"]],
  [9, "Syrdarya Region", ["syrdarya region", "sirdaryo viloyati"]],
  [1, "Andijan Region", ["andijan region", "andijon viloyati"]],
  [6, "Namangan Region", ["namangan region", "namangan viloyati", "namangan shahri"]],
  [12, "Fergana Region", ["fergana region", "fargona viloyati"]],
];

const norm = (s: string) =>
  s
    .toLowerCase()
    .replace(/['ʻʼ‘’`]/g, "")
    .replace(/\s+/g, " ")
    .trim();

const BY_NAME = new Map(REGIONS.flatMap(([id, , names]) => names.map((n) => [n, id] as const)));

const url = (id: number) => `https://aura.uz/content?region=${id}`;

/** AURA gallery for the region a T-Port location belongs to, or null when there is no match. */
export function auraRegionUrl(region: string): string | null {
  const id = BY_NAME.get(norm(region));
  return id ? url(id) : null;
}

/** Every region gallery, for the credits page. */
export const AURA_REGIONS = REGIONS.map(([id, label]) => ({ label, href: url(id) }));
