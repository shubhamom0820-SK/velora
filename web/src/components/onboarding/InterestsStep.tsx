"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { en } from "@/i18n/en";
import { t } from "@/i18n/t";
import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";
import { useInterests, useSetInterests } from "@/lib/queries/onboarding";

import { errorCopy } from "./errorCopy";
import { FormError } from "./FormError";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";

/** Exactly 5 (T-3.8), the schema's own count, so the browser may hold to it (D-082). */
const PICK = 5;

function interestLabel(id: number, fallback: string): string {
  const labels: Readonly<Record<string, string>> = en.interests;
  return labels[String(id)] ?? fallback;
}

/** Interests (T-3.8), in `en.ts`'s words by id (P-26). */
export function InterestsStep({ me }: { me: Me }) {
  const advance = useAdvance();
  const interests = useInterests();
  const [picked, setPicked] = useState<number[]>(me.profile.interest_ids);
  const save = useSetInterests();
  const copy = save.isError ? errorCopy(save.error) : null;

  function toggle(id: number) {
    setPicked((current) =>
      current.includes(id)
        ? current.filter((x) => x !== id)
        : current.length < PICK
          ? [...current, id]
          : current,
    );
  }

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (picked.length === PICK) save.mutate(picked, { onSuccess: advance });
      }}
    >
      <StepFrame
        index={9}
        title={t("onboarding.interests.title")}
        sub={t("onboarding.interests.sub", { count: picked.length })}
        back={stepPath("photos")}
        signedIn
        footer={
          <Button
            type="submit"
            fullWidth
            loading={save.isPending}
            disabled={picked.length !== PICK}
          >
            {t("onboarding.continue")}
          </Button>
        }
      >
        {interests.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : interests.isError ? (
          <ErrorState onRetry={() => void interests.refetch()} />
        ) : (
          <div className="flex flex-wrap gap-2">
            {interests.data.map((interest) => (
              <Chip
                key={interest.id}
                active={picked.includes(interest.id)}
                onClick={() => toggle(interest.id)}
              >
                {interestLabel(interest.id, interest.label)}
              </Chip>
            ))}
          </div>
        )}
        <FormError copy={copy} />
      </StepFrame>
    </form>
  );
}
