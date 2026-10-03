import Link from "next/link";

import { t } from "@/i18n/t";

import type { ErrorCopy } from "./errorCopy";

/** A failed request, said inline (T-3.11), with /contact when a person can help. */
export function FormError({ copy }: { copy: ErrorCopy | null }) {
  if (!copy) return null;
  return (
    <p role="alert" className="text-small text-accent mt-3">
      {copy.message}
      {copy.contact && (
        <>
          {" "}
          <Link href="/contact" className="underline underline-offset-2">
            {t("apiErrors.contact")}
          </Link>
        </>
      )}
    </p>
  );
}
