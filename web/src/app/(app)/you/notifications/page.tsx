import type { Metadata } from "next";

import { NotificationSettings } from "@/components/notifications/NotificationSettings";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("notifications.settings.title") };

/** Notification settings (T-9.4), linked from You. */
export default function NotificationSettingsPage() {
  return <NotificationSettings />;
}
