"use client";

import type {
  InfiniteData,
  UseInfiniteQueryResult,
} from "@tanstack/react-query";
import { useId, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";

type SectionProps = {
  title: string;
  /** A line under the title, saying what the list is. */
  body?: string;
  children: ReactNode;
};

/** One part of the You tab (T-9.8): a titled section, the gifts' shape (T-8.10). */
export function YouSection({ title, body, children }: SectionProps) {
  const heading = useId();
  return (
    <section
      aria-labelledby={heading}
      className="flex flex-col gap-2 px-(--shell-gutter) py-5"
    >
      <h2 id={heading} className="text-title-2 text-ink">
        {title}
      </h2>
      {body && <p className="text-small text-mute">{body}</p>}
      {children}
    </section>
  );
}

type Page<T> = { items: T[]; next_cursor: string | null };

type PagedListProps<T> = {
  query: UseInfiniteQueryResult<InfiniteData<Page<T>>>;
  /** Said when the list loaded and holds nothing. */
  empty: string;
  /** Said when it couldn't load, with a way to try again. */
  failed: string;
  row: (item: T) => ReactNode;
};

/**
 * A paged list inside a section, in each of its states: loading, failed with
 * a retry, empty in a line, or its rows with "Show more" while a page
 * follows (D-270).
 */
export function PagedList<T>({ query, empty, failed, row }: PagedListProps<T>) {
  if (query.isPending) {
    return (
      <div aria-busy className="flex flex-col gap-3 py-2">
        <Skeleton />
        <Skeleton className="w-2/3" />
      </div>
    );
  }
  if (query.isError) {
    return <ErrorState title={failed} onRetry={() => void query.refetch()} />;
  }
  const items = query.data.pages.flatMap((page) => page.items);
  if (items.length === 0) {
    return <p className="text-body text-mute">{empty}</p>;
  }
  return (
    <>
      <ul className="flex flex-col">{items.map(row)}</ul>
      {query.hasNextPage && (
        <Button
          variant="ghost"
          size="sm"
          loading={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          {t("you.more")}
        </Button>
      )}
    </>
  );
}
