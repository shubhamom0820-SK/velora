import type { Metadata } from "next";

import { AuditList } from "@/components/admin/AuditList";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.audit.title") };

/** The audit log (T-9.5), newest first. */
export default function AdminAuditPage() {
  return <AuditList />;
}
