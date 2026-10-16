import type { Metadata } from "next";

import { UserDetail } from "@/components/admin/UserDetail";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.users.title") };

/** One account for staff (T-9.5). */
export default async function AdminUserPage({
  params,
}: PageProps<"/admin/users/[id]">) {
  const { id } = await params;
  return <UserDetail id={id} />;
}
