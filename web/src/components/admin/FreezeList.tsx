"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { t } from "@/i18n/t";
import {
  useAdminFreezes,
  useSetStatus,
  type AdminFreeze,
} from "@/lib/queries/admin";
import { useMe } from "@/lib/queries/me";

import { AdminList } from "./AdminList";
import { ConfirmAction } from "./ConfirmAction";
import { entryTime } from "./time";

function FreezeRow({
  freeze,
  isAdmin,
}: {
  freeze: AdminFreeze;
  isAdmin: boolean;
}) {
  const [open, setOpen] = useState(false);
  const lift = useSetStatus(freeze.user.id);
  return (
    <article className="border-line bg-surface rounded-card flex flex-col gap-1 border p-4">
      <Link
        href={`/admin/users/${freeze.user.id}`}
        className="text-ui text-accent underline"
      >
        {freeze.user.first_name ?? t("admin.users.unnamed")}
      </Link>
      <span className="text-small text-mute">
        {freeze.automatic
          ? t("admin.freezes.automatic", {
              rule: freeze.rule ?? "?",
              score: freeze.score ?? "?",
            })
          : t("admin.freezes.manual")}
        {freeze.frozen_at &&
          ` · ${entryTime.format(new Date(freeze.frozen_at))}`}
      </span>
      {isAdmin && (
        <div>
          <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
            {t("admin.freezes.unfreeze")}
          </Button>
        </div>
      )}
      <ConfirmAction
        open={open}
        onClose={() => setOpen(false)}
        title={t("admin.freezes.unfreeze")}
        confirmLabel={t("admin.freezes.unfreeze")}
        variant="primary"
        pending={lift.isPending}
        error={lift.error}
        onConfirm={(reason) =>
          lift.mutate(
            { status: "active", reason },
            { onSuccess: () => setOpen(false) },
          )
        }
      />
    </article>
  );
}

/**
 * Who is frozen now (P-800, D-928), the newest first, T-9.2's automatic ones
 * marked with their rule and score, so a wrong one is seen and lifted, by an
 * admin, through the founder's own tool's path (D-906).
 */
export function FreezeList() {
  const freezes = useAdminFreezes();
  const isAdmin = useMe().data?.role === "admin";
  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-title-1">{t("admin.freezes.title")}</h1>
      <AdminList
        query={freezes}
        empty={t("admin.freezes.empty")}
        keyOf={(f) => f.user.id}
      >
        {(freeze) => <FreezeRow freeze={freeze} isAdmin={isAdmin} />}
      </AdminList>
    </section>
  );
}
