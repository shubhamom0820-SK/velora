"use client";

import {
  Heart,
  type LucideIcon,
  MessageCircle,
  User,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Icon } from "@/components/ui/Icon";
import type { MessageKey } from "@/i18n/t";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { cx } from "@/lib/cx";

/**
 * The app's four places, in this order (T-5.6). No Vibe: after beta (D-010).
 * Each is a placeholder route until its task builds the screen.
 */
const NAV: ReadonlyArray<{
  href: string;
  label: MessageKey;
  icon: LucideIcon;
}> = [
  { href: "/discover", label: "shell.discover", icon: Heart },
  { href: "/chats", label: "shell.chats", icon: MessageCircle },
  { href: "/wallet", label: "shell.wallet", icon: Wallet },
  { href: "/you", label: "shell.you", icon: User },
];

/** A place is current on its own path and on every path beneath it. */
function isCurrent(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * The header and bottom nav around every `(app)` screen (T-5.6), inside
 * T-3.10's gate and PIN lock, never on `(auth)` routes. Provisional: the app
 * has no visual design yet (P-57).
 *
 * The shell's shape lives here and nowhere else; its colours, type and sizes
 * are tokens in src/styles/tokens.css (`--shell-*`). T-6.5's design pass should
 * change those values, not this structure. `look.test.ts` holds both.
 *
 * One `<nav>`, inside the header: fixed along the bottom on mobile, in the
 * header's row from `md` up, as in the prototype. The wordmark is `APP_NAME`,
 * never the prototype's "Knot" (CLAUDE.md rule 17).
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="bg-bg mx-auto flex min-h-dvh max-w-(--shell-width) flex-col">
      <header className="bg-chrome border-chrome-line sticky top-0 z-10 flex h-(--shell-header-height) items-center gap-(--shell-gutter) border-b px-(--shell-gutter)">
        <span className="text-title-1 text-chrome-ink">{APP_NAME}</span>
        <nav
          aria-label={t("shell.nav")}
          className="bg-chrome border-chrome-line fixed inset-x-0 bottom-0 z-10 flex h-(--shell-nav-height) border-t md:static md:h-auto md:self-stretch md:border-t-0"
        >
          {NAV.map(({ href, label, icon }) => {
            const current = isCurrent(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={current ? "page" : undefined}
                className={cx(
                  "text-micro flex flex-1 flex-col items-center justify-center gap-(--shell-nav-gap) md:flex-none md:px-(--shell-gutter)",
                  current ? "text-chrome-accent" : "text-chrome-mute",
                )}
              >
                {/* Filled when current: colour alone wouldn't say which. */}
                <Icon
                  icon={icon}
                  className={cx(
                    "size-(--shell-nav-icon)",
                    current && "fill-current",
                  )}
                />
                {t(label)}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="flex flex-1 flex-col pb-(--shell-nav-height) md:pb-0">
        {children}
      </main>
    </div>
  );
}
