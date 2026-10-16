"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { t } from "@/i18n/t";
import { useAdminUsers, type AdminUser } from "@/lib/queries/admin";

import { AdminList } from "./AdminList";
import { refusalText } from "./refusal";

function UserRow({ user }: { user: AdminUser }) {
  return (
    <Link
      href={`/admin/users/${user.id}`}
      className="border-line bg-surface rounded-card flex items-center justify-between gap-3 border p-4"
    >
      <span className="flex flex-col">
        <span className="text-ui text-ink font-semibold">
          {user.first_name ?? t("admin.users.unnamed")}
          {user.username && (
            <span className="text-mute font-normal"> @{user.username}</span>
          )}
        </span>
        <span className="text-small text-mute">
          {[user.city, user.age, user.gender].filter(Boolean).join(" · ")}
        </span>
      </span>
      <span className="flex gap-2">
        {user.erased && <Badge tone="soft">{t("admin.users.erased")}</Badge>}
        <Badge tone={user.status === "active" ? "soft" : "ink"}>
          {t(`admin.status.${user.status}`)}
        </Badge>
      </span>
    </Link>
  );
}

/**
 * User search (T-9.5): a whole number, never a part of one (D-061); an
 * account's id; or the start of a name or @username. Empty, the newest
 * accounts. An erased account is found by its number, marked erased (D-500).
 */
export function UserSearch() {
  const [typed, setTyped] = useState("");
  const [q, setQ] = useState("");
  const users = useAdminUsers(q);

  function search(event: FormEvent) {
    event.preventDefault();
    setQ(typed.trim());
  }

  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-title-1">{t("admin.users.title")}</h1>
      <form onSubmit={search} className="flex items-end gap-2">
        <div className="flex-1">
          <Field
            label={t("admin.users.search")}
            helper={t("admin.users.searchHelper")}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            maxLength={64}
            error={users.isError && q ? refusalText(users.error) : undefined}
          />
        </div>
        <Button type="submit">{t("admin.users.search")}</Button>
      </form>
      <AdminList
        query={users}
        empty={t("admin.users.empty")}
        keyOf={(user) => user.id}
      >
        {(user) => <UserRow user={user} />}
      </AdminList>
    </section>
  );
}
