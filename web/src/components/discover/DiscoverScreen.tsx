"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { creditsText } from "@/lib/credits";
import {
  HOME_FEED,
  useDiscover,
  useSuperLike,
  useSwipe,
  type Card,
  type DiscoverFilters,
  type Feed,
  type SwipeDirection,
} from "@/lib/queries/discover";
import { useMe } from "@/lib/queries/me";
import { usePrices } from "@/lib/queries/wallet";

import { ActionRow } from "./ActionRow";
import { Deck, type DeckHandle } from "./Deck";
import { DiscoverEmpty } from "./DiscoverEmpty";
import { FeedRow } from "./FeedRow";
import { activeCount, filtersOf, hrefOf, NO_FILTERS } from "./filterParams";
import { FiltersSheet } from "./FiltersSheet";
import { MatchSheet, type Match } from "./MatchSheet";
import { profileHref } from "./SwipeCard";

/** At this many cards left, the next page is asked for (T-6.5). */
export const PREFETCH_AT = 5;

/** The answers that mean the card is gone anyway: never put it back. */
const GONE_ANYWAY: ReadonlySet<string> = new Set([
  "ALREADY_EXISTS",
  "NOT_FOUND",
]);

/** Whether a key press belongs to something being typed in, not the deck. */
function typing(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}

const KEYS: Readonly<Record<string, SwipeDirection>> = {
  ArrowLeft: "pass",
  ArrowRight: "like",
  ArrowUp: "super",
};

/**
 * Discover (T-6.5): the feed row, the deck, the action row, and the match
 * sheet. A swipe takes the card off at once and is sent; if the API refuses
 * it, the card comes back with a toast, except when it is gone anyway (swiped
 * already, or no longer someone the feed could show). A man's Super Like sends
 * the price its button showed (P-56); a woman's sends 0 and shows none.
 */
export function DiscoverScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const filters = useMemo(
    () => filtersOf(new URLSearchParams(params.toString())),
    [params],
  );
  const filterCount = activeCount(filters);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [feed, setFeed] = useState<Feed>(HOME_FEED);

  const me = useMe().data;
  const isMan = me?.gender === "male";
  const prices = usePrices();
  const priceOf = (action: string): number | null | undefined => {
    if (!isMan) return null;
    return prices.data?.[action];
  };
  const superAvailable = !prices.isSuccess || "super_like" in prices.data;

  const discover = useDiscover(feed, filters);
  const swipe = useSwipe();
  const superLike = useSuperLike();
  const toast = useToast();

  const [gone, setGone] = useState<ReadonlySet<string>>(new Set());
  const cards = useMemo(() => {
    const seen = new Set<string>();
    const all: Card[] = [];
    for (const page of discover.data?.pages ?? []) {
      for (const card of page.items) {
        if (seen.has(card.id)) continue;
        seen.add(card.id);
        all.push(card);
      }
    }
    return all.filter((card) => !gone.has(card.id));
  }, [discover.data, gone]);

  // A man's swipes left: the latest page's count, or a swipe's answer after it.
  const pages = discover.data?.pages.length ?? 0;
  const [answered, setAnswered] = useState<{
    left: number;
    pages: number;
  } | null>(null);
  const fromPage = discover.data?.pages.at(-1)?.swipes_left ?? null;
  const swipesLeft = !isMan
    ? null
    : answered && answered.pages === pages
      ? answered.left
      : fromPage;

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = discover;
  useEffect(() => {
    if (cards.length <= PREFETCH_AT && hasNextPage && !isFetchingNextPage) {
      void fetchNextPage();
    }
  }, [cards.length, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const [match, setMatch] = useState<Match | null>(null);
  const deck = useRef<DeckHandle>(null);
  // What the last swipe did, for a screen reader (T-9.11): the card leaving
  // says nothing by itself.
  const [swiped, setSwiped] = useState("");

  const putBack = useCallback((id: string) => {
    setGone((now) => {
      const next = new Set(now);
      next.delete(id);
      return next;
    });
  }, []);

  const send = useCallback(
    async (card: Card, dir: SwipeDirection, shownPrice: number) => {
      const mutation = dir === "super" ? superLike : swipe;
      try {
        const result = await mutation.mutateAsync({
          target_id: card.id,
          dir,
          shown_price: shownPrice,
        });
        if (result.swipes_left !== null) {
          setAnswered({ left: result.swipes_left, pages });
        }
        if (result.matched && result.match_id) {
          setMatch({ matchId: result.match_id, theirName: card.first_name });
        }
      } catch (error) {
        if (error instanceof ApiError && GONE_ANYWAY.has(error.code)) return;
        putBack(card.id);
        if (!(error instanceof ApiError)) {
          toast.show({ message: t("discover.errors.failed"), tone: "error" });
        } else if (error.code === "SWIPE_LIMIT_REACHED") {
          setAnswered({ left: 0, pages });
          toast.show({ message: t("discover.errors.limit"), tone: "error" });
        } else if (error.code === "PRICE_CHANGED") {
          toast.show({
            message: t("discover.errors.priceChanged", {
              velas: creditsText(Number(error.details?.price)),
            }),
            tone: "error",
          });
        } else if (error.code !== "INSUFFICIENT_CREDITS") {
          // Out of Velas opens the store sheet instead (QueryProvider).
          toast.show({ message: t("discover.errors.failed"), tone: "error" });
        }
      }
    },
    [superLike, swipe, pages, putBack, toast],
  );

  const superPrice = priceOf("super_like");

  const onSwipe = useCallback(
    (card: Card, dir: SwipeDirection): boolean => {
      if (dir === "super" && (!superAvailable || superPrice === undefined)) {
        return false;
      }
      if (isMan && dir !== "super" && swipesLeft === 0) {
        toast.show({ message: t("discover.errors.limit"), tone: "error" });
        return false;
      }
      setGone((now) => new Set(now).add(card.id));
      setSwiped(t(`discover.swiped.${dir}`, { name: card.first_name }));
      void send(card, dir, dir === "super" ? (superPrice ?? 0) : 0);
      return true;
    },
    [superAvailable, superPrice, isMan, swipesLeft, toast, send],
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const dir = KEYS[event.key];
      if (!dir || event.defaultPrevented) return;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
        return;
      }
      if (typing(event.target)) return;
      // A sheet open, or the PIN lock up: the deck isn't what's in front.
      if (document.querySelector('[role="dialog"]')) return;
      event.preventDefault();
      deck.current?.swipe(dir);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  /** The one way the deck's filters change: into the URL (filterParams). */
  function applyFilters(next: DiscoverFilters) {
    router.replace(hrefOf(pathname, next));
  }

  let body;
  if (discover.isPending || (cards.length === 0 && isFetchingNextPage)) {
    body = (
      <div aria-busy className="h-[min(35rem,calc(100dvh-17rem))] min-h-96">
        <Skeleton variant="card" className="rounded-swipe size-full" />
      </div>
    );
  } else if (discover.isError && cards.length === 0) {
    body = (
      <ErrorState
        title={t("discover.failed")}
        onRetry={() => void discover.refetch()}
      />
    );
  } else if (cards.length === 0) {
    body =
      filterCount > 0 ? (
        <DiscoverEmpty
          kind="filters"
          onClear={() => applyFilters(NO_FILTERS)}
        />
      ) : (
        <DiscoverEmpty
          kind="nobody"
          onCheckAgain={() => void discover.refetch()}
        />
      );
  } else {
    body = (
      <Deck
        ref={deck}
        cards={cards}
        onSwipe={onSwipe}
        onOpen={(card) => router.push(profileHref(card.id))}
      />
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-130 flex-col gap-4 px-5 py-4">
      <h1 className="sr-only">{t("discover.title")}</h1>
      <FeedRow
        feed={feed}
        onFeed={setFeed}
        filterCount={filterCount}
        onFilters={() => setFiltersOpen(true)}
      />
      {body}
      <ActionRow
        onSwipe={(dir) => void deck.current?.swipe(dir)}
        disabled={cards.length === 0}
        superPrice={superPrice}
        superAvailable={superAvailable}
        swipesLeft={swipesLeft}
        name={cards[0]?.first_name ?? null}
      />
      <p role="status" className="sr-only">
        {swiped}
      </p>
      <MatchSheet
        match={match}
        myName={me?.profile.first_name ?? ""}
        openPrice={priceOf("thread_open")}
        onClose={() => setMatch(null)}
      />
      {filtersOpen && (
        <FiltersSheet
          applied={filters}
          onClose={() => setFiltersOpen(false)}
          onApply={(next) => {
            setFiltersOpen(false);
            applyFilters(next);
          }}
        />
      )}
    </div>
  );
}
