"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { ApiError } from "@/lib/api";
import type { Me } from "@/lib/queries/me";
import { useSetDob } from "@/lib/queries/onboarding";
import { useSession } from "@/store/session";

import { errorCopy } from "./errorCopy";
import { FormError } from "./FormError";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";

/** `2001-03-14` as people say it, "14 March 2001": the date as typed, never a time zone's. */
function inWords(isoDate: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${isoDate}T00:00:00Z`));
}

/**
 * The date of birth (D-079). The browser never judges it: no age check here and
 * no age worked out, because a refusal in the browser would let a minor change
 * the year where the server never sees the attempt, and the number would never
 * be barred. The server decides, in IST. A confirm step first, since the date
 * can't change once saved, and a date under 18 deletes the account (D-072).
 */
export function BirthdayStep({ me }: { me: Me }) {
  const advance = useAdvance();
  if (me.onboarding_step !== "dob") {
    return (
      <StepFrame
        index={2}
        title={t("onboarding.birthday.title")}
        signedIn
        footer={
          <Button fullWidth onClick={() => advance(me)}>
            {t("onboarding.continue")}
          </Button>
        }
      >
        <p className="text-body">
          {t("onboarding.birthday.answered", { age: me.age ?? "" })}
        </p>
      </StepFrame>
    );
  }
  return <BirthdayForm />;
}

function BirthdayForm() {
  const [dob, setDob] = useState("");
  const [confirming, setConfirming] = useState(false);
  const save = useSetDob();
  const advance = useAdvance();
  const queryClient = useQueryClient();
  const copy = save.isError ? errorCopy(save.error) : null;

  function confirm() {
    save.mutate(dob, {
      onSuccess: advance,
      onError: (error) => {
        setConfirming(false);
        if (error instanceof ApiError && error.code === "UNDERAGE") {
          // The account is gone (D-072): forget it here too, and say why.
          queryClient.clear();
          useSession.getState().endForUnderage();
        }
      },
    });
  }

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (dob) setConfirming(true);
      }}
    >
      <StepFrame
        index={2}
        title={t("onboarding.birthday.title")}
        sub={t("onboarding.birthday.sub", { app: APP_NAME })}
        signedIn
        footer={
          <Button type="submit" fullWidth disabled={!dob}>
            {t("onboarding.continue")}
          </Button>
        }
      >
        <Field
          type="date"
          label={t("onboarding.birthday.label")}
          value={dob}
          onChange={(event) => setDob(event.target.value)}
          error={copy?.fields.dob}
        />
        {!copy?.fields.dob && <FormError copy={copy} />}
      </StepFrame>
      <Sheet
        open={confirming}
        onClose={() => setConfirming(false)}
        title={t("onboarding.birthday.confirmTitle")}
        footer={
          <div className="flex flex-col gap-2.5">
            <Button fullWidth loading={save.isPending} onClick={confirm}>
              {t("onboarding.birthday.confirm")}
            </Button>
            <Button
              variant="ghost"
              fullWidth
              onClick={() => setConfirming(false)}
            >
              {t("onboarding.birthday.edit")}
            </Button>
          </div>
        }
      >
        <p className="text-body">
          {dob && t("onboarding.birthday.confirmBody", { date: inWords(dob) })}
        </p>
      </Sheet>
    </form>
  );
}
