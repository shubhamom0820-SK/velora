"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { GiftGrid } from "@/components/ui/GiftGrid";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { creditsText } from "@/lib/credits";
import { type Gift, useGifts, useSendGift } from "@/lib/queries/gifts";

/** The next Monday, when his free sends come back (D-650): "Monday, 12 October", in IST. */
export const resetDay = new Intl.DateTimeFormat("en-IN", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: "Asia/Kolkata",
});

/** How long the cooldown has left, from `retry_after_s`, rounded up: "5h 12m", "3m". */
export function waitText(seconds: number): string {
  const minutes = Math.max(1, Math.ceil(seconds / 60));
  const hours = Math.floor(minutes / 60);
  return hours > 0
    ? t("gifts.waitHours", { hours, minutes: minutes % 60 })
    : t("gifts.waitMinutes", { minutes });
}

/** The price in words: "Free" for 0, else "10 Velas". */
function priceText(price: number): string {
  return price === 0 ? t("gifts.free") : creditsText(price);
}

/** A send's key, sent again by another tap on the same gift at the same price. */
type Attempt = { giftId: string; price: number; key: string };

/**
 * His gift sheet on a woman's profile (T-8.10): D-231's four gifts, each at
 * the price he would pay now, and his free sends left this week. Built from
 * existing parts only (the founder, 9 October 2026), as T-8.7's store was.
 *
 * The price shown is the price sent (P-56, D-600): 0 while a free send is
 * left, else the gift's `credits` from `GET /gifts`, never `/prices`. If the
 * API says the price changed, the sheet shows the one it gave, and the next
 * tap sends that. The same gift at the same price keeps its key, so trying
 * again after no answer is the same send (D-653); anything else is a new key.
 * A send the API refused wrote nothing, so its key being sent again is
 * harmless.
 *
 * Mounted only while open, so closing it forgets everything it learned.
 */
export function GiftSheet({
  recipientId,
  name,
  onClose,
}: {
  recipientId: string;
  name: string;
  onClose: () => void;
}) {
  const toast = useToast();
  const catalogue = useGifts();
  const send = useSendGift();
  const [selected, setSelected] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // What the API said a gift costs now (`PRICE_CHANGED`'s `details.price`):
  // the catalogue's gifts are held a minute on the server (D-652).
  const [repriced, setRepriced] = useState<Record<string, number>>({});
  // Gifts she had from him inside the cooldown, refused until the sheet reopens.
  const [cooling, setCooling] = useState<ReadonlySet<string>>(new Set());
  const [attempt, setAttempt] = useState<Attempt | null>(null);

  const freeLeft = catalogue.data?.free_sends_left ?? 0;
  const priceOf = (gift: Gift) =>
    repriced[gift.id] ?? (freeLeft > 0 ? 0 : gift.credits);
  const gifts = catalogue.data?.gifts ?? [];
  const chosen = gifts.find((gift) => gift.id === selected) ?? null;

  function onSelect(id: string) {
    setSelected(id);
    setNotice(null);
  }

  function onSend() {
    if (!chosen) return;
    const price = priceOf(chosen);
    const key =
      attempt?.giftId === chosen.id && attempt.price === price
        ? attempt.key
        : crypto.randomUUID();
    setAttempt({ giftId: chosen.id, price, key });
    setNotice(null);
    send.mutate(
      {
        recipient_id: recipientId,
        gift_id: chosen.id,
        shown_price: price,
        key,
      },
      {
        onSuccess: () => {
          toast.show({
            message: t("gifts.sent", { gift: chosen.label, name }),
          });
          onClose();
        },
        onError: (error) => {
          if (!(error instanceof ApiError)) {
            setNotice(t("gifts.failed"));
            return;
          }
          switch (error.code) {
            case "INSUFFICIENT_CREDITS":
              // The store sheet opens (QueryProvider); this one makes way.
              onClose();
              return;
            case "PRICE_CHANGED": {
              const now = Number(error.details?.price);
              setRepriced((before) => ({ ...before, [chosen.id]: now }));
              setNotice(
                now === 0
                  ? t("gifts.nowFree")
                  : t("gifts.priceChanged", { velas: creditsText(now) }),
              );
              return;
            }
            case "GIFT_COOLDOWN":
              setCooling((before) => new Set(before).add(chosen.id));
              setNotice(
                t("gifts.cooldown", {
                  name,
                  gift: chosen.label,
                  wait: waitText(Number(error.details?.retry_after_s)),
                }),
              );
              return;
            case "NOT_FOUND":
            case "NOT_ALLOWED":
              setNotice(t("gifts.unavailable", { name }));
              return;
            default:
              setNotice(t("gifts.failed"));
          }
        },
      },
    );
  }

  const note = !catalogue.data
    ? undefined
    : freeLeft > 0
      ? t(freeLeft === 1 ? "gifts.freeLeft.one" : "gifts.freeLeft.other", {
          count: freeLeft,
        })
      : catalogue.data.free_sends_reset_at
        ? t("gifts.noneLeft", {
            date: resetDay.format(new Date(catalogue.data.free_sends_reset_at)),
          })
        : undefined;

  return (
    <Sheet
      open
      onClose={onClose}
      title={t("gifts.title", { name })}
      footer={
        catalogue.data && (
          <Button
            fullWidth
            loading={send.isPending}
            disabled={!chosen || cooling.has(chosen.id)}
            onClick={onSend}
          >
            {chosen
              ? t("gifts.send", {
                  gift: chosen.label,
                  price: priceText(priceOf(chosen)),
                })
              : t("gifts.choose")}
          </Button>
        )
      }
    >
      {catalogue.isPending ? (
        <div aria-busy className="grid grid-cols-2 gap-3">
          {[0, 1, 2, 3].map((n) => (
            <Skeleton key={n} className="rounded-card h-28" />
          ))}
        </div>
      ) : catalogue.isError ? (
        <ErrorState
          title={t("gifts.loadFailed")}
          onRetry={() => void catalogue.refetch()}
        />
      ) : (
        <div className="flex flex-col gap-3">
          <GiftGrid
            gifts={gifts.map((gift) => ({
              id: gift.id,
              label: gift.label,
              asset: gift.asset,
              price: priceText(priceOf(gift)),
            }))}
            selected={selected}
            onSelect={onSelect}
            note={note}
            disabled={send.isPending}
          />
          {notice && (
            <p role="alert" className="text-small text-accent">
              {notice}
            </p>
          )}
        </div>
      )}
    </Sheet>
  );
}
