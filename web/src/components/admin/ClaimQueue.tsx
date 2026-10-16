"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { t } from "@/i18n/t";
import {
  useAdminClaims,
  useResolveClaim,
  type AdminClaim,
  type ClaimAction,
} from "@/lib/queries/admin";

import { AdminList } from "./AdminList";
import { ConfirmAction } from "./ConfirmAction";
import { entryTime } from "./time";

const ACTIONS: readonly ClaimAction[] = ["grant", "refund", "reject"];

function ClaimCard({ claim }: { claim: AdminClaim }) {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<ClaimAction | null>(null);
  const resolve = useResolveClaim();
  return (
    <article className="border-line bg-surface rounded-card flex flex-col gap-1 border p-4">
      <span className="text-ui text-ink font-semibold">
        {t(`admin.claims.reasons.${claim.reason}`)}
      </span>
      <Link
        href={`/admin/users/${claim.user_id}`}
        className="text-small text-accent underline"
      >
        {claim.user_id}
      </Link>
      <span className="text-small text-mute">
        {claim.order_id} · {claim.payment_status} ·{" "}
        {entryTime.format(new Date(claim.created_at))}
      </span>
      <div>
        <Button size="sm" onClick={() => setOpen(true)}>
          {t("admin.reports.resolve")}
        </Button>
      </div>
      <ConfirmAction
        open={open}
        onClose={() => setOpen(false)}
        title={t("admin.claims.title")}
        confirmLabel={t("admin.reports.resolve")}
        variant="primary"
        pending={resolve.isPending}
        error={resolve.error}
        ready={action !== null}
        onConfirm={(note) => {
          if (action === null) return;
          resolve.mutate(
            { id: claim.id, action, note },
            { onSuccess: () => setOpen(false) },
          );
        }}
      >
        <div role="group" className="flex flex-wrap gap-2">
          {ACTIONS.map((choice) => (
            <Chip
              key={choice}
              active={action === choice}
              onClick={() => setAction(choice)}
            >
              {t(`admin.claims.actions.${choice}`)}
            </Chip>
          ))}
        </div>
      </ConfirmAction>
    </article>
  );
}

/**
 * The claims screen (P-480): T-8.3's open claims, oldest first, each resolved
 * by an admin with grant, refund or reject behind a confirmation, from what
 * the gateway says (D-580). An admin's alone; a moderator's call is refused.
 */
export function ClaimQueue() {
  const claims = useAdminClaims();
  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-title-1">{t("admin.claims.title")}</h1>
      <AdminList
        query={claims}
        empty={t("admin.claims.empty")}
        keyOf={(claim) => claim.id}
      >
        {(claim) => <ClaimCard claim={claim} />}
      </AdminList>
    </section>
  );
}
