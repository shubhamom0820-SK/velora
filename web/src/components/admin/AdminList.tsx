"use client";

import type {
  InfiniteData,
  UseInfiniteQueryResult,
} from "@tanstack/react-query";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";

type Page<T> = { items: T[]; next_cursor: string | null };

type AdminListProps<T> = {
  query: UseInfiniteQueryResult<InfiniteData<Page<T>>>;
  empty: string;
  keyOf: (item: T) => string;
  children: (item: T) => ReactNode;
};

/**
 * One of the panel's lists, a page at a time (D-270): its loading, empty and
 * error states, and "Load more" rather than loading as it scrolls, since every
 * page staff read is audited (D-920).
 */
export function AdminList<T>({
  query,
  empty,
  keyOf,
  children,
}: AdminListProps<T>) {
  const items = query.data?.pages.flatMap((page) => page.items);

  if (items === undefined) {
    return query.isError ? (
      <ErrorState
        title={t("admin.failed")}
        onRetry={() => void query.refetch()}
      />
    ) : (
      <div aria-busy="true" className="flex flex-col gap-3">
        <Skeleton variant="card" />
        <Skeleton variant="card" />
      </div>
    );
  }
  if (items.length === 0) return <EmptyState title={empty} />;
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-3">
        {items.map((item) => (
          <li key={keyOf(item)}>{children(item)}</li>
        ))}
      </ul>
      {query.isFetchNextPageError && (
        <ErrorState
          title={t("admin.failed")}
          onRetry={() => void query.fetchNextPage()}
        />
      )}
      {query.hasNextPage && !query.isFetchNextPageError && (
        <Button
          variant="ghost"
          size="sm"
          loading={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          {t("admin.loadMore")}
        </Button>
      )}
    </div>
  );
}
