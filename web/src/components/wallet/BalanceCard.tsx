"use client";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { creditsCount, creditsUnit } from "@/lib/credits";
import { useWallet } from "@/lib/queries/wallet";
import { useStoreSheet } from "@/store/store-sheet";

/**
 * A man's balance on the black card (✦), from the one wallet query the header's
 * pill reads too, and "Buy Velas" below it, which opens the store sheet.
 */
export function BalanceCard() {
  const wallet = useWallet();
  const showStore = useStoreSheet((state) => state.show);
  const balance = wallet.data?.balance;

  return (
    <section aria-busy={wallet.isPending} className="flex flex-col gap-4">
      {wallet.isError ? (
        <ErrorState
          title={t("wallet.balanceFailed")}
          onRetry={() => void wallet.refetch()}
        />
      ) : (
        <div className="bg-chrome rounded-card px-5 py-5">
          <h2 className="text-small text-chrome-mute">{t("wallet.balance")}</h2>
          {balance === undefined ? (
            <Skeleton className="mt-4 mb-3 w-24" />
          ) : (
            <p className="mt-1 flex items-baseline gap-2">
              <span className="text-display text-chrome-accent">
                {creditsCount(balance)}
              </span>
              <span className="text-ui text-chrome-mute">
                {creditsUnit(balance)}
              </span>
            </p>
          )}
        </div>
      )}
      <Button fullWidth onClick={showStore}>
        {t("wallet.buy")}
      </Button>
    </section>
  );
}
