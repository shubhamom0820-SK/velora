import type { Metadata } from "next";

import { FreezeList } from "@/components/admin/FreezeList";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.freezes.title") };

/** Who is frozen now (P-800, D-928). */
export default function AdminFreezesPage() {
  return <FreezeList />;
}
