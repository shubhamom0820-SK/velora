"use client";

import { Search, SearchX } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { t } from "@/i18n/t";
import { useSearch } from "@/lib/queries/search";

import { SearchResultRow } from "./SearchResultRow";
import {
  SEARCH_MAX,
  SEARCH_TEXT_MIN,
  type SearchQuery,
  searchQueryOf,
} from "./searchQuery";
import { useDebounced } from "./useDebounced";

/** How long typing must pause before the search is asked. */
export const SEARCH_DEBOUNCE_MS = 300;

/** As the wallet's history: the next page is asked this far before the end. */
const PREFETCH_MARGIN = "200px";

function askable(query: SearchQuery): string | null {
  return query.kind === "username" || query.kind === "text" ? query.q : null;
}

/**
 * Search (T-6.6, 08-DESIGN §8). The field sits on a chrome bar at the top of
 * the screen, under the shell's header, whose shape is AppShell's alone
 * (D-540). It asks once typing pauses, and only what the API would answer:
 * otherwise it says why. In @ mode an "@ username" badge marks the results.
 */
export function SearchScreen() {
  const fieldId = useId();
  const hintId = useId();
  const [raw, setRaw] = useState("");
  const query = searchQueryOf(useDebounced(raw, SEARCH_DEBOUNCE_MS));
  const q = askable(query);
  const search = useSearch(q);
  const end = useRef<HTMLDivElement>(null);
  const {
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    fetchNextPage,
  } = search;

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

  const people =
    q === null ? undefined : search.data?.pages.flatMap((p) => p.items);
  const hint =
    query.kind === "tooShort"
      ? t("search.tooShort", { min: SEARCH_TEXT_MIN })
      : query.kind === "badUsername"
        ? t("search.badUsername")
        : query.kind === "empty"
          ? t("search.hint")
          : null;

  return (
    <div className="flex flex-1 flex-col">
      <h1 className="sr-only">{t("search.title")}</h1>
      <div className="bg-chrome px-(--shell-gutter) py-3">
        <div className="bg-chrome-line rounded-input focus-within:outline-chrome-accent flex items-center gap-2 px-3 focus-within:outline-2">
          <Icon icon={Search} size={18} className="text-chrome-mute" />
          <label htmlFor={fieldId} className="sr-only">
            {t("search.label")}
          </label>
          <input
            id={fieldId}
            type="search"
            value={raw}
            onChange={(event) => setRaw(event.target.value)}
            maxLength={SEARCH_MAX}
            placeholder={t("search.placeholder")}
            aria-describedby={hint ? hintId : undefined}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            className="text-input text-chrome-ink placeholder:text-chrome-mute min-w-0 flex-1 bg-transparent py-2.5 outline-none"
          />
        </div>
      </div>
      {hint !== null && (
        <p
          id={hintId}
          className="text-small text-mute px-(--shell-gutter) py-4"
        >
          {hint}
        </p>
      )}
      {q !== null && (
        <section
          aria-label={t("search.resultsFor", { q })}
          aria-busy={search.isPending}
        >
          {query.kind === "username" && (
            <div className="px-(--shell-gutter) pt-4">
              <Badge>{t("search.usernameMode")}</Badge>
            </div>
          )}
          {people === undefined ? (
            search.isError ? (
              <ErrorState
                title={t("search.failed")}
                onRetry={() => void search.refetch()}
              />
            ) : (
              <div className="flex flex-col gap-4 px-(--shell-gutter) py-4">
                <Skeleton />
                <Skeleton className="w-2/3" />
                <Skeleton />
              </div>
            )
          ) : people.length === 0 ? (
            <EmptyState
              icon={SearchX}
              title={t("search.empty")}
              body={t("search.emptyBody")}
            />
          ) : (
            <>
              <ul className="divide-line divide-y">
                {people.map((person) => (
                  <li key={person.id}>
                    <SearchResultRow person={person} />
                  </li>
                ))}
              </ul>
              <div ref={end} />
              {isFetchingNextPage && (
                <div className="text-mute flex justify-center py-4">
                  <Spinner label={t("search.loadingMore")} />
                </div>
              )}
              {isFetchNextPageError && (
                <ErrorState
                  title={t("search.failed")}
                  onRetry={() => void fetchNextPage()}
                />
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}
