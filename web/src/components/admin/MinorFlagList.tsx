"use client";

import Link from "next/link";

import { t } from "@/i18n/t";
import { useAdminMinorFlags, type AdminMinorFlag } from "@/lib/queries/admin";

import { AdminList } from "./AdminList";
import { flagsText, MINOR_FLAGS_INTRO } from "./MinorReview";
import { entryTime } from "./time";

function FlagRow({ item }: { item: AdminMinorFlag }) {
  return (
    <article className="border-line bg-surface rounded-card flex flex-col gap-1 border p-4">
      <Link
        href={`/admin/users/${item.user.id}`}
        className="text-ui text-accent underline"
      >
        {item.user.first_name ?? t("admin.users.unnamed")}
      </Link>
      <span className="text-small text-mute">
        {t(`admin.status.${item.user.status}`)} · {flagsText(item)}
      </span>
      <span className="text-small text-mute">
        {t("admin.minorFlags.between", {
          first: entryTime.format(new Date(item.first_at)),
          last: entryTime.format(new Date(item.last_at)),
        })}
      </span>
    </article>
  );
}

/**
 * Who waits for a human with possible-minor flags (P-72, D-991), the newest
 * flag first. Each opens the person's page, where the decision is made: the
 * same place an admin's notification opens (D-994).
 */
export function MinorFlagList() {
  const flags = useAdminMinorFlags();
  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-title-1">{t("admin.minorFlags.title")}</h1>
      <p className="text-small text-mute">{t(MINOR_FLAGS_INTRO)}</p>
      <AdminList
        query={flags}
        empty={t("admin.minorFlags.empty")}
        keyOf={(item) => item.user.id}
      >
        {(item) => <FlagRow item={item} />}
      </AdminList>
    </section>
  );
}
