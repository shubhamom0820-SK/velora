import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { UploadError } from "@/lib/upload";

import { errorCopy } from "./errorCopy";

/**
 * What a photo's slot says when it isn't on the profile (T-4.6). The API names
 * the reason (`reject_reason`, D-096); these words are the web's, in `en.ts`.
 * A reason not listed here reads as `other`, D-093's wording, which accuses
 * nobody: so does a possible minor, which the API already sends as `other`.
 */
const REASONS = [
  "unsupported_format",
  "too_large",
  "abandoned",
  "nudity",
  "no_face",
  "text_overlay",
  "other",
] as const;
type Reason = (typeof REASONS)[number];

export function reasonCopy(reason: string | null | undefined): string {
  const known: Reason = REASONS.find((listed) => listed === reason) ?? "other";
  return t(`onboarding.photos.reasons.${known}`);
}

/** The server refused the photo itself: choosing another is the way on. */
export function isRefusal(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.code === "UNSUPPORTED_IMAGE" || error.code === "IMAGE_TOO_LARGE")
  );
}

/** What went wrong with an upload, said in its slot. */
export function uploadErrorCopy(error: unknown): string {
  if (error instanceof UploadError) {
    // Storage refusing a signed PUT is ours to fix, not the person's.
    return error.failure === "network"
      ? t("onboarding.photos.reasons.network")
      : t("apiErrors.unknown");
  }
  if (error instanceof ApiError) {
    if (error.code === "UNSUPPORTED_IMAGE")
      return reasonCopy("unsupported_format");
    if (error.code === "IMAGE_TOO_LARGE") return reasonCopy("too_large");
  }
  return errorCopy(error).message;
}
