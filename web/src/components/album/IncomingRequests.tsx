"use client";

import { Lock } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import {
  type AlbumRequest,
  useDecideAlbumRequest,
  useIncomingAlbumRequests,
  useRevokeAlbumRequest,
} from "@/lib/queries/album";

import { AlbumRequestRow } from "./AlbumRequestRow";

/** How far below the screen the next page is asked for. */
const PREFETCH_MARGIN = "200px";

type Busy = { id: string; what: "grant" | "decline" | "revoke" };

/**
 * The requests to see your private album (T-8.8, D-732), at
 * `/you/album-requests`: pending ones to grant or decline, granted ones to stop
 * sharing, newest first, a page at a time. Stopping asks first: it deletes
 * their copies (D-730). A request someone else's answer or a block took away
 * meanwhile says so, and the list is asked again.
 */
export function IncomingRequests() {
  const toast = useToast();
  const requests = useIncomingAlbumRequests();
  const decide = useDecideAlbumRequest();
  const revoke = useRevokeAlbumRequest();
  const [busy, setBusy] = useState<Busy | null>(null);
  const [stopping, setStopping] = useState<AlbumRequest | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const {
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    fetchNextPage,
  } = requests;

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

  function refused(error: unknown) {
    const message =
      error instanceof ApiError && error.code === "NOT_ALLOWED"
        ? t("albumRequests.alreadyAnswered")
        : error instanceof ApiError && error.code === "NOT_FOUND"
          ? t("albumRequests.gone")
          : t("albumRequests.failed");
    toast.show({ message, tone: "error" });
  }

  function onDecide(id: string, grant: boolean) {
    setBusy({ id, what: grant ? "grant" : "decline" });
    decide.mutate(
      { id, grant },
      {
        onSuccess: () =>
          toast.show({
            message: grant
              ? t("albumRequests.granted")
              : t("albumRequests.declined"),
          }),
        onError: refused,
        onSettled: () => setBusy(null),
      },
    );
  }

  function onRevoke(request: AlbumRequest) {
    setStopping(null);
    setBusy({ id: request.id, what: "revoke" });
    revoke.mutate(request.id, {
      onSuccess: () => toast.show({ message: t("albumRequests.revoked") }),
      onError: refused,
      onSettled: () => setBusy(null),
    });
  }

  const all = requests.data?.pages.flatMap((page) => page.items);
  const stoppingName = stopping?.requester.deleted
    ? t("albumRequests.deleted")
    : (stopping?.requester.first_name ?? t("albumRequests.deleted"));

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex flex-col gap-1 px-(--shell-gutter) pt-5">
        <h1 className="text-title-1 text-ink">{t("albumRequests.title")}</h1>
        <p className="text-small text-mute">{t("albumRequests.intro")}</p>
      </header>
      <section
        aria-label={t("albumRequests.title")}
        aria-busy={requests.isPending}
        className="px-(--shell-gutter) pb-5"
      >
        {all === undefined ? (
          requests.isError ? (
            <ErrorState
              title={t("albumRequests.loadFailed")}
              onRetry={() => void requests.refetch()}
            />
          ) : (
            <div className="flex flex-col gap-3 pt-4">
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
            </div>
          )
        ) : all.length === 0 ? (
          <EmptyState
            icon={Lock}
            title={t("albumRequests.empty")}
            body={t("albumRequests.emptyBody")}
          />
        ) : (
          <>
            <ul>
              {all.map((request) => (
                <li key={request.id}>
                  <AlbumRequestRow
                    request={request}
                    busy={busy?.id === request.id ? busy.what : null}
                    onDecide={(grant) => onDecide(request.id, grant)}
                    onRevoke={() => setStopping(request)}
                  />
                </li>
              ))}
            </ul>
            <div ref={end} />
            {isFetchingNextPage && (
              <div className="text-mute flex justify-center py-4">
                <Spinner label={t("albumRequests.loadingMore")} />
              </div>
            )}
            {isFetchNextPageError && (
              <ErrorState
                title={t("albumRequests.loadFailed")}
                onRetry={() => void fetchNextPage()}
              />
            )}
          </>
        )}
      </section>
      <Sheet
        open={stopping !== null}
        onClose={() => setStopping(null)}
        title={t("albumRequests.revokeTitle", { name: stoppingName })}
        footer={
          <div className="flex gap-2">
            <Button
              variant="ghost"
              className="flex-1"
              onClick={() => setStopping(null)}
            >
              {t("albumRequests.cancel")}
            </Button>
            <Button
              variant="danger"
              className="flex-1"
              onClick={() => stopping && onRevoke(stopping)}
            >
              {t("albumRequests.revoke")}
            </Button>
          </div>
        }
      >
        <p className="text-body text-ink">{t("albumRequests.revokeBody")}</p>
      </Sheet>
    </div>
  );
}
