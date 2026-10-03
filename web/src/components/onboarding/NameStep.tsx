"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { t } from "@/i18n/t";
import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";
import { useUpdateProfile } from "@/lib/queries/onboarding";
import { z } from "@/lib/zod";

import { errorCopy } from "./errorCopy";
import { FormError } from "./FormError";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";

/**
 * Lengths only (D-082), as T-3.7 states them: what counts as a letter, and
 * every other rule, is the server's, and comes back inline.
 */
const nameForm = z.object({
  first_name: z.string().trim().min(1).max(30),
  hometown: z.string().trim().min(1).max(40),
  city: z.string().trim().min(1).max(40),
});

/** First name, hometown and city (T-3.7): the `profile` step. */
export function NameStep({ me }: { me: Me }) {
  const advance = useAdvance();
  const save = useUpdateProfile();
  const form = useForm({
    resolver: zodResolver(nameForm),
    mode: "onChange",
    defaultValues: {
      first_name: me.profile.first_name ?? "",
      hometown: me.profile.hometown ?? "",
      city: me.profile.city ?? "",
    },
  });
  const copy = save.isError ? errorCopy(save.error) : null;

  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((values) =>
        save.mutate(values, { onSuccess: advance }),
      )}
    >
      <StepFrame
        index={5}
        title={t("onboarding.name.title")}
        sub={t("onboarding.name.sub")}
        back={stepPath("seeking")}
        signedIn
        footer={
          <Button
            type="submit"
            fullWidth
            loading={save.isPending}
            disabled={!form.formState.isValid}
          >
            {t("onboarding.continue")}
          </Button>
        }
      >
        <div className="flex flex-col gap-3">
          <Field
            label={t("onboarding.name.firstName")}
            placeholder={t("onboarding.name.firstNamePlaceholder")}
            autoComplete="given-name"
            error={copy?.fields.first_name}
            {...form.register("first_name")}
          />
          <Field
            label={t("onboarding.name.hometown")}
            placeholder={t("onboarding.name.hometownPlaceholder")}
            error={copy?.fields.hometown}
            {...form.register("hometown")}
          />
          <Field
            label={t("onboarding.name.city")}
            placeholder={t("onboarding.name.cityPlaceholder")}
            autoComplete="address-level2"
            error={copy?.fields.city}
            {...form.register("city")}
          />
        </div>
        {copy && Object.keys(copy.fields).length === 0 && (
          <FormError copy={copy} />
        )}
      </StepFrame>
    </form>
  );
}
