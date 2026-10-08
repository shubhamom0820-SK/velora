"use client";

import {
  Heart,
  type LucideIcon,
  MessageCircle,
  User,
  Wallet,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Icon } from "@/components/ui/Icon";
import type { MessageKey } from "@/i18n/t";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { creditsCount, creditsText } from "@/lib/credits";
import { cx } from "@/lib/cx";
import { useMe } from "@/lib/queries/me";
import { useWallet } from "@/lib/queries/wallet";
import { useStoreSheet } from "@/store/store-sheet";

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
 *
 * At the header's end (T-5.5): a man's balance pill, which opens the store
 * sheet, or a woman's "Free access". The pill reads the one wallet query; a
 * woman's screen never asks for it. Its look is the `--shell-pill-*` tokens,
 * which `look.test.ts` holds like every other class here.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const gender = useMe().data?.gender;
  const wallet = useWallet({ enabled: gender === "male" });
  const showStore = useStoreSheet((state) => state.show);
  const balance = wallet.data?.balance;
  return (
    <div className="bg-bg mx-auto flex min-h-dvh max-w-(--shell-width) flex-col">
      <header className="bg-chrome border-chrome-line sticky top-0 z-10 flex h-(--shell-header-height) items-center gap-(--shell-gutter) border-b-(length:--shell-line) px-(--shell-gutter)">
        <span className="text-title-1 text-chrome-ink">{APP_NAME}</span>
        <nav
          aria-label={t("shell.nav")}
          className="bg-chrome border-chrome-line fixed inset-x-0 bottom-0 z-10 flex h-(--shell-nav-height) border-t-(length:--shell-line) md:static md:h-auto md:self-stretch md:border-t-0"
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
        {gender === "male" && (
          <button
            type="button"
            onClick={showStore}
            aria-label={
              balance !== undefined
                ? t("wallet.pill", { velas: creditsText(balance) })
                : t(
                    wallet.isError
                      ? "wallet.pillUnavailable"
                      : "wallet.pillLoading",
                  )
            }
            className="bg-accent text-on-accent text-ui rounded-pill shadow-1 relative ml-auto flex items-center gap-(--shell-pill-gap) px-(--shell-pill-pad-x) py-(--shell-pill-pad-y) before:absolute before:-inset-(--shell-pill-tap)"
          >
            <Icon
              icon={Zap}
              className="size-(--shell-pill-icon) fill-current"
            />
            {balance !== undefined && creditsCount(balance)}
          </button>
        )}
        {gender === "female" && (
          <span className="bg-chrome-accent-soft border-chrome-accent text-chrome-ink text-micro rounded-pill ml-auto border-(length:--shell-line) px-(--shell-pill-pad-x) py-(--shell-pill-pad-y)">
            {t("wallet.freeAccess")}
          </span>
        )}
      </header>
      <main className="flex flex-1 flex-col pb-(--shell-nav-height) md:pb-0">
        {children}
      </main>
    </div>
  );
}
