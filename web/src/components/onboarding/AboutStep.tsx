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

/** Up to 300 characters, trimmed (T-3.7): the length is the schema's (D-082). */
const ABOUT_MAX = 300;

const SKIP =
  "text-small text-mute mt-3 w-full py-2 underline underline-offset-2";

/**
 * About (T-3.7's `about` step). Optional (D-951): "Skip for now" saves none,
 * and shows only while the box is empty, so it never throws away what someone
 * wrote. No links or phone numbers is the server's rule, and its refusal comes
 * back beside the field (D-082).
 */
export function AboutStep({ me }: { me: Me }) {
  const advance = useAdvance();
  const [about, setAbout] = useState(me.profile.about ?? "");
  const save = useUpdateProfile();
  const copy = save.isError ? errorCopy(save.error) : null;
  const written = about.trim();

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (written) save.mutate({ about: written }, { onSuccess: advance });
      }}
    >
      <StepFrame
        index={8}
        title={t("onboarding.about.title")}
        sub={t("onboarding.about.sub")}
        back={stepPath("username")}
        signedIn
        footer={
          <>
            <Button
              type="submit"
              fullWidth
              loading={save.isPending}
              disabled={!written}
            >
              {t("onboarding.continue")}
            </Button>
            {!written && (
              <button
                type="button"
                className={SKIP}
                disabled={save.isPending}
                onClick={() =>
                  save.mutate({ about: "" }, { onSuccess: advance })
                }
              >
                {t("onboarding.about.skip")}
              </button>
            )}
          </>
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
