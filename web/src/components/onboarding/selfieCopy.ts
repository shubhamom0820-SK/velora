import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { APP_NAME } from "@/lib/app";
import type { CameraBrowser, CameraFailure } from "@/lib/camera";
import type { Place } from "@/lib/onboarding";
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

/**
 * Each requirement `PROFILE_INCOMPLETE` may name (the API's
 * `onboarding.rules.Missing`, D-310), and the screen that fills it in. The API
 * names them in onboarding's order, so the first is the earliest to go back to.
 */
const MISSING_PLACE = {
  seeking: "seeking",
  intents: "seeking",
  first_name: "profile",
  hometown: "profile",
  city: "profile",
  location: "location",
  username: "username",
  about: "about",
  photo: "photos",
  interests: "interests",
} as const satisfies Record<string, Place>;
type Missing = keyof typeof MISSING_PLACE;
const MISSING = Object.keys(MISSING_PLACE) as Missing[];

const isMissing = (name: unknown): name is Missing =>
  MISSING.some((listed) => listed === name);

export type FinishCopy = {
  message: string;
  /** The screen to go back to, when the server named one. */
  place: Place | null;
};

/**
 * Why finishing was refused (T-4.8): the first thing still needed, with its
 * screen; that the selfie hasn't matched; otherwise the shared wording. A name
 * this list doesn't know reads as the general line, with nowhere to go.
 */
export function finishCopy(error: unknown): FinishCopy {
  if (error instanceof ApiError && error.code === "PROFILE_INCOMPLETE") {
    const named = error.details?.missing;
    const first = Array.isArray(named) ? named.find(isMissing) : undefined;
    if (!first) {
      return { message: t("onboarding.selfie.finish.incomplete"), place: null };
    }
    const place = MISSING_PLACE[first];
    return {
      message: t(`onboarding.selfie.finish.missing.${place}`),
      place,
    };
  }
  if (error instanceof ApiError && error.code === "VERIFICATION_REQUIRED") {
    return { message: t("onboarding.selfie.finish.needsMatch"), place: null };
  }
  return { message: errorCopy(error).message, place: null };
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
