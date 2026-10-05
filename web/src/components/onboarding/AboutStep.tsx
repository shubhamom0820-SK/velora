"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { TextArea } from "@/components/ui/TextArea";
import { t } from "@/i18n/t";
import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";
import { useUpdateProfile } from "@/lib/queries/onboarding";

import { errorCopy } from "./errorCopy";
import { FormError } from "./FormError";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";

/** 40 to 300 characters, trimmed (T-3.7): the length is the schema's (D-082). */
const ABOUT_MIN = 40;
const ABOUT_MAX = 300;

/**
 * About (T-3.7's `about` step). No links or phone numbers is the server's rule,
 * and its refusal comes back beside the field (D-082).
 */
export function AboutStep({ me }: { me: Me }) {
  const advance = useAdvance();
  const [about, setAbout] = useState(me.profile.about ?? "");
  const save = useUpdateProfile();
  const copy = save.isError ? errorCopy(save.error) : null;
  const length = about.trim().length;
  const short = ABOUT_MIN - length;

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (short <= 0)
          save.mutate({ about: about.trim() }, { onSuccess: advance });
      }}
    >
      <StepFrame
        index={8}
        title={t("onboarding.about.title")}
        sub={t("onboarding.about.sub")}
        back={stepPath("username")}
        signedIn
        footer={
          <Button
            type="submit"
            fullWidth
            loading={save.isPending}
            disabled={short > 0}
          >
            {short > 0
              ? t("onboarding.about.moreNeeded", { count: short })
              : t("onboarding.continue")}
          </Button>
        }
      >
        <TextArea
          label={t("onboarding.about.label")}
          placeholder={t("onboarding.about.placeholder")}
          rows={7}
          maxLength={ABOUT_MAX}
          value={about}
          onChange={(event) => setAbout(event.target.value)}
          error={copy?.fields.about}
        />
        {!copy?.fields.about && <FormError copy={copy} />}
      </StepFrame>
    </form>
  );
}
