import type { Metadata } from "next";

import { YouScreen } from "@/components/you/YouScreen";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("you.title") };

/**
 * The You tab (T-9.8), inside the app shell's `<main>` (T-5.6) and a nonce
 * route (D-541).
 */
export default function YouPage() {
  return <YouScreen />;
}
