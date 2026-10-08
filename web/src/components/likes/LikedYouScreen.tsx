"use client";

import { Heart } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { creditsText } from "@/lib/credits";
import { useLikes, useLikesCount, useReveal } from "@/lib/queries/likes";
import { useMe } from "@/lib/queries/me";
import { usePrices } from "@/lib/queries/wallet";

import { LikeTile } from "./LikeTile";

/** As the wallet's history: the next page is asked this far before the end. */
const PREFETCH_MARGIN = "200px";

/**
 * Liked you (T-6.7, 08-DESIGN §8): a two-column grid of everyone who liked or
 * Super Liked you and is waiting on your swipe, with their count in the
 * header. A man reveals each for the `liked_you_reveal` price, read from
 * `/prices`, never written here; a woman's are all revealed (D-002), and she
 * is never asked for prices. Can't afford it: the store sheet opens.
 */
export function LikedYouScreen() {
  const toast = useToast();
  const man = useMe().data?.gender === "male";
  const likes = useLikes();
  const count = useLikesCount();
  const prices = usePrices({ enabled: man });
  const reveal = useReveal();
  const [revealing, setRevealing] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const {
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    fetchNextPage,
  } = likes;

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

  const all = likes.data?.pages.flatMap((page) => page.items);
  const price = man ? prices.data?.liked_you_reveal : undefined;

  function onReveal(handle: string) {
    setRevealing(handle);
    // The price this screen showed: his from /prices, hers 0 (D-002).
    reveal.mutate(
      { handle, shownPrice: price ?? 0 },
      {
        onError: (error) => {
          // Can't afford it: the store sheet opens instead (QueryProvider).
          if (
            error instanceof ApiError &&
            error.code === "INSUFFICIENT_CREDITS"
          ) {
            return;
          }
          // The price moved: /prices is asked again (QueryProvider), and he
          // is told the new one before trying again.
          const message =
            error instanceof ApiError && error.code === "PRICE_CHANGED"
              ? t("likes.priceChanged", {
                  velas: creditsText(Number(error.details?.price)),
                })
              : t("likes.revealFailed");
          toast.show({ message, tone: "error" });
        },
        onSettled: () => setRevealing(null),
      },
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="bg-chrome flex items-center gap-2 px-(--shell-gutter) py-3">
        <h1 className="text-title-2 text-chrome-ink">{t("likes.title")}</h1>
        {count.data !== undefined && count.data.count > 0 && (
          <Badge
            tone="count"
            label={t("likes.count", { count: count.data.count })}
          >
            {count.data.count}
          </Badge>
        )}
      </div>
      <section
        aria-label={t("likes.title")}
        aria-busy={likes.isPending}
        className="p-(--shell-gutter)"
      >
        {all === undefined ? (
          likes.isError ? (
            <ErrorState
              title={t("likes.failed")}
              onRetry={() => void likes.refetch()}
            />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <Skeleton className="rounded-card h-[204px]" />
              <Skeleton className="rounded-card h-[204px]" />
            </div>
          )
        ) : all.length === 0 ? (
          <EmptyState
            icon={Heart}
            title={t("likes.empty")}
            body={t("likes.emptyBody")}
          />
        ) : (
          <>
            <ul className="grid grid-cols-2 gap-3">
              {all.map((like) => (
                <li key={like.handle}>
                  <LikeTile
                    like={like}
                    price={price}
                    revealing={revealing === like.handle}
                    onReveal={() => onReveal(like.handle)}
                  />
                </li>
              ))}
            </ul>
            <div ref={end} />
            {isFetchingNextPage && (
              <div className="text-mute flex justify-center py-4">
                <Spinner label={t("likes.loadingMore")} />
              </div>
            )}
            {isFetchNextPageError && (
              <ErrorState
                title={t("likes.failed")}
                onRetry={() => void fetchNextPage()}
              />
            )}
          </>
        )}
      </section>
    </div>
  );
}
