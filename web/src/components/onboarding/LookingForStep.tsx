"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { en } from "@/i18n/en";
import { t } from "@/i18n/t";
import type { Me } from "@/lib/queries/me";
import {
  useIntents,
  useSetSeeking,
  type Seeking,
} from "@/lib/queries/onboarding";

import { errorCopy } from "./errorCopy";
import { FormError } from "./FormError";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";

const SEEKING = [
  ["women", "onboarding.lookingFor.women"],
  ["men", "onboarding.lookingFor.men"],
  ["everyone", "onboarding.lookingFor.everyone"],
] as const satisfies readonly (readonly [Seeking, string])[];

/** 1 to 3 intents (D-041); the schema's own limit, so the browser may hold to it (D-082). */
const MAX_INTENTS = 3;

/** An intent's words from `en.ts` by id (P-26), the database's label only for an id not there. */
function intentLabel(id: number, fallback: string): string {
  const labels: Readonly<Record<string, string>> = en.intents;
  return labels[String(id)] ?? fallback;
}

/** Seeking and intents (T-3.6). No back arrow: behind it is a gender that can't change (D-080). */
export function LookingForStep({ me }: { me: Me }) {
  const advance = useAdvance();
  const intents = useIntents();
  const [seeking, setSeeking] = useState<Seeking | null>(me.profile.seeking);
  const [picked, setPicked] = useState<number[]>(me.profile.intent_ids);
  const save = useSetSeeking();
  const copy = save.isError ? errorCopy(save.error) : null;
  const ready =
    seeking !== null && picked.length >= 1 && picked.length <= MAX_INTENTS;

  function toggle(id: number) {
    setPicked((current) =>
      current.includes(id)
        ? current.filter((x) => x !== id)
        : current.length < MAX_INTENTS
          ? [...current, id]
          : current,
    );
  }

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (ready)
          save.mutate({ seeking, intent_ids: picked }, { onSuccess: advance });
      }}
    >
      <StepFrame
        index={4}
        title={t("onboarding.lookingFor.title")}
        signedIn
        footer={
          <Button
            type="submit"
            fullWidth
            loading={save.isPending}
            disabled={!ready}
          >
            {t("onboarding.continue")}
          </Button>
        }
      >
        <p className="text-small text-mute mb-2.5">
          {t("onboarding.lookingFor.showMe")}
        </p>
        <div className="flex flex-wrap gap-2">
          {SEEKING.map(([value, label]) => (
            <Chip
              key={value}
              active={seeking === value}
              onClick={() => setSeeking(value)}
            >
              {t(label)}
            </Chip>
          ))}
        </div>
        <p className="text-small text-mute mt-6 mb-2.5">
          {t("onboarding.lookingFor.intents")} ·{" "}
          {t("onboarding.lookingFor.intentsHelp")}
        </p>
        {intents.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : intents.isError ? (
          <ErrorState onRetry={() => void intents.refetch()} />
        ) : (
          <div className="flex flex-wrap gap-2">
            {intents.data.map((intent) => (
              <Chip
                key={intent.id}
                active={picked.includes(intent.id)}
                onClick={() => toggle(intent.id)}
              >
                {intentLabel(intent.id, intent.label)}
              </Chip>
            ))}
          </div>
        )}
        <FormError copy={copy} />
      </StepFrame>
    </form>
  );
}
