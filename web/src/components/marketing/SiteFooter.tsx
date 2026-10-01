import Link from "next/link";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { PLACE } from "@/lib/legal";

const LINKS = [
  { href: "/terms", key: "landing.footer.terms" },
  { href: "/privacy", key: "landing.footer.privacy" },
  { href: "/refunds", key: "landing.footer.refunds" },
  { href: "/contact", key: "landing.footer.contact" },
] as const;

/**
 * The black footer on every marketing page (T-2.2's layout): the legal links
 * and the © line, with the registered office's city (D-013). The © line is
 * full `--chrome-mute`: the prototype's 70% opacity falls below the contrast
 * its small text needs. Not printed: a printed legal page is the page alone.
 */
export function SiteFooter() {
  return (
    <footer className="bg-chrome border-chrome-line border-t px-6 py-8 print:hidden">
      <nav aria-label={t("landing.footer.label")}>
        <ul className="flex flex-wrap justify-center gap-6">
          {LINKS.map(({ href, key }) => (
            <li key={href}>
              {/* The invisible ::before stretches the tap area past 44 px
                  (08-DESIGN §3) without moving the layout. */}
              <Link
                href={href}
                className="text-small text-chrome-mute relative before:absolute before:-inset-x-2 before:-inset-y-3.5"
              >
                {t(key)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <p className="text-small text-chrome-mute mt-4 text-center">
        {t("landing.footer.copyright", {
          year: new Date().getFullYear(),
          app: APP_NAME,
          city: PLACE.city,
          country: PLACE.country,
        })}
      </p>
    </footer>
  );
}
