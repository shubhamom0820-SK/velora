import type { Metadata } from "next";

import { MetricTiles } from "@/components/admin/MetricTiles";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.title") };

/** The panel's dashboard (T-9.5, D-926): counts, and money in for an admin. */
export default function AdminPage() {
  return <MetricTiles />;
}
