"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { t } from "@/i18n/t";
import type { components } from "@/types/api";

type CardLite = components["schemas"]["CardLite"];

type PersonRowProps = {
  person: CardLite;
  /** Under the name, e.g. when or why. */
  detail?: string;
  /** Where the row opens; none, a row that opens nothing. */
  href?: string;
  /** Beside the row, e.g. Unblock. */
  action?: ReactNode;
};

/** A deleted account's name, as the chats list says it (D-051, D-500). */
export function nameOf(person: CardLite): string {
  return person.deleted ? t("chats.deletedAccount") : (person.first_name ?? "");
}

/**
 * One person in a You list (T-9.8): avatar, name and a line under it, opening
 * what `href` says, with its action beside it. Their text is React's to
 * escape, never set as HTML.
 */
export function PersonRow({ person, detail, href, action }: PersonRowProps) {
  const name = nameOf(person);
  const body = (
    <>
      <Avatar
        name={name}
        src={person.main_photo_url ?? undefined}
        size={46}
        online={person.is_online}
        verified={person.shows_badge}
      />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-ui text-ink truncate">{name}</span>
        {detail && (
          <span className="text-small text-mute truncate">{detail}</span>
        )}
      </span>
    </>
  );
  return (
    <li className="border-line flex items-center gap-3 border-b py-3 last:border-b-0">
      {href ? (
        <Link
          href={href}
          className="focus-visible:outline-accent flex min-w-0 flex-1 items-center gap-3 focus-visible:outline-2"
        >
          {body}
        </Link>
      ) : (
        <div className="flex min-w-0 flex-1 items-center gap-3">{body}</div>
      )}
      {action}
    </li>
  );
}
