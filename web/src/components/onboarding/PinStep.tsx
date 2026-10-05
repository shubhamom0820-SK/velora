"use client";

import { useState } from "react";

import { RELOCK_AFTER_HIDDEN_MS } from "@/components/session/PinLock";
import { Button } from "@/components/ui/Button";
import { PinPad } from "@/components/ui/PinPad";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";
import { useSetPin, useSkipPin } from "@/lib/queries/onboarding";

import { errorCopy } from "./errorCopy";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";

type Stage = { kind: "set" } | { kind: "confirm"; first: string };

/**
 * The PIN (T-3.9, D-069): set, confirm, send. Which PINs are too easy is the
 * server's list alone (D-082); a refusal returns to "set" with its reason.
 * A PIN already set isn't changed here: that needs the current one.
 */
export function PinStep({ me }: { me: Me }) {
  const advance = useAdvance();
  const [stage, setStage] = useState<Stage>({ kind: "set" });
  const [pin, setPin] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const save = useSetPin();
  const skip = useSkipPin();

  if (me.has_pin) {
    return (
      <StepFrame
        index={11}
        title={t("onboarding.pin.setTitle")}
        back={stepPath("interests")}
        signedIn
        footer={
          <Button fullWidth onClick={() => advance(me)}>
            {t("onboarding.continue")}
          </Button>
        }
      >
        <p className="text-body">{t("onboarding.pin.answered")}</p>
      </StepFrame>
    );
  }

  function complete(value: string) {
    setPin("");
    if (stage.kind === "set") {
      setMessage(null);
      setStage({ kind: "confirm", first: value });
      return;
    }
    if (value !== stage.first) {
      setStage({ kind: "set" });
      setMessage(t("onboarding.pin.mismatch"));
      return;
    }
    save.mutate(value, {
      onSuccess: advance,
      onError: (error) => {
        const copy = errorCopy(error);
        setStage({ kind: "set" });
        setMessage(copy.fields.pin ?? copy.message);
      },
    });
  }

  const confirming = stage.kind === "confirm";
  return (
    <StepFrame
      index={11}
      title={
        confirming
          ? t("onboarding.pin.confirmTitle")
          : t("onboarding.pin.setTitle")
      }
      sub={
        confirming
          ? t("onboarding.pin.confirmSub")
          : t("onboarding.pin.setSub", {
              app: APP_NAME,
              minutes: RELOCK_AFTER_HIDDEN_MS / 60_000,
            })
      }
      back={
        confirming
          ? () => {
              setPin("");
              setStage({ kind: "set" });
            }
          : stepPath("interests")
      }
      signedIn
      footer={
        <button
          type="button"
          className="text-small text-mute w-full py-2 underline underline-offset-2"
          onClick={() => {
            if (!skip.isPending) skip.mutate(undefined, { onSuccess: advance });
          }}
        >
          {t("onboarding.pin.skip")}
        </button>
      }
    >
      <div className="flex flex-col items-center pt-2">
        <PinPad
          value={pin}
          onChange={setPin}
          onComplete={complete}
          disabled={save.isPending || skip.isPending}
        />
        {(message ?? (skip.isError ? errorCopy(skip.error).message : null)) && (
          <p role="alert" className="text-small text-accent mt-6 text-center">
            {message ?? errorCopy(skip.error).message}
          </p>
        )}
      </div>
    </StepFrame>
  );
}
