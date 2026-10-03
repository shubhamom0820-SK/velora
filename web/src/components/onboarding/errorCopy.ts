import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { APP_NAME } from "@/lib/app";

/**
 * What a screen says about a failed request (T-3.11), from `ApiError.code`
 * through `en.ts`, never the API's own words: those are English only and
 * worded for developers. Business rules are the server's alone (D-082), so a
 * refusal arrives here and is shown inline, beside the field it names.
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

export function errorCopy(error: unknown): ErrorCopy {
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
