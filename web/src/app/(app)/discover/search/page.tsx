import type { Metadata } from "next";

import { SearchScreen } from "@/components/search/SearchScreen";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("search.title") };

/** Search (T-6.6). T-6.5's feed row links here (P-443). */
export default function SearchPage() {
  return <SearchScreen />;
}
