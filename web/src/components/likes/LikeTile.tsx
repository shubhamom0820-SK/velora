"use client";

import { Lock, Star, User } from "lucide-react";
import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { t } from "@/i18n/t";
import { creditsText } from "@/lib/credits";
import type { LikeCard } from "@/lib/queries/likes";

type LikeTileProps = {
  like: LikeCard;
  /** What a reveal costs this man, from `/prices`; undefined while unknown,
   * or when the reveal is switched off, and then no pill is shown. */
  price: number | undefined;
  revealing: boolean;
  onReveal: () => void;
};

/**
 * One tile of Liked you (08-DESIGN §8): 204 px, `--corner-card`. Revealed,
 * the photo, the thread, the name and distance, and a star for a Super Like.
 * Unrevealed, the server's blur, an `<img>` of a picture it made, never a CSS
 * filter over the real one (D-543), and the "Reveal" pill with its price.
 */
export function LikeTile({ like, price, revealing, onReveal }: LikeTileProps) {
  const card = like.card;
  return (
    <div className="rounded-card bg-surface-2 relative flex h-[204px] flex-col overflow-hidden">
      {like.is_super && (
        <span className="bg-ink text-chrome-ink rounded-pill absolute top-2 left-2 z-10 flex size-7 items-center justify-center">
          <Icon
            icon={Star}
            size={14}
            label={t("likes.superLike")}
            className="fill-current"
          />
        </span>
      )}
      {card ? (
        <Link href={`/people/${card.id}`} className="flex flex-1 flex-col">
          <div className="relative flex-1">
            {card.main_photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={card.main_photo_url}
                alt=""
                className="size-full object-cover"
              />
            ) : (
              <span className="text-line-strong flex size-full items-center justify-center">
                <Icon icon={User} size={48} />
              </span>
            )}
          </div>
          <span aria-hidden className="bg-accent h-0.5" />
          <span className="bg-surface flex flex-col px-3 py-2">
            <span className="text-ui text-ink truncate">
              {card.age === null
                ? card.first_name
                : t("likes.nameAge", { name: card.first_name, age: card.age })}
            </span>
            {card.distance_km !== null && (
              <span className="text-micro text-mute">
                {t("likes.distance", { km: card.distance_km })}
              </span>
            )}
          </span>
        </Link>
      ) : (
        <>
          {like.blurred_photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={like.blurred_photo_url}
              alt={t("likes.someone")}
              className="size-full object-cover"
            />
          ) : (
            <span
              role="img"
              aria-label={t("likes.someone")}
              className="text-line-strong flex size-full items-center justify-center"
            >
              <Icon icon={User} size={48} />
            </span>
          )}
          {price !== undefined && (
            <button
              type="button"
              onClick={onReveal}
              disabled={revealing}
              className="bg-surface text-ink text-ui rounded-pill shadow-2 absolute inset-x-3 bottom-3 flex items-center justify-center gap-1.5 py-2 disabled:opacity-60"
            >
              {revealing ? (
                <Spinner label={t("likes.revealing")} />
              ) : (
                <Icon icon={Lock} size={14} />
              )}
              {t("likes.reveal", { price: creditsText(price) })}
            </button>
          )}
        </>
      )}
    </div>
  );
}
