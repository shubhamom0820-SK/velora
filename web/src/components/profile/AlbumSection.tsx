"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Loader, Lock } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { creditsText } from "@/lib/credits";
import { useAlbum, useRequestAlbum } from "@/lib/queries/album";
import { queryKeys } from "@/lib/queries/keys";
import { useMe } from "@/lib/queries/me";
import { usePrices } from "@/lib/queries/wallet";

const CARD =
  "bg-surface rounded-card border-line flex flex-col gap-3 border p-4";

/**
 * The album row on someone's profile (T-8.8, 08-DESIGN §8), from `GET
 * /users/{id}/album`'s `status` (D-732): locked, with "Ask to view" and its
 * price; asked and waiting; or shown, his own watermarked copies. A decline or
 * a revoke reads as locked, never named (D-230). A man's price is the
 * `album_request` one from `/prices`, never written here, and is what the
 * request sends (P-56, D-600); a woman's is free and sends 0. Your own shows
 * the count alone, as others see it, and asks nothing.
 */
export function AlbumSection({
  id,
  count,
  own,
}: {
  id: string;
  count: number;
  own: boolean;
}) {
  const toast = useToast();
  const client = useQueryClient();
  const man = useMe().data?.gender === "male";
  const prices = usePrices({ enabled: man && !own });
  const album = useAlbum(id, !own);
  const ask = useRequestAlbum();
  // His from /prices (none while unknown or switched off), hers free (D-098).
  const price = man ? prices.data?.album_request : 0;

  function onAsk(shownPrice: number) {
    ask.mutate(
      { ownerId: id, shownPrice },
      {
        onSuccess: () => toast.show({ message: t("profile.albumSent") }),
        onError: (error) => {
          // Can't afford it: the store sheet opens instead (QueryProvider).
          if (
            error instanceof ApiError &&
            error.code === "INSUFFICIENT_CREDITS"
          ) {
            return;
          }
          if (
            error instanceof ApiError &&
            refusedBecause(error, "empty_album")
          ) {
            // The count was more than there is to see: ask again.
            void client.invalidateQueries({ queryKey: queryKeys.profile(id) });
          }
          toast.show({ message: askRefusal(error), tone: "error" });
        },
      },
    );
  }

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-micro text-mute tracking-wide uppercase">
        {t("profile.album")}
      </h2>
      <div className={CARD} aria-busy={!own && album.isPending}>
        <p className="text-ui text-ink flex items-center gap-2">
          <Icon icon={Lock} size={16} className="text-mute" />
          {count === 1
            ? t("profile.albumOne")
            : t("profile.albumOther", { count })}
        </p>
        {own ? null : album.isPending ? (
          <Skeleton className="h-10" />
        ) : album.isError ? (
          <div className="flex items-center justify-between gap-3">
            <p className="text-small text-mute">
              {t("profile.albumLoadFailed")}
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void album.refetch()}
            >
              {t("ui.retry")}
            </Button>
          </div>
        ) : album.data.status === "pending" ? (
          <p className="text-small text-mute">{t("profile.albumPending")}</p>
        ) : album.data.status === "granted" ? (
          album.data.photos.length === 0 ? (
            <p
              role="status"
              className="text-small text-mute flex items-center gap-2"
            >
              <Icon
                icon={Loader}
                size={16}
                className="motion-safe:animate-spin motion-reduce:animate-pulse"
              />
              {t("profile.albumPreparing")}
            </p>
          ) : (
            <>
              <ul className="grid grid-cols-2 gap-2">
                {album.data.photos.map((photo, index, all) => (
                  <li key={photo.url}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={photo.url}
                      alt={t("profile.albumPhoto", {
                        n: index + 1,
                        total: all.length,
                      })}
                      className="rounded-card aspect-square w-full object-cover"
                    />
                  </li>
                ))}
              </ul>
              <p className="text-small text-mute">{t("profile.albumNote")}</p>
            </>
          )
        ) : (
          price !== undefined && (
            <Button
              variant="ghost"
              onClick={() => onAsk(price)}
              loading={ask.isPending}
              disabled={ask.isPending}
            >
              {t("profile.albumAsk", {
                price: price === 0 ? t("wallet.free") : creditsText(price),
              })}
            </Button>
          )
        )}
      </div>
    </section>
  );
}

function refusedBecause(error: ApiError, why: string): boolean {
  return error.code === "NOT_ALLOWED" && error.details?.why === why;
}

/** Each refusal in words, never its code (T-8.8). */
function askRefusal(error: unknown): string {
  if (!(error instanceof ApiError)) return t("profile.albumFailed");
  if (error.code === "PRICE_CHANGED") {
    // /prices is asked again (QueryProvider); he sees the new price first.
    return t("profile.albumPriceChanged", {
      velas: creditsText(Number(error.details?.price)),
    });
  }
  if (refusedBecause(error, "recently_declined")) {
    return t("profile.albumTooSoon");
  }
  if (refusedBecause(error, "empty_album")) return t("profile.albumEmpty");
  if (error.code === "NOT_FOUND") return t("profile.albumUnavailable");
  return t("profile.albumFailed");
}
