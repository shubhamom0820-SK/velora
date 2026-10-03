"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { t } from "@/i18n/t";
import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";
import {
  useSetUsername,
  useUsernameAvailability,
} from "@/lib/queries/onboarding";

import { errorCopy } from "./errorCopy";
import { FormError } from "./FormError";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";

/**
 * How long typing pauses before the name is checked. A named constant, a
 * Checklist A exception recorded on T-3.10: the browser's pacing, not a limit
 * the server enforces (that's 30 checks a minute, T-3.7).
 */
export const USERNAME_CHECK_DELAY_MS = 400;

/** The schema's format (T-1.9), the one rule the browser may hold to (D-082). */
const FORMAT = /^[a-z0-9._]{4,20}$/;

function useSettled(value: string, delayMs: number): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return settled;
}

/**
 * The username (T-3.7). Whether it's free, reserved or taken is the server's to
 * say (D-068, D-082); the page it names lives on this environment's own host,
 * from site.ts, never a hard-coded domain.
 */
export function UsernameStep({ me, host }: { me: Me; host: string }) {
  const advance = useAdvance();
  const [name, setName] = useState(me.profile.username ?? "");
  const settled = useSettled(name, USERNAME_CHECK_DELAY_MS);
  const wellFormed = FORMAT.test(name);
  const ownName = name === me.profile.username;
  const check = useUsernameAvailability(
    FORMAT.test(settled) && settled === name && !ownName ? settled : null,
  );
  const save = useSetUsername();
  const copy = save.isError ? errorCopy(save.error) : null;

  const free = ownName || (check.data?.available === true && settled === name);
  const status =
    !wellFormed || ownName
      ? null
      : settled !== name || check.isFetching
        ? t("onboarding.username.checking")
        : check.data?.available === true
          ? t("onboarding.username.available")
          : check.data?.available === false
            ? t("onboarding.username.taken")
            : null;
  const suggestion =
    check.data?.available === false && settled === name
      ? check.data.suggestion
      : null;

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (wellFormed && free) save.mutate(name, { onSuccess: advance });
      }}
    >
      <StepFrame
        index={6}
        title={t("onboarding.username.title")}
        sub={t("onboarding.username.sub")}
        back={stepPath("profile")}
        signedIn
        footer={
          <Button
            type="submit"
            fullWidth
            loading={save.isPending}
            disabled={!wellFormed || !free}
          >
            {t("onboarding.continue")}
          </Button>
        }
      >
        <Field
          label={t("onboarding.username.label")}
          placeholder={t("onboarding.username.placeholder")}
          helper={t("onboarding.username.help")}
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          value={name}
          // Stored in lowercase (T-3.7); shown that way as it's typed.
          onChange={(event) => setName(event.target.value.toLowerCase().trim())}
          error={copy?.fields.username}
        />
        <p aria-live="polite" className="text-small text-mute mt-2.5">
          {status}
          {suggestion && (
            <>
              {" "}
              <button
                type="button"
                className="text-accent underline underline-offset-2"
                onClick={() => setName(suggestion)}
              >
                {t("onboarding.username.suggestion", { name: suggestion })}
              </button>
            </>
          )}
        </p>
        {wellFormed && (
          <p className="text-small text-mute mt-1.5">
            {t("onboarding.username.page", { url: `${host}/@${name}` })}
          </p>
        )}
        {!copy?.fields.username && <FormError copy={copy} />}
      </StepFrame>
    </form>
  );
}
