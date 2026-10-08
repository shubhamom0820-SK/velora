"use client";

import { CircleCheck } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { t, type MessageKey } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { cx } from "@/lib/cx";
import { type ClaimReason, useClaim } from "@/lib/queries/store";

/** The two kinds, never a change of mind (D-580, D-230). */
const REASONS = [
  "missing_velas",
  "duplicate_charge",
] as const satisfies readonly ClaimReason[];

/** What the API's refusal means, in his words (04-API, `POST /refund-requests`). */
function refusal(error: unknown): MessageKey {
  if (!(error instanceof ApiError)) return "wallet.store.claim.failed";
  switch (error.code) {
    case "ALREADY_EXISTS":
      return "wallet.store.claim.already";
    case "NOT_ALLOWED":
      return "wallet.store.claim.granted";
    case "NOT_FOUND":
      return "wallet.store.claim.notFound";
    case "RATE_LIMITED":
      return "wallet.store.claim.tooMany";
    default:
      return "wallet.store.claim.failed";
  }
}

type ClaimFormProps = {
  paymentId: string;
  onDone: () => void;
};

/**
 * The man's claim on a payment that broke (P-481, D-580), from the checkout's
 * "didn't go through" and "still confirming" sheets, where the payment's id is
 * known. One of the two kinds and nothing in his words. Sent, it says what
 * happens next as `/refunds` does, with no promise of when. A claim from the
 * history waits for a list of his payments (P-662).
 */
export function ClaimForm({ paymentId, onDone }: ClaimFormProps) {
  const [reason, setReason] = useState<ClaimReason | null>(null);
  const claim = useClaim();
  const errorId = useId();

  if (claim.isSuccess) {
    return (
      <section
        role="status"
        className="flex flex-col items-center gap-2 py-2 text-center"
      >
        <Icon icon={CircleCheck} size={28} className="text-accent" />
        <h3 className="text-title-2 text-ink">
          {t("wallet.store.claim.sentTitle")}
        </h3>
        <p className="text-small text-mute">
          {t("wallet.store.claim.sentBody")}
        </p>
        <Button fullWidth onClick={onDone} className="mt-4">
          {t("wallet.store.close")}
        </Button>
      </section>
    );
  }

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (reason && !claim.isPending) claim.mutate({ paymentId, reason });
      }}
    >
      <fieldset
        className="flex flex-col gap-3"
        aria-describedby={claim.isError ? errorId : undefined}
      >
        <legend className="sr-only">{t("wallet.store.claim.reasons")}</legend>
        {REASONS.map((value) => (
          <label
            key={value}
            className={cx(
              "rounded-card flex cursor-pointer items-center gap-3 border-[1.5px] p-4",
              reason === value ? "border-accent bg-accent-soft" : "border-line",
            )}
          >
            <input
              type="radio"
              name="claim-reason"
              value={value}
              checked={reason === value}
              onChange={() => setReason(value)}
              className="accent-accent size-5"
            />
            <span className="text-ui text-ink font-semibold">
              {t(`wallet.store.claim.${value}`)}
            </span>
          </label>
        ))}
      </fieldset>
      <p className="text-small text-mute">{t("wallet.store.claim.final")}</p>
      {claim.isError && (
        <p id={errorId} role="alert" className="text-small text-accent">
          {t(refusal(claim.error))}
        </p>
      )}
      <Button
        type="submit"
        fullWidth
        disabled={reason === null}
        loading={claim.isPending}
      >
        {t("wallet.store.claim.send")}
      </Button>
    </form>
  );
}
