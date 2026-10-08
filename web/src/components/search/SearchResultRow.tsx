import Link from "next/link";

import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { t } from "@/i18n/t";
import type { SearchResult } from "@/lib/queries/search";

/**
 * One person in search's results (08-DESIGN §8): a 64 px row, a 44 px avatar
 * with the badge where D-393's rule holds (`shows_badge`, never
 * `is_verified`) and the online dot, the name and age, the @username and
 * city, and "Exact" on an exact username match; it opens their profile,
 * `/people/[id]` (T-6.8). Their text is theirs, so it
 * is React's to escape, never set as HTML (the CSP re-check, T-6.6).
 */
export function SearchResultRow({ person }: { person: SearchResult }) {
  return (
    <Link
      href={`/people/${person.id}`}
      className="hover:bg-surface flex h-16 items-center gap-3 px-(--shell-gutter)"
    >
      <Avatar
        name={person.first_name}
        src={person.main_photo_url ?? undefined}
        size={44}
        online={person.is_online}
        verified={person.shows_badge}
      />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-ui text-ink truncate">
          {person.age === null
            ? person.first_name
            : t("search.nameAge", { name: person.first_name, age: person.age })}
        </span>
        <span className="text-small text-mute truncate">
          {person.city
            ? t("search.usernameCity", {
                username: person.username,
                city: person.city,
              })
            : t("search.usernameOnly", { username: person.username })}
        </span>
      </span>
      {person.exact && <Badge tone="soft">{t("search.exact")}</Badge>}
    </Link>
  );
}
