import type { Metadata } from "next";

import { UserSearch } from "@/components/admin/UserSearch";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("admin.users.title") };

/** User search (T-9.5): a whole number, an id, or a name's start (D-061). */
export default function AdminUsersPage() {
  return <UserSearch />;
}
