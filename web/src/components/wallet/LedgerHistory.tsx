"use client";

import { Receipt } from "lucide-react";
import { useEffect, useId, useRef } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { deltaText } from "@/lib/credits";
import { useLedger } from "@/lib/queries/wallet";

/** When an entry happened, in the reader's own time zone: "5 Oct 2026, 2:42 pm". */
export const entryTime = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "short",
});

/**
 * Asks for the next page this far before the end of the list comes into
 * view, so scrolling rarely meets the spinner.
 */
const PREFETCH_MARGIN = "200px";

/**
 * A man's history, newest first, with each reason in words from `en.ts`
 * (D-033). The next page loads as the end of the list scrolls into view; one
 * that fails says so and waits for "Try again", rather than asking again by
 * itself.
 */
export function LedgerHistory() {
  const headingId = useId();
  const ledger = useLedger();
  const end = useRef<HTMLDivElement>(null);
  const {
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    fetchNextPage,
  } = ledger;

  useEffect(() => {
    const node = end.current;
    if (!node || !hasNextPage || isFetchingNextPage || isFetchNextPageError) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void fetchNextPage();
        }
      },
      { rootMargin: PREFETCH_MARGIN },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage]);

  const entries = ledger.data?.pages.flatMap((page) => page.items);

  return (
    <section aria-labelledby={headingId} aria-busy={ledger.isPending}>
      <h2 id={headingId} className="text-ui text-ink flex items-center gap-2">
        <Icon icon={Receipt} size={16} className="text-accent" />
        {t("wallet.history")}
      </h2>
      {entries === undefined ? (
        ledger.isError ? (
          <ErrorState
            title={t("wallet.historyFailed")}
            onRetry={() => void ledger.refetch()}
          />
        ) : (
          <div className="mt-3 flex flex-col gap-4">
            <Skeleton />
            <Skeleton className="w-2/3" />
            <Skeleton />
          </div>
        )
      ) : entries.length === 0 ? (
        <EmptyState
          icon={Receipt}
          title={t("wallet.historyEmpty")}
          body={t("wallet.historyEmptyBody")}
        />
      ) : (
        <>
          <ul className="border-line rounded-card divide-line mt-3 divide-y overflow-hidden border">
            {entries.map((entry) => (
              <li
                key={entry.id}
                className="bg-surface flex items-center justify-between gap-4 px-4 py-3"
              >
                <span className="flex flex-col">
                  <span className="text-ui text-ink">
                    {t(`wallet.reason.${entry.reason}`, { app: APP_NAME })}
                  </span>
                  <time
                    dateTime={entry.created_at}
                    className="text-micro text-mute"
                  >
                    {entryTime.format(new Date(entry.created_at))}
                  </time>
                </span>
                <span
                  className={
                    entry.delta < 0 ? "text-ui text-accent" : "text-ui text-ink"
                  }
                >
                  {deltaText(entry.delta)}
                </span>
              </li>
            ))}
          </ul>
          <div ref={end} />
          {isFetchingNextPage && (
            <div className="text-mute mt-4 flex justify-center">
              <Spinner label={t("wallet.loadingMore")} />
            </div>
          )}
          {isFetchNextPageError && (
            <ErrorState
              title={t("wallet.historyFailed")}
              onRetry={() => void fetchNextPage()}
            />
          )}
        </>
      )}
    </section>
  );
}
