import type { Metadata } from "next";

import { SettingsScreen } from "@/components/you/SettingsScreen";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("settings.title") };

/** Privacy and account (T-9.8, T-9.6's routes), linked from You. */
export default function SettingsPage() {
  return <SettingsScreen />;
}
