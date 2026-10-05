"use client";

import { useId } from "react";

import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { en } from "@/i18n/en";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { creditsText } from "@/lib/credits";
import { type LedgerReason, usePrices } from "@/lib/queries/wallet";

/**
 * The priced actions in the order the list shows them. `/prices` keys each by
 * the debit reason it is charged under (pricing.service), and says which are
 * active; this says only the order and, through `en.ts`, the words.
 */
const ORDER = [
  "thread_open",
  "thread_reopen",
  "thread_extend",
  "dm_open",
  "dm_message",
  "album_request",
  "voice_unlock",
  "super_like",
  "liked_you_reveal",
] as const satisfies readonly LedgerReason[];

type Priced = (typeof ORDER)[number];

const isPriced = (key: string): key is Priced =>
  (ORDER as readonly string[]).includes(key);

const isReason = (key: string): key is LedgerReason =>
  Object.hasOwn(en.wallet.reason, key);

export type PriceRow = { key: string; label: string; credits: number };

/**
 * What the list shows for these prices: each action `/prices` returns, in
 * `ORDER`, then any it returns that `ORDER` doesn't know, by their history
 * words. A key that isn't a ledger reason has no words at all, so it is left
 * out rather than shown as a code. A switched-off action isn't in `/prices`,
 * so it isn't here either.
 */
export function priceRows(
  prices: Readonly<Record<string, number>>,
): PriceRow[] {
  const known = ORDER.flatMap((key) => {
    const credits = prices[key];
    return credits === undefined
      ? []
      : [{ key, label: t(`wallet.action.${key}`), credits }];
  });
  const others = Object.entries(prices)
    .filter(([key]) => !isPriced(key))
    .sort(([a], [b]) => a.localeCompare(b))
    .flatMap(([key, credits]) =>
      isReason(key)
        ? [
            {
              key,
              label: t(`wallet.reason.${key}`, { app: APP_NAME }),
              credits,
            },
          ]
        : [],
    );
  return [...known, ...others];
}

/** Free for everyone, so `/prices` has no row for them (D-003, D-098). */
const FREE_ROWS = [
  { key: "tie_the_knot", label: "wallet.tieTheKnot" },
  { key: "knot_messages", label: "wallet.knotMessages" },
] as const;

/**
 * "What things cost", for men: `/prices`' actions (D-098, D-231), then tying
 * the knot and messaging in a knot, both free. Not the prototype's Wink, Boost,
 * calls or "Gifts 20–500" (08-DESIGN §5).
 */
export function PriceList() {
  const headingId = useId();
  const prices = usePrices();

  const rows: Array<{
    key: string;
    label: string;
    price: string;
    free: boolean;
  }> = prices.data
    ? [
        ...priceRows(prices.data).map(({ key, label, credits }) => ({
          key,
          label,
          price: credits === 0 ? t("wallet.free") : creditsText(credits),
          free: credits === 0,
        })),
        ...FREE_ROWS.map(({ key, label }) => ({
          key,
          label: t(label),
          price: t("wallet.free"),
          free: true,
        })),
      ]
    : [];

  return (
    <section aria-labelledby={headingId} aria-busy={prices.isPending}>
      <h2 id={headingId} className="text-ui text-ink">
        {t("wallet.prices")}
      </h2>
      {prices.isError ? (
        <ErrorState
          title={t("wallet.pricesFailed")}
          onRetry={() => void prices.refetch()}
        />
      ) : prices.isPending ? (
        <div className="mt-3 flex flex-col gap-4">
          <Skeleton />
          <Skeleton className="w-2/3" />
          <Skeleton />
        </div>
      ) : (
        <ul className="border-line rounded-card divide-line mt-3 divide-y overflow-hidden border">
          {rows.map(({ key, label, price, free }) => (
            <li
              key={key}
              className="bg-surface text-ui flex items-center justify-between gap-4 px-4 py-3"
            >
              <span className="text-ink">{label}</span>
              <span className={free ? "text-mute" : "text-accent"}>
                {price}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
