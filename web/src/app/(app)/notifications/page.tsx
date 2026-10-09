import type { Metadata } from "next";

import { NotificationsScreen } from "@/components/notifications/NotificationsScreen";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("notifications.title") };

/** The in-app list (T-9.4), linked from You until the header has a bell (P-750). */
export default function NotificationsPage() {
  return <NotificationsScreen />;
}
