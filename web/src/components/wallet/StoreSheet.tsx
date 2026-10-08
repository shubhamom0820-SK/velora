"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/useToast";
import { t, type MessageKey } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { APP_NAME } from "@/lib/app";
import { checkoutPath, checkoutWindowFor } from "@/lib/checkout-path";
import { creditsText } from "@/lib/credits";
import { useMe } from "@/lib/queries/me";
import {
  type Order,
  type Pack,
  useCreateOrder,
  usePacks,
  usePaymentWait,
  useRefreshPacks,
} from "@/lib/queries/store";
import { usePrices } from "@/lib/queries/wallet";
import { openRazorpay } from "@/lib/razorpay";
import { useSession } from "@/store/session";
import { useStoreSheet } from "@/store/store-sheet";

import { CheckoutState } from "./CheckoutState";
import { ClaimForm } from "./ClaimForm";
import { PackList } from "./PackList";

/** A pack and the order made for it: what every step after the tap carries. */
type Paying = { pack: Pack; order: Order };

type Flow =
  | { step: "packs"; notice: MessageKey | null }
  | { step: "opening" }
  | ({ step: "standin" | "razorpay" | "notPaid" } & Paying)
  // Confirming for 60 s, then "still confirming" (the poll's own timeout);
  // `attempt` restarts the 60 s.
  | ({ step: "confirming"; attempt: number } & Paying)
  | ({ step: "claim" } & Paying);

const PACKS: Flow = { step: "packs", notice: null };

/** Why an order wasn't made, in his words. Nothing was charged in any case. */
function orderRefusal(error: unknown): MessageKey {
  if (!(error instanceof ApiError)) return "wallet.store.orderFailed";
  switch (error.code) {
    case "NOT_FOUND":
      return "wallet.store.packGone";
    case "PROVIDER_UNAVAILABLE":
      return "wallet.store.unavailable";
    case "RATE_LIMITED":
      return "wallet.store.tooMany";
    default:
      return "wallet.store.orderFailed";
  }
}

type View = Exclude<Flow["step"], "razorpay"> | "waiting";

const TITLE: Record<View, MessageKey> = {
  packs: "wallet.store.title",
  opening: "wallet.store.title",
  standin: "wallet.store.standin.title",
  confirming: "wallet.store.confirming.title",
  notPaid: "wallet.store.notPaid.title",
  waiting: "wallet.store.waiting.title",
  claim: "wallet.store.claim.open",
};

/** A fresh Idempotency-Key for one pack's order: 36 of `A-Za-z0-9-`. */
function newKey(): string {
  return crypto.randomUUID();
}

/**
 * The store sheet (T-8.7), for men: opened by the balance pill, "Buy Velas"
 * and any mutation refused with `INSUFFICIENT_CREDITS`. A woman is never shown
 * it, and her browser never asks for packs (`NOT_ALLOWED`, D-076).
 *
 * A tap on a pack makes its order and checks the order's amount is the price
 * shown; then Razorpay's window, or the stand-in on a local or CI build
 * (D-761). Paid, the store waits for the webhook (`usePaymentWait`) and then
 * says how many Velas arrived. Closed without paying, "didn't go through",
 * whose "Try again" reopens the same order, never a second one (D-761). No
 * `paid` within 60 s: "still confirming". Both of those carry the claim.
 *
 * Behind the PIN lock any sheet is `inert` (P-220); this one closes as well
 * when the lock goes up, and when the app's routes unmount, so a sign-out with
 * it open doesn't bring it back at the next sign-in. Closing it starts it over
 * at the packs, and anything still in flight from before is ignored.
 */
export function StoreSheet() {
  const open = useStoreSheet((state) => state.open);
  const hide = useStoreSheet((state) => state.hide);
  const locked = useSession((state) => state.locked);
  const isMan = useMe().data?.gender === "male";
  const toast = useToast();
  const [flow, setFlow] = useState<Flow>(PACKS);
  // Bumped whenever the sheet starts over: a callback from an earlier run
  // (an order, Razorpay's window) finds it changed and does nothing.
  const [run, setRun] = useState(0);
  const currentRun = useRef(run);
  // Closed, it starts over at the packs: adjusted while rendering, as React
  // has it for state that follows a prop, never in an effect.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (!open) {
      setFlow(PACKS);
      setRun(run + 1);
    }
  }

  const packs = usePacks({ enabled: open && isMan });
  const prices = usePrices({ enabled: open && isMan });
  const createOrder = useCreateOrder();
  const refreshPacks = useRefreshPacks();
  const confirming = flow.step === "confirming" ? flow : null;
  const wait = usePaymentWait(
    confirming?.order.payment_id ?? null,
    confirming?.attempt ?? 0,
  );

  useEffect(() => {
    if (locked) hide();
  }, [locked, hide]);
  useEffect(() => hide, [hide]);
  useEffect(() => {
    currentRun.current = run;
  }, [run]);

  const paidVelas = wait.state === "paid" ? wait.velas : null;
  useEffect(() => {
    if (!confirming || paidVelas === null) return;
    toast.show({
      message: t("wallet.store.paid", { velas: creditsText(paidVelas) }),
    });
    hide();
  }, [confirming, paidVelas, toast, hide]);

  // What shows: the flow's step, or "still confirming" once the poll's 60 s
  // ran out with no `paid`.
  const view: View | "razorpay" =
    flow.step === "confirming" && wait.state === "timedOut"
      ? "waiting"
      : flow.step;

  if (!isMan) return null;

  /** Calls `then` only if the sheet hasn't started over since. */
  function inThisRun<A extends unknown[]>(then: (...args: A) => void) {
    const mine = currentRun.current;
    return (...args: A) => {
      if (currentRun.current === mine) then(...args);
    };
  }

  function openWindow({ pack, order }: Paying) {
    // Only the pack and the order: a step's own fields never ride along.
    const paying: Paying = { pack, order };
    const window = checkoutWindowFor(checkoutPath(), paying.order.key_id);
    if (window === null) {
      setFlow({ step: "packs", notice: "wallet.store.notHere" });
      return;
    }
    if (window === "standin") {
      setFlow({ step: "standin", ...paying });
      return;
    }
    setFlow({ step: "razorpay", ...paying });
    openRazorpay(
      {
        keyId: paying.order.key_id,
        orderId: paying.order.order_id,
        amountPaise: paying.order.amount_paise,
        name: APP_NAME,
        description: creditsText(paying.pack.credits),
      },
      {
        onPaid: inThisRun(() =>
          setFlow({ step: "confirming", attempt: 0, ...paying }),
        ),
        onDismiss: inThisRun(() => setFlow({ step: "notPaid", ...paying })),
      },
    ).catch(
      inThisRun(() =>
        setFlow({ step: "packs", notice: "wallet.store.windowFailed" }),
      ),
    );
  }

  function buy(pack: Pack) {
    setFlow({ step: "opening" });
    createOrder.mutate(
      { packId: pack.id, key: newKey() },
      {
        onSuccess: inThisRun((order: Order) => {
          if (order.amount_paise !== pack.price_paise) {
            refreshPacks();
            setFlow({ step: "packs", notice: "wallet.store.priceChanged" });
            return;
          }
          openWindow({ pack, order });
        }),
        onError: inThisRun((error: Error) => {
          if (error instanceof ApiError && error.code === "NOT_FOUND") {
            refreshPacks();
          }
          setFlow({ step: "packs", notice: orderRefusal(error) });
        }),
      },
    );
  }

  function body() {
    switch (flow.step) {
      case "packs":
      case "opening":
        return (
          <div className="flex flex-col gap-4">
            {flow.step === "packs" && flow.notice && (
              <p role="alert" className="text-small text-accent">
                {t(flow.notice)}
              </p>
            )}
            {packs.isPending ? (
              <div
                aria-busy="true"
                aria-label={t("wallet.store.loading")}
                className="flex flex-col gap-5 py-3"
              >
                <Skeleton />
                <Skeleton className="w-5/6" />
                <Skeleton className="w-2/3" />
                <Skeleton className="w-5/6" />
              </div>
            ) : packs.isError ? (
              <ErrorState
                title={t("wallet.store.failed")}
                onRetry={() => void packs.refetch()}
              />
            ) : packs.data.length === 0 ? (
              <EmptyState
                title={t("wallet.store.emptyTitle")}
                body={t("wallet.store.emptyBody")}
              />
            ) : (
              <PackList
                packs={packs.data}
                threadPrice={prices.data?.thread_open}
                disabled={flow.step === "opening"}
                onBuy={buy}
              />
            )}
            {flow.step === "opening" && (
              <p className="text-small text-mute flex items-center gap-2 self-center">
                <Spinner size={16} label={t("wallet.store.opening")} />
                {t("wallet.store.opening")}
              </p>
            )}
            <p className="text-small text-mute text-center">
              {t("wallet.store.final")}{" "}
              <Link href="/refunds" className="underline underline-offset-2">
                {t("wallet.store.refunds")}
              </Link>
            </p>
          </div>
        );
      case "standin": {
        const paying = flow;
        return (
          <CheckoutState
            view="standin"
            onPay={() => setFlow({ ...paying, step: "confirming", attempt: 0 })}
            onClose={() => setFlow({ ...paying, step: "notPaid" })}
          />
        );
      }
      case "confirming": {
        const paying = flow;
        if (view === "waiting") {
          return (
            <CheckoutState
              view="waiting"
              onCheck={() =>
                setFlow({ ...paying, attempt: paying.attempt + 1 })
              }
              onClaim={() =>
                setFlow({
                  step: "claim",
                  pack: paying.pack,
                  order: paying.order,
                })
              }
              onClose={hide}
            />
          );
        }
        return <CheckoutState view="confirming" />;
      }
      case "razorpay":
        return <CheckoutState view="confirming" />;
      case "notPaid": {
        const paying = flow;
        return (
          <CheckoutState
            view="notPaid"
            onRetry={() => openWindow(paying)}
            onPacks={() => setFlow(PACKS)}
            onClaim={() =>
              setFlow({ step: "claim", pack: paying.pack, order: paying.order })
            }
          />
        );
      }
      case "claim":
        return <ClaimForm paymentId={flow.order.payment_id} onDone={hide} />;
    }
  }

  return (
    <Sheet
      // Razorpay's own window is up: this sheet steps aside until it closes.
      open={open && !locked && view !== "razorpay"}
      onClose={hide}
      title={t(TITLE[view === "razorpay" ? "confirming" : view])}
    >
      {body()}
    </Sheet>
  );
}
