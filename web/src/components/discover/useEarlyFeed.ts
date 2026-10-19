"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { discoverQuery, HOME_FEED } from "@/lib/queries/discover";
import { useSession } from "@/store/session";

import { filtersOf } from "./filterParams";

/**
 * The deck's first page, asked for as soon as there is an access token
 * (T-9.10, D-1033), while the app's gate is still waiting for `/me`: the feed
 * waited for `/me` before, two round trips each with its CORS preflight (by
 * the presets' latency, about 1.1 s at Slow 4G and 0.33 s at Fast 4G). The
 * page lands in the cache under the deck's own key, so the deck reads it
 * rather than asking again, and a request already on its way is shared, never
 * sent twice.
 *
 * Only on `/discover`, the screen it is for. Nothing here shows anything: the
 * gate still decides what renders, and the server still decides who may see a
 * feed. An unfinished onboarding is refused (`ONBOARDING_INCOMPLETE`) and goes
 * to its step as before; a frozen or banned account is refused as its `/me`
 * is, and signed out as before (D-067).
 */
export function useEarlyFeed(onDiscover: boolean) {
  const client = useQueryClient();
  const signedIn = useSession((state) => state.status === "signed-in");
  useEffect(() => {
    if (!onDiscover || !signedIn) return;
    // The deck reads its filters from the address; on the first load this is
    // the same address, so the same key.
    const filters = filtersOf(new URLSearchParams(window.location.search));
    void client.prefetchInfiniteQuery(discoverQuery(HOME_FEED, filters));
  }, [client, onDiscover, signedIn]);
}
