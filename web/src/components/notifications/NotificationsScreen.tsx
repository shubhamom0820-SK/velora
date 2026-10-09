"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";

import { entryTime } from "@/components/wallet/LedgerHistory";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import { routeFor, sentenceFor } from "@/lib/notification-view";
import {
  useMarkNotificationsRead,
  useNotifications,
} from "@/lib/queries/notifications";

/** As the wallet's history: the next page is asked this far before the end. */
const PREFETCH_MARGIN = "200px";

/**
 * The in-app list (T-9.4), at `/notifications`, newest first: each row the
 * kind's sentence and its time, leading where the push would. Built from the
 * existing parts (D-859); no bell in the header until a design (P-750).
 * Opening it marks everything read, once the first page has come.
 */
export function NotificationsScreen() {
  const list = useNotifications();
  const markRead = useMarkNotificationsRead();
  const end = useRef<HTMLDivElement>(null);
  const marked = useRef(false);
  const {
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    fetchNextPage,
  } = list;
  const all = list.data?.pages.flatMap((page) => page.items);
  const anyUnread = all?.some((item) => item.read_at === null) ?? false;
  const { mutate } = markRead;

  useEffect(() => {
    if (anyUnread && !marked.current) {
      marked.current = true;
      mutate();
    }
  }, [anyUnread, mutate]);

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

  return (
    <div className="flex flex-1 flex-col">
      <div className="bg-chrome px-(--shell-gutter) py-3">
        <h1 className="text-title-2 text-chrome-ink">
          {t("notifications.title")}
        </h1>
      </div>
      <section
        aria-label={t("notifications.title")}
        aria-busy={list.isPending}
        className="p-(--shell-gutter)"
      >
        {all === undefined ? (
          list.isError ? (
            <ErrorState
              title={t("notifications.failed")}
              onRetry={() => void list.refetch()}
            />
          ) : (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-14" />
              <Skeleton className="h-14" />
              <Skeleton className="h-14" />
            </div>
          )
        ) : all.length === 0 ? (
          <EmptyState
            icon={Bell}
            title={t("notifications.empty")}
            body={t("notifications.emptyBody")}
          />
        ) : (
          <>
            <ul className="divide-line flex flex-col divide-y">
              {all.map((item) => (
                <li key={item.id}>
                  <Link
                    href={routeFor(item.kind, item.data)}
                    className="focus-visible:outline-accent flex items-start gap-3 py-3 focus-visible:outline-2"
                  >
                    <span
                      aria-hidden
                      className={cx(
                        "rounded-pill mt-2 size-2 shrink-0",
                        item.read_at === null ? "bg-accent" : "bg-transparent",
                      )}
                    />
                    <span className="flex flex-col">
                      <span className="text-body text-ink">
                        {item.read_at === null && (
                          <span className="sr-only">
                            {t("notifications.unread")}:{" "}
                          </span>
                        )}
                        {sentenceFor(item.kind, item.data)}
                      </span>
                      <time
                        dateTime={item.created_at}
                        className="text-small text-mute"
                      >
                        {entryTime.format(new Date(item.created_at))}
                      </time>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <div ref={end} />
            {isFetchingNextPage && (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
