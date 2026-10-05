"use client";

import { MapPin } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { APP_NAME } from "@/lib/app";
import { cx } from "@/lib/cx";
import {
  currentPosition,
  locationPermission,
  PositionError,
  type PositionFailure,
} from "@/lib/geolocation";
import { stepPath } from "@/lib/onboarding";
import type { Me } from "@/lib/queries/me";
import { useAreas, useSetLocation } from "@/lib/queries/onboarding";

import { errorCopy } from "./errorCopy";
import { FormError } from "./FormError";
import { StepFrame } from "./StepFrame";
import { useAdvance } from "./useAdvance";

/** Why the picker shows instead: the browser's answer, or the server's. */
type Why = PositionFailure | "outside";

/**
 * Where are you (T-4.10, D-220), after Name. Asks for the position once, and
 * only when the person taps to share it, having read why (D-034); a refusal,
 * no reading, or a position the server refuses (outside India) lands on the
 * area picker, saying which. A browser that has already said no goes straight
 * there, rather than offering a button that can't work.
 */
export function LocationStep({ me }: { me: Me }) {
  const advance = useAdvance();
  const save = useSetLocation();
  const [why, setWhy] = useState<Why | null>(null);
  const [picking, setPicking] = useState(false);
  const [locating, setLocating] = useState(false);
  const [area, setArea] = useState<string | null>(null);
  const areas = useAreas(picking);
  const copy = save.isError ? errorCopy(save.error) : null;

  useEffect(() => {
    let current = true;
    void locationPermission().then((state) => {
      if (current && state === "denied") {
        setWhy("denied");
        setPicking(true);
      }
    });
    return () => {
      current = false;
    };
  }, []);

  function toPicker(reason: Why | null) {
    setWhy(reason);
    setPicking(true);
  }

  async function share() {
    save.reset();
    setLocating(true);
    try {
      const position = await currentPosition();
      save.mutate(position, {
        onSuccess: advance,
        onError: (error) => {
          // The only refusal of a position the browser read: outside India.
          if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
            save.reset();
            toPicker("outside");
          }
        },
      });
    } catch (error) {
      toPicker(error instanceof PositionError ? error.reason : "unavailable");
    } finally {
      setLocating(false);
    }
  }

  const reason = why && (
    <p role="status" className="text-small text-mute mb-4">
      {t(`onboarding.location.why.${why}`, { app: APP_NAME })}
    </p>
  );

  if (!picking) {
    return (
      <StepFrame
        index={6}
        title={t("onboarding.location.title")}
        sub={t("onboarding.location.sub")}
        back={stepPath("profile")}
        signedIn
        footer={
          <div className="flex flex-col gap-2">
            <Button
              fullWidth
              loading={locating || save.isPending}
              onClick={() => void share()}
            >
              {t("onboarding.location.share")}
            </Button>
            <Button
              variant="ghost"
              fullWidth
              disabled={locating || save.isPending}
              onClick={() => toPicker(null)}
            >
              {t("onboarding.location.pickInstead")}
            </Button>
            {me.profile.location !== "none" && (
              <Button
                variant="ghost"
                fullWidth
                disabled={locating || save.isPending}
                onClick={() => advance(me)}
              >
                {t("onboarding.location.keep")}
              </Button>
            )}
          </div>
        }
      >
        <div className="flex flex-col items-center py-6">
          <Icon icon={MapPin} size={40} className="text-accent" />
        </div>
        {me.profile.location !== "none" && (
          <p className="text-small text-mute">
            {t("onboarding.location.isSet")}
          </p>
        )}
        <FormError copy={copy} />
      </StepFrame>
    );
  }

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (area) save.mutate({ area_id: area }, { onSuccess: advance });
      }}
    >
      <StepFrame
        index={6}
        title={t("onboarding.location.pickTitle")}
        sub={t("onboarding.location.pickSub")}
        back={stepPath("profile")}
        signedIn
        footer={
          <div className="flex flex-col gap-2">
            <Button
              type="submit"
              fullWidth
              loading={save.isPending}
              disabled={!area}
            >
              {t("onboarding.continue")}
            </Button>
            {why !== "denied" && (
              <Button
                variant="ghost"
                fullWidth
                disabled={save.isPending}
                onClick={() => {
                  save.reset();
                  setWhy(null);
                  setPicking(false);
                }}
              >
                {t("onboarding.location.useLocation")}
              </Button>
            )}
          </div>
        }
      >
        {reason}
        {areas.isPending ? (
          <Skeleton className="h-60 w-full" />
        ) : areas.isError ? (
          <ErrorState
            title={t("onboarding.location.areasFailed")}
            onRetry={() => void areas.refetch()}
          />
        ) : areas.data.length === 0 ? (
          <EmptyState icon={MapPin} title={t("onboarding.location.noAreas")} />
        ) : (
          <fieldset className="flex flex-col gap-2">
            <legend className="sr-only">
              {t("onboarding.location.areas")}
            </legend>
            {areas.data.map((option) => (
              <label
                key={option.id}
                className={cx(
                  "rounded-input flex cursor-pointer items-center gap-3 border-[1.5px] px-4 py-3",
                  area === option.id
                    ? "border-accent bg-accent-soft"
                    : "border-line",
                )}
              >
                <input
                  type="radio"
                  name="area"
                  value={option.id}
                  checked={area === option.id}
                  onChange={() => setArea(option.id)}
                  className="accent-accent size-5"
                />
                <span className="text-ui text-ink">{option.name}</span>
              </label>
            ))}
          </fieldset>
        )}
        <FormError copy={copy} />
      </StepFrame>
    </form>
  );
}
