import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { APP_NAME } from "@/lib/app";
import type { CameraBrowser, CameraFailure } from "@/lib/camera";
import { UploadError } from "@/lib/upload";

import { errorCopy } from "./errorCopy";

/**
 * What the selfie step says (T-4.7). The API names a rejection's reason from
 * D-263's list; these words are the web's, in `en.ts`, each saying what to
 * change and accusing nobody. A reason not listed reads as `other`.
 */
const REASONS = [
  "no_face",
  "many_faces",
  "no_match",
  "no_photos",
  "unreadable",
  "unavailable",
  "other",
] as const;
type Reason = (typeof REASONS)[number];

export function selfieReasonCopy(reason: string | null | undefined): string {
  const known: Reason = REASONS.find((listed) => listed === reason) ?? "other";
  return t(`onboarding.selfie.reasons.${known}`);
}

/** `attempts_left`: selfies that may still be sent in the next 24 hours. */
export function triesCopy(left: number): string {
  if (left <= 0) return t("onboarding.selfie.triesNone");
  if (left === 1) return t("onboarding.selfie.triesOne");
  return t("onboarding.selfie.triesMany", { count: left });
}

/** `RATE_LIMITED`'s wait, in minutes under an hour, else in hours. */
export function waitCopy(retryAfterS: number): string {
  const minutes = Math.max(1, Math.ceil(retryAfterS / 60));
  if (minutes < 60) return t("onboarding.selfie.waitMinutes", { minutes });
  return t("onboarding.selfie.waitHours", { hours: Math.ceil(minutes / 60) });
}

/**
 * Why starting or sending was refused: the wait, when the day's selfies or the
 * hour's starts are used up; otherwise the shared wording for the code.
 */
export function refusalCopy(error: unknown): string {
  if (error instanceof ApiError && error.code === "RATE_LIMITED") {
    const after = error.details?.retry_after_s;
    if (typeof after === "number") return waitCopy(after);
  }
  return errorCopy(error).message;
}

/** Why a selfie didn't reach the API, said under it. */
export function sendFailedCopy(error: unknown): string {
  if (error instanceof UploadError) {
    // Storage refusing a signed PUT is ours to fix, not the person's.
    return error.failure === "network"
      ? t("onboarding.selfie.sendFailed")
      : t("apiErrors.unknown");
  }
  return errorCopy(error).message;
}

/** Why the camera didn't open, and, when it's blocked, where to allow it. */
export function cameraCopy(
  failure: CameraFailure,
  browser: CameraBrowser,
  host: string,
): { title: string; how: string | null } {
  switch (failure) {
    case "denied":
      return {
        title: t("onboarding.selfie.camera.denied", { app: APP_NAME }),
        how: t(`onboarding.selfie.camera.how.${browser}`, { host }),
      };
    case "unsupported":
      return {
        title: t("onboarding.selfie.camera.unsupported", { app: APP_NAME }),
        how: null,
      };
    case "none":
    case "busy":
    case "other":
      return { title: t(`onboarding.selfie.camera.${failure}`), how: null };
  }
}
