import type { Metadata } from "next";

import { ReportQueue } from "@/components/admin/ReportQueue";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.reports.title") };

/** The report queue (T-9.5, D-921), oldest first, each with its day (P-761). */
export default function AdminReportsPage() {
  return <ReportQueue />;
}
