import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";

/**
 * What staff are told when an action didn't go through: the API's `why`
 * where it gave one (`NOT_ALLOWED`), its code otherwise. Staff read the
 * API's own words for the case, so a refusal is never a mystery (D-920).
 */
export function refusalText(error: unknown): string {
  if (error instanceof ApiError) {
    const why = error.details?.why;
    return t("admin.refused", {
      why: typeof why === "string" ? why : error.code,
    });
  }
  return t("admin.actionFailed");
}
