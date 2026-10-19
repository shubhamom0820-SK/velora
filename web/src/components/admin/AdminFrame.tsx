"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { t, type MessageKey } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { cx } from "@/lib/cx";
import { useMe } from "@/lib/queries/me";

type Section = { href: string; label: MessageKey; adminOnly?: boolean };

/** The panel's sections. Claims move Velas or money: an admin's (D-582). */
const SECTIONS: readonly Section[] = [
  { href: "/admin", label: "admin.nav.dashboard" },
  { href: "/admin/reports", label: "admin.nav.reports" },
  { href: "/admin/moderation", label: "admin.nav.moderation" },
  { href: "/admin/users", label: "admin.nav.users" },
  { href: "/admin/freezes", label: "admin.nav.freezes" },
  { href: "/admin/minor-flags", label: "admin.nav.minorFlags" },
  { href: "/admin/claims", label: "admin.nav.claims", adminOnly: true },
  { href: "/admin/audit", label: "admin.nav.audit" },
];

/**
 * The panel's frame: a heading and its sections, 760 px wide at most
 * (08-DESIGN §3), from existing parts only (D-920). No app shell: staff work
 * here, nobody dates.
 */
export function AdminFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const me = useMe();
  const isAdmin = me.data?.role === "admin";

  return (
    <div className="bg-bg text-ink mx-auto flex min-h-dvh max-w-190 flex-col gap-4 px-4 py-6">
      <header className="flex flex-col gap-3">
        <p className="text-title-1">
          {APP_NAME} · {t("admin.title")}
        </p>
        <nav aria-label={t("admin.nav.label")}>
          <ul className="flex flex-wrap gap-2">
            {SECTIONS.filter((section) => isAdmin || !section.adminOnly).map(
              (section) => {
                const here = pathname === section.href;
                return (
                  <li key={section.href}>
                    <Link
                      href={section.href}
                      aria-current={here ? "page" : undefined}
                      className={cx(
                        "rounded-pill text-ui inline-flex border px-3.5 py-2",
                        "focus-visible:outline-accent focus-visible:outline-2 focus-visible:outline-offset-2",
                        here
                          ? "border-accent bg-accent-soft text-accent-text font-semibold"
                          : "border-line text-mute",
                      )}
                    >
                      {t(section.label)}
                    </Link>
                  </li>
                );
              },
            )}
          </ul>
        </nav>
      </header>
      <main className="flex flex-col gap-4">{children}</main>
    </div>
  );
}
