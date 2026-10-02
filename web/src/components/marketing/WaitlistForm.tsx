"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { t, type MessageKey } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { useJoinWaitlist } from "@/lib/queries/waitlist";

// The API's own limits and shape check (api/app/modules/waitlist/schemas.py),
// so the browser turns away what the API would without a round trip. The API
// still decides.
const EMAIL_SHAPE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const EMAIL_MAX = 254;
const CITY_MAX = 40;

function failureMessage(error: Error): MessageKey {
  if (error instanceof ApiError) {
    if (error.code === "RATE_LIMITED") return "landing.waitlist.rateLimited";
    if (error.code === "VALIDATION_ERROR")
      return "landing.waitlist.invalidEmail";
  }
  return "landing.waitlist.failed";
}

/**
 * The waitlist form and its success state: the landing page's one client
 * component (T-2.3).
 *
 * Plain React state, not React Hook Form and Zod: this is the landing page,
 * where T-2.1 scored 98–100 on performance, and two form libraries for an email
 * and a city would spend that. T-3.11's multi-step forms bring them in.
 */
export function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [city, setCity] = useState("");
  const [invalid, setInvalid] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const join = useJoinWaitlist();

  const failure = join.error ? failureMessage(join.error) : null;
  const emailError =
    invalid || failure === "landing.waitlist.invalidEmail"
      ? t("landing.waitlist.invalidEmail")
      : undefined;
  const formError =
    failure && failure !== "landing.waitlist.invalidEmail" ? t(failure) : null;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const address = email.trim();
    if (address.length > EMAIL_MAX || !EMAIL_SHAPE.test(address)) {
      setInvalid(true);
      emailRef.current?.focus();
      return;
    }
    setInvalid(false);
    const where = city.trim();
    join.mutate(where ? { email: address, city: where } : { email: address });
  }

  // Editing after a failure clears it: the message was about the last try.
  function edited() {
    setInvalid(false);
    if (join.isError) join.reset();
  }

  return (
    <div className="mt-4">
      {/* Always in the page, so screen readers announce the success when it appears. */}
      <div role="status">
        {join.isSuccess && (
          <p className="bg-accent-soft rounded-input text-ui text-accent flex items-center gap-2 px-4 py-3">
            <Icon icon={Check} size={16} />
            {t("landing.waitlist.joined")}
          </p>
        )}
      </div>
      {!join.isSuccess && (
        <form noValidate onSubmit={submit} className="flex flex-col gap-3">
          <Field
            ref={emailRef}
            label={t("landing.waitlist.email")}
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder={t("landing.waitlist.emailPlaceholder")}
            maxLength={EMAIL_MAX}
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              edited();
            }}
            error={emailError}
          />
          <Field
            label={t("landing.waitlist.city")}
            autoComplete="address-level2"
            maxLength={CITY_MAX}
            value={city}
            onChange={(event) => {
              setCity(event.target.value);
              edited();
            }}
          />
          {formError && (
            <p role="alert" className="text-small text-accent">
              {formError}
            </p>
          )}
          <Button type="submit" loading={join.isPending} fullWidth>
            {t("landing.waitlist.join")}
          </Button>
          <p className="text-small text-mute">
            {t("landing.waitlist.privacyNote")}{" "}
            <Link href="/privacy" className="underline underline-offset-2">
              {t("landing.waitlist.privacyLink")}
            </Link>
          </p>
        </form>
      )}
    </div>
  );
}
