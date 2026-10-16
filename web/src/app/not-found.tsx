import { connection } from "next/server";

import { ButtonLink } from "@/components/ui/ButtonLink";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

/**
 * Every 404 of the site (P-445, D-980): an unmatched address and any
 * `notFound()`. Ours rather than Next's built-in page, which sets inline
 * styles that neither CSP allows. Styled by classes only.
 *
 * Per request, never prerendered: a 404 beneath a nonce route (`/login/…`) is
 * served under the proxy's nonce policy, and a page built ahead of the request
 * carries no nonce, so every script on it was refused and it never hydrated.
 * A not-found file takes no `dynamic` export, hence `connection()`.
 * e2e/not-found.spec.ts holds both policies to no violation.
 *
 * Its own `<title>`, as Next's page has: a not-found file takes no `metadata`.
 */
export default async function NotFound() {
  await connection();
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col items-center gap-5 px-4 py-10 text-center">
      <title>{t("notFound.title")}</title>
      <h1 className="text-title-1 text-ink">{t("notFound.title")}</h1>
      <p className="text-body text-mute">{t("notFound.body")}</p>
      <ButtonLink href="/">{t("notFound.home", { app: APP_NAME })}</ButtonLink>
    </main>
  );
}
