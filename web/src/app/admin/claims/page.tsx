import type { Metadata } from "next";

import { ClaimQueue } from "@/components/admin/ClaimQueue";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.claims.title") };

/** The claims screen (P-480): an admin's, T-8.3's routes (D-582). */
export default function AdminClaimsPage() {
  return <ClaimQueue />;
}
