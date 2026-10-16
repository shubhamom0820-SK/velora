import type { Metadata } from "next";

import { ModerationQueue } from "@/components/admin/ModerationQueue";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.photos.title") };

/** The moderation queue (T-9.5, D-925). */
export default function AdminModerationPage() {
  return <ModerationQueue />;
}
