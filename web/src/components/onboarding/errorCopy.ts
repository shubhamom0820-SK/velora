import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { APP_NAME } from "@/lib/app";

/**
 * What a screen says about a failed request (T-3.11), from `ApiError.code`
 * through `en.ts`, never the API's own words: those are English only and
 * worded for developers. Business rules are the server's alone (D-082), so a
 * refusal arrives here and is shown inline, beside the field it names.
 *
 * On Path A, Firebase answers first (T-3.14): its errors carry an `auth/…`
 * code, read here by shape so this file never loads the SDK.
 */

const FIELDS = [
  "phone",
  "otp",
  "dob",
  "first_name",
  "hometown",
  "city",
  "username",
  "intent_ids",
  "about",
  "interest_ids",
  "pin",
] as const;
export type FieldName = (typeof FIELDS)[number];

export type ErrorCopy = {
  message: string;
  /** Offer a way to a person: /contact, where grievance@ is (decision 16). */
  contact: boolean;
  /** A line for each field the API named. */
  fields: Partial<Record<FieldName, string>>;
};

const plain = (message: string): ErrorCopy => ({
  message,
  contact: false,
  fields: {},
});

function namedFields(error: ApiError): ErrorCopy["fields"] {
  const fields: ErrorCopy["fields"] = {};
  const listed = error.details?.fields;
  if (!Array.isArray(listed)) return fields;
  for (const item of listed) {
    const name: unknown = (item as { field?: unknown }).field;
    const known = FIELDS.find((field) => field === name);
    if (known) fields[known] = t(`apiErrors.fields.${known}`);
  }
  return fields;
}

/** Firebase Auth's code for `error`, if it is one of its errors. */
function firebaseCode(error: unknown): string | null {
  if (!(error instanceof Error) || !("code" in error)) return null;
  const { code } = error;
  return typeof code === "string" && code.startsWith("auth/") ? code : null;
}

function firebaseCopy(code: string): ErrorCopy {
  switch (code) {
    case "auth/invalid-phone-number":
    case "auth/missing-phone-number":
      return {
        ...plain(t("apiErrors.invalid")),
        fields: { phone: t("apiErrors.fields.phone") },
      };
    // The SMS region policy, India only, refusing a number from anywhere
    // else. Asked for +1 650-555-0100 on 4 October 2026, Firebase answered 400
    // "OPERATION_NOT_ALLOWED : SMS unable to be sent until this region enabled
    // by the app developer.", before any reCAPTCHA check, and the SDK turns
    // OPERATION_NOT_ALLOWED into this code. It says it's the number, not them.
    // The same code would come back if phone sign-in were switched off in the
    // console: our outage, and this line would then be wrong.
    case "auth/operation-not-allowed":
      return plain(t("apiErrors.phoneNotSupported"));
    case "auth/invalid-verification-code":
      return plain(t("apiErrors.codeInvalid"));
    case "auth/code-expired":
      return plain(t("apiErrors.otpExpired"));
    case "auth/too-many-requests":
      return plain(t("apiErrors.firebaseTooMany"));
    case "auth/quota-exceeded":
      return plain(t("apiErrors.codesUnavailable"));
    case "auth/captcha-check-failed":
      return plain(t("apiErrors.captchaFailed"));
    case "auth/network-request-failed":
      return plain(t("apiErrors.network", { app: APP_NAME }));
    default:
      return plain(t("apiErrors.unknown"));
  }
}

export function errorCopy(error: unknown): ErrorCopy {
  const firebase = firebaseCode(error);
  if (firebase) return firebaseCopy(firebase);
  if (!(error instanceof ApiError)) {
    return plain(t("apiErrors.network", { app: APP_NAME }));
  }
  switch (error.code) {
    case "VALIDATION_ERROR":
      return { ...plain(t("apiErrors.invalid")), fields: namedFields(error) };
    case "PHONE_NOT_SUPPORTED":
      return plain(t("apiErrors.phoneNotSupported"));
    case "RATE_LIMITED":
      return plain(t("apiErrors.rateLimited"));
    case "PROVIDER_UNAVAILABLE":
      return plain(t("apiErrors.providerUnavailable"));
    case "OTP_INVALID": {
      const left = error.details?.attempts_left;
      if (left === 1) return plain(t("apiErrors.otpInvalidOne"));
      if (typeof left === "number") {
        return plain(t("apiErrors.otpInvalidMany", { count: left }));
      }
      return plain(t("apiErrors.unknown"));
    }
    case "OTP_EXPIRED":
      return plain(t("apiErrors.otpExpired"));
    case "OTP_TOO_MANY":
      return plain(t("apiErrors.otpTooMany"));
    case "FIREBASE_TOKEN_INVALID":
      return plain(t("apiErrors.firebaseTokenInvalid"));
    case "ACCOUNT_BANNED":
    case "ACCOUNT_FROZEN":
    case "FORBIDDEN":
      return { ...plain(t("apiErrors.cantSignIn")), contact: true };
    case "IMMUTABLE_FIELD":
      return plain(t("apiErrors.immutable"));
    case "USERNAME_TAKEN":
      return {
        ...plain(t("apiErrors.usernameTaken")),
        fields: { username: t("apiErrors.usernameTaken") },
      };
    default:
      return plain(t("apiErrors.unknown"));
  }
}
