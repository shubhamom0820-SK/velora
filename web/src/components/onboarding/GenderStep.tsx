"use client";

import { Lock } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import type { Me } from "@/lib/queries/me";
import { useSetGender, type Gender } from "@/lib/queries/onboarding";

import { errorCopy } from "./errorCopy";
import { FormError } from "./FormError";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";

const OPTIONS = [
  {
    value: "male",
    label: "onboarding.gender.man",
    note: "onboarding.gender.manNote",
  },
  {
    value: "female",
    label: "onboarding.gender.woman",
    note: "onboarding.gender.womanNote",
  },
] as const satisfies readonly { value: Gender; label: string; note: string }[];

/** Gender, once (D-008): the server refuses a change, and the database too (T-1.9). */
export function GenderStep({ me }: { me: Me }) {
  const advance = useAdvance();
  const [gender, setGender] = useState<Gender | null>(null);
  const save = useSetGender();
  const copy = save.isError ? errorCopy(save.error) : null;

  if (me.gender !== null) {
    return (
      <StepFrame
        index={3}
        title={t("onboarding.gender.title")}
        signedIn
        footer={
          <Button fullWidth onClick={() => advance(me)}>
            {t("onboarding.continue")}
          </Button>
        }
      >
        <p className="text-body">
          {me.gender === "male"
            ? t("onboarding.gender.answeredMan")
            : t("onboarding.gender.answeredWoman")}
        </p>
      </StepFrame>
    );
  }

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (gender) save.mutate(gender, { onSuccess: advance });
      }}
    >
      <StepFrame
        index={3}
        title={t("onboarding.gender.title")}
        sub={t("onboarding.gender.sub")}
        signedIn
        footer={
          <Button
            type="submit"
            fullWidth
            loading={save.isPending}
            disabled={!gender}
          >
            {t("onboarding.continue")}
          </Button>
        }
      >
        <fieldset className="flex flex-col gap-3">
          <legend className="sr-only">{t("onboarding.gender.title")}</legend>
          {OPTIONS.map((option) => (
            <label
              key={option.value}
              className={cx(
                "rounded-card flex cursor-pointer items-center gap-3 border-[1.5px] p-4",
                gender === option.value
                  ? "border-accent bg-accent-soft"
                  : "border-line",
              )}
            >
              <input
                type="radio"
                name="gender"
                value={option.value}
                checked={gender === option.value}
                onChange={() => setGender(option.value)}
                className="accent-accent size-5"
              />
              <span>
                <span className="text-ui text-ink block font-semibold">
                  {t(option.label)}
                </span>
                <span className="text-small text-mute block">
                  {t(option.note)}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
        <p className="bg-surface rounded-input text-small text-mute mt-5 flex items-start gap-2 p-3.5">
          <Icon icon={Lock} size={14} className="mt-0.5 shrink-0" />
          {t("onboarding.gender.lock")}
        </p>
        <FormError copy={copy} />
      </StepFrame>
    </form>
  );
}
