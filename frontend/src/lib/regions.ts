/**
 * Uzbekistan's 14 regions for the Explore page; each has a landmark and a destination from
 * EXPLORE_PLACES and its own page at /explore/[key].
 */
import type { IconName } from "@/components/Icons";
import { EXPLORE_PLACES, type ExplorePlace } from "./explore";

export interface UzRegion {
  key: string;
  name: string;
  nameUz: string;
  /** Region name as T-Port's locations use it (also picks the AURA region). */
  region: string;
  icon: IconName;
}

export const UZ_REGIONS: UzRegion[] = [
  { key: "tashkent-city", name: "Tashkent", nameUz: "Toshkent shahri", region: "Tashkent City", icon: "city" },
  { key: "tashkent-region", name: "Tashkent Region", nameUz: "Toshkent viloyati", region: "Tashkent Region", icon: "mountain" },
  { key: "samarkand", name: "Samarkand", nameUz: "Samarqand viloyati", region: "Samarkand Region", icon: "dome" },
  { key: "bukhara", name: "Bukhara", nameUz: "Buxoro viloyati", region: "Bukhara Region", icon: "tower" },
  { key: "khorezm", name: "Khorezm", nameUz: "Xorazm viloyati", region: "Khorezm Region", icon: "fortress" },
  { key: "fergana", name: "Fergana", nameUz: "Fargʻona viloyati", region: "Fergana Region", icon: "flower" },
  { key: "andijan", name: "Andijan", nameUz: "Andijon viloyati", region: "Andijan Region", icon: "leaf" },
  { key: "namangan", name: "Namangan", nameUz: "Namangan viloyati", region: "Namangan Region", icon: "flower" },
  { key: "kashkadarya", name: "Kashkadarya", nameUz: "Qashqadaryo viloyati", region: "Kashkadarya Region", icon: "fortress" },
  { key: "surkhandarya", name: "Surkhandarya", nameUz: "Surxondaryo viloyati", region: "Surkhandarya Region", icon: "sun" },
  { key: "jizzakh", name: "Jizzakh", nameUz: "Jizzax viloyati", region: "Jizzakh Region", icon: "mountain" },
  { key: "syrdarya", name: "Syrdarya", nameUz: "Sirdaryo viloyati", region: "Syrdarya Region", icon: "waves" },
  { key: "navoi", name: "Navoi", nameUz: "Navoiy viloyati", region: "Navoiy Region", icon: "dome" },
  { key: "karakalpakstan", name: "Karakalpakstan", nameUz: "Qoraqalpogʻiston Respublikasi", region: "Republic of Karakalpakstan", icon: "waves" },
];

export const regionByKey = (key: string) => UZ_REGIONS.find((r) => r.key === key) ?? null;

export const regionPlaces = (key: string): ExplorePlace[] => EXPLORE_PLACES.filter((p) => p.regionKey === key);

export const regionHref = (key: string) => `/explore/${key}`;
export const placeHref = (p: ExplorePlace) => `${regionHref(p.regionKey)}#${p.key}`;
