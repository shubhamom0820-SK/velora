"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { t } from "@/i18n/t";
import { useAdminAudit } from "@/lib/queries/admin";

import { AdminList } from "./AdminList";
import { entryTime } from "./time";

/**
 * The audit log (T-9.5), newest first: every staff call and every automatic
 * action, the system user's named "System" (D-905). Filtered by one action,
 * e.g. `fraud.freeze`. Reading it is audited too.
 */
export function AuditList() {
  const [typed, setTyped] = useState("");
  const [action, setAction] = useState("");
  const entries = useAdminAudit(action);

  function filter(event: FormEvent) {
    event.preventDefault();
    setAction(typed.trim());
  }

  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-title-1">{t("admin.audit.title")}</h1>
      <form onSubmit={filter} className="flex items-end gap-2">
        <div className="flex-1">
          <Field
            label={t("admin.audit.filter")}
            value={typed}
            maxLength={64}
            onChange={(event) => setTyped(event.target.value)}
          />
        </div>
        <Button type="submit">{t("admin.audit.filter")}</Button>
      </form>
      <AdminList
        query={entries}
        empty={t("admin.audit.empty")}
        keyOf={(entry) => entry.id}
      >
        {(entry) => (
          <div className="border-line bg-surface rounded-card flex flex-col gap-1 border p-3">
            <span className="text-ui text-ink font-semibold">
              {entry.action}
            </span>
            <span className="text-small text-mute">
              {entry.actor_is_system ? t("admin.audit.system") : entry.actor_id}{" "}
              · {entryTime.format(new Date(entry.created_at))}
            </span>
            {entry.target_id && (
              <span className="text-small text-mute">
                {entry.target_type} {entry.target_id}
              </span>
            )}
            {entry.meta && (
              <code className="text-micro text-mute break-all">
                {JSON.stringify(entry.meta)}
              </code>
            )}
          </div>
        )}
      </AdminList>
    </section>
  );
}
