import type { Metadata } from "next";

import { MinorFlagList } from "@/components/admin/MinorFlagList";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.minorFlags.title") };

/** Who waits for a human with possible-minor flags (P-72, D-991). */
export default function AdminMinorFlagsPage() {
  return <MinorFlagList />;
}
