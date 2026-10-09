import type { Metadata } from "next";

import { IncomingRequests } from "@/components/album/IncomingRequests";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("albumRequests.title") };

/**
 * The requests to see your private album (T-8.8, D-790), inside the app
 * shell's `<main>` (T-5.6) and beneath `/you`, a nonce route (D-541). Linked
 * from the You tab's settings rows (T-9.8).
 */
export default function AlbumRequestsPage() {
  return <IncomingRequests />;
}
