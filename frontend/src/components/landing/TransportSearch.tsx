"use client";

import { useLang } from "../LanguageSelect";
import { SearchForm, type SearchLabels } from "../SearchForm";
import { I18N, type Key } from "@/lib/i18n";

/** The real journey search (autocomplete, swap, dates), with landing categories and translated labels. */
export function TransportSearch() {
  const lang = useLang();
  const t = (k: Key) => I18N[k][lang];
  const labels: SearchLabels = {
    title: t("search.title"),
    modes: t("search.modes"),
    from: t("search.from"),
    to: t("search.to"),
    date: t("search.date"),
    placeholder: t("search.placeholder"),
    swap: t("search.swap"),
    submit: t("search.submit"),
    searching: t("search.searching"),
    errPick: t("search.errPick"),
    errSame: t("search.errSame"),
    errDate: t("search.errDate"),
    errModes: t("search.errModes"),
    all: t("search.all"),
    multimodal: t("search.multimodal"),
    multimodalHint: t("search.multimodalHint"),
    mode: { train: t("search.train"), bus: t("search.bus"), flight: t("search.flight"), taxi: t("search.taxi") },
  };
  return <SearchForm categories labels={labels} />;
}
