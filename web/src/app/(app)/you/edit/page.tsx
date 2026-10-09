import type { Metadata } from "next";

import { EditProfile } from "@/components/you/EditProfile";
import { t } from "@/i18n/t";

export const metadata: Metadata = { title: t("you.edit") };

/** Edit profile (T-9.8), linked from You. */
export default function EditProfilePage() {
  return <EditProfile />;
}
