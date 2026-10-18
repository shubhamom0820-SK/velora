"use client";

import { Sparkles, Zap } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { creditsCount, creditsText } from "@/lib/credits";
import type { Pack } from "@/lib/queries/store";
import { bestValue, perThread, perVela, rupees } from "@/lib/store-math";

type PackListProps = {
  packs: readonly Pack[];
  /** `/prices`' `thread_open`; without it a row says its per-Vela rate alone. */
  threadPrice: number | undefined;
  /** While an order is being made: no second tap. */
  disabled: boolean;
  onBuy: (pack: Pack) => void;
};

/**
 * The store's packs (T-8.7), from the prototype's store sheet with D-099's
 * packs (08-DESIGN §5), built from existing parts only: each a row you tap to
 * pay, its Velas, its rate per Vela and per Thread, its price. "Best value"
 * on the cheapest Vela, worked out (D-760); no "Most popular" (P-660). The
 * first-purchase banner shows while any pack carries a bonus, each pack's
 * bonus its own row's number, never a percentage written here.
 */
export function PackList({
  packs,
  threadPrice,
  disabled,
  onBuy,
}: PackListProps) {
  const best = bestValue(packs);
  const firstPurchase = packs.some((pack) => pack.bonus_credits > 0);

  return (
    <div className="flex flex-col gap-3">
      {firstPurchase && (
        <p className="border-accent bg-accent-soft text-small text-accent-text rounded-card flex items-center gap-2 border px-4 py-2.5 font-semibold">
          <Icon icon={Sparkles} size={16} />
          {t("wallet.store.firstPurchase")}
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {packs.map((pack) => (
          <li key={pack.id}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onBuy(pack)}
              className="border-line bg-surface rounded-card focus-visible:outline-accent flex w-full items-center gap-3 border px-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-60"
            >
              <span className="bg-accent text-on-accent rounded-pill flex size-8 shrink-0 items-center justify-center">
                <Icon icon={Zap} size={16} className="fill-current" />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="text-ui text-ink flex flex-wrap items-center gap-x-2 font-semibold">
                  {creditsText(pack.credits)}
                  {pack.bonus_credits > 0 && (
                    <span className="text-small text-accent">
                      {t("wallet.store.bonus", {
                        count: creditsCount(pack.bonus_credits),
                      })}
                    </span>
                  )}
                  {pack.id === best && (
                    <Badge tone="soft">{t("wallet.store.bestValue")}</Badge>
                  )}
                </span>
                <span className="text-small text-mute">
                  {threadPrice === undefined
                    ? t("wallet.store.rateVelaOnly", { perVela: perVela(pack) })
                    : t("wallet.store.rate", {
                        perVela: perVela(pack),
                        perThread: perThread(pack, threadPrice),
                      })}
                </span>
              </span>
              <span className="text-ui text-ink shrink-0 font-bold">
                {rupees(pack.price_paise)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
