import type { Metadata } from "next";
import { Suspense } from "react";

import { DiscoverScreen } from "@/components/discover/DiscoverScreen";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("discover.title") };

/**
 * Discover (T-6.5), inside the app shell's `<main>` (T-5.6). The deck reads
 * its filters from the URL, where T-6.9's sheet writes them, so it waits for
 * the search params under a Suspense boundary.
 */
export default function DiscoverPage() {
  return (
    <Suspense>
      <DiscoverScreen />
    </Suspense>
  );
}
