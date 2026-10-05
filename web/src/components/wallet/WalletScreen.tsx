"use client";

import Link from "next/link";

import { t } from "@/i18n/t";
import { useMe } from "@/lib/queries/me";

import { BalanceCard } from "./BalanceCard";
import { FreeForYou } from "./FreeForYou";
import { LedgerHistory } from "./LedgerHistory";
import { PriceList } from "./PriceList";

/**
 * The Wallet place (T-5.5), inside the app shell. A man's: his balance, what
 * things cost and his history, then a quiet link to the refund policy; no
 * refund request, since purchases are final (D-050, D-230). A woman's says
 * everything is free, and asks the API for none of it.
 */
export function WalletScreen() {
  const gender = useMe().data?.gender;

  return (
    <div className="mx-auto flex w-full max-w-130 flex-col gap-8 px-5 py-6">
      <h1 className="sr-only">{t("wallet.title")}</h1>
      {gender === "male" && (
        <>
          <BalanceCard />
          <PriceList />
          <LedgerHistory />
          <Link
            href="/refunds"
            className="text-small text-mute self-center underline underline-offset-2"
          >
            {t("wallet.refunds")}
          </Link>
        </>
      )}
      {gender === "female" && <FreeForYou />}
    </div>
  );
}
