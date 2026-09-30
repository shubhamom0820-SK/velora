import { notFound } from "next/navigation";

import { t } from "@/i18n/t";

/**
 * Placeholder until the admin panel (T-9.5). Served only by `next dev` — the
 * same allowlist as `/dev/ui` — so public staging doesn't show it (P-30). T-9.5
 * replaces this gate with a role check, which is UX, not protection: the API's
 * `require_role` is what guards admin data.
 */
export default function AdminPage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return (
    <main className="bg-bg text-ink flex min-h-dvh flex-col items-center justify-center gap-2 p-6">
      <h1 className="text-title-1">{t("placeholder.admin")}</h1>
      <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
    </main>
  );
}
