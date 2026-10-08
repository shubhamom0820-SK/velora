"use client";

import { CircleAlert, Clock } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { t } from "@/i18n/t";

export type CheckoutView =
  | { view: "standin"; onPay: () => void; onClose: () => void }
  | { view: "confirming" }
  | {
      view: "notPaid";
      onRetry: () => void;
      onPacks: () => void;
      onClaim: () => void;
    }
  | {
      view: "waiting";
      onCheck: () => void;
      onClaim: () => void;
      onClose: () => void;
    };

function Actions({ children }: { children: ReactNode }) {
  return <div className="mt-6 flex w-full flex-col gap-2">{children}</div>;
}

/**
 * The store's states between a tap and the Velas (T-8.7), from the
 * prototype's checkout states (processing, failed) and built from existing
 * parts only: the stand-in for Razorpay's window on local and CI builds
 * (D-761), "Confirming", "didn't go through" with Try again, and "still
 * confirming" when the webhook hasn't landed in 60 s. The last two carry the
 * claim (P-481): the payment's id is known there.
 */
export function CheckoutState(props: CheckoutView) {
  switch (props.view) {
    case "standin":
      return (
        <div className="flex flex-col">
          <p className="text-body text-mute">
            {t("wallet.store.standin.body")}
          </p>
          <Actions>
            <Button fullWidth onClick={props.onPay}>
              {t("wallet.store.standin.pay")}
            </Button>
            <Button variant="ghost" fullWidth onClick={props.onClose}>
              {t("wallet.store.standin.close")}
            </Button>
          </Actions>
        </div>
      );
    case "confirming":
      return (
        <div className="flex flex-col items-center gap-3 py-4 text-center">
          <Spinner size={28} label={t("wallet.store.confirming.title")} />
          <p className="text-body text-mute">
            {t("wallet.store.confirming.body")}
          </p>
        </div>
      );
    case "notPaid":
      return (
        <div className="flex flex-col items-center text-center">
          <Icon icon={CircleAlert} size={28} className="text-accent" />
          <p className="text-body text-mute mt-3">
            {t("wallet.store.notPaid.body")}
          </p>
          <Actions>
            <Button fullWidth onClick={props.onRetry}>
              {t("wallet.store.notPaid.retry")}
            </Button>
            <Button variant="ghost" fullWidth onClick={props.onPacks}>
              {t("wallet.store.notPaid.packs")}
            </Button>
            <Button variant="ghost" fullWidth onClick={props.onClaim}>
              {t("wallet.store.claim.open")}
            </Button>
          </Actions>
        </div>
      );
    case "waiting":
      return (
        <div className="flex flex-col items-center text-center">
          <Icon icon={Clock} size={28} className="text-mute" />
          <p className="text-body text-mute mt-3">
            {t("wallet.store.waiting.body")}
          </p>
          <Actions>
            <Button fullWidth onClick={props.onCheck}>
              {t("wallet.store.waiting.check")}
            </Button>
            <Button variant="ghost" fullWidth onClick={props.onClaim}>
              {t("wallet.store.claim.open")}
            </Button>
            <Button variant="ghost" fullWidth onClick={props.onClose}>
              {t("wallet.store.close")}
            </Button>
          </Actions>
        </div>
      );
  }
}
