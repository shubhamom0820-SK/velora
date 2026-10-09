"use client";

import {
  Bell,
  ChevronRight,
  Images,
  Inbox,
  Lock,
  type LucideIcon,
  Shield,
} from "lucide-react";
import Link from "next/link";

import { SignOutButton } from "@/components/session/SignOutButton";
import { Icon } from "@/components/ui/Icon";
import { t, type MessageKey } from "@/i18n/t";
import type { Me } from "@/lib/queries/me";
import { useSession } from "@/store/session";

import { YouSection } from "./YouSection";

const ITEM = "border-line border-b last:border-b-0";
const ROW =
  "text-ui text-ink focus-visible:outline-accent flex w-full items-center gap-3 px-1 py-3.5 text-left focus-visible:outline-2";

const LINKS = [
  { href: "/you/settings", icon: Shield, label: "you.account" },
  { href: "/notifications", icon: Inbox, label: "notifications.you.list" },
  {
    href: "/you/notifications",
    icon: Bell,
    label: "notifications.you.settings",
  },
  // T-8.8's link (D-790), for everyone: a woman may ask for a man's album too.
  { href: "/you/album-requests", icon: Images, label: "albumRequests.title" },
] as const satisfies readonly {
  href: string;
  icon: LucideIcon;
  label: MessageKey;
}[];

/**
 * The settings rows (T-9.8), the prototype's list: each opens its screen;
 * "Lock now" puts the PIN lock up at once, only for someone with a PIN
 * (D-069: a deterrent, not protection); and sign out (T-3.10).
 */
export function YouRows({ me }: { me: Me }) {
  return (
    <YouSection title={t("you.settings")}>
      <ul className="rounded-card border-line bg-surface flex flex-col border px-3">
        {LINKS.map((row) => (
          <li key={row.href} className={ITEM}>
            <Link href={row.href} className={ROW}>
              <Icon icon={row.icon} size={16} className="text-mute" />
              <span className="flex-1">{t(row.label)}</span>
              <Icon icon={ChevronRight} size={15} className="text-mute" />
            </Link>
          </li>
        ))}
        {me.has_pin && (
          <li className={ITEM}>
            <button
              type="button"
              className={ROW}
              onClick={() => useSession.getState().setLocked(true)}
            >
              <Icon icon={Lock} size={16} className="text-mute" />
              <span className="flex-1">{t("you.lockNow")}</span>
            </button>
          </li>
        )}
      </ul>
      <div className="pt-4">
        <SignOutButton />
      </div>
    </YouSection>
  );
}
