"use client";

import { Gift, Heart } from "lucide-react";
import { useState } from "react";

import { GiftSheet } from "@/components/gifts/GiftSheet";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { useLike } from "@/lib/queries/profiles";

/**
 * The sticky bar at the profile's foot (08-DESIGN §8): Like. "Open thread"
 * joins it with the chats' screens (P-440). A like already given, here or in
 * the deck, reads as given; one the API refuses says why. Gift, with its
 * sheet (T-8.10), only where the API says a gift is taken (`can_gift`, D-780):
 * a man on a woman's profile.
 */
export function ProfileActions({
  id,
  firstName,
  canGift,
}: {
  id: string;
  firstName: string;
  canGift: boolean;
}) {
  const toast = useToast();
  const like = useLike();
  const [liked, setLiked] = useState(false);
  const [gifting, setGifting] = useState(false);

  function onLike() {
    like.mutate(id, {
      onSuccess: (result) => {
        setLiked(true);
        if (result.matched) toast.show({ message: t("profile.matched") });
      },
      onError: (error) => {
        if (error instanceof ApiError && error.code === "ALREADY_EXISTS") {
          setLiked(true);
          return;
        }
        const message =
          error instanceof ApiError && error.code === "NOT_FOUND"
            ? t("profile.likeRefused")
            : error instanceof ApiError && error.code === "SWIPE_LIMIT_REACHED"
              ? t("profile.likeLimit")
              : t("profile.likeFailed");
        toast.show({ message, tone: "error" });
      },
    });
  }

  return (
    <div className="bg-bg border-line sticky bottom-(--shell-nav-height) flex gap-3 border-t px-(--shell-gutter) py-3 md:bottom-0">
      <Button
        onClick={onLike}
        disabled={liked}
        loading={like.isPending}
        className="flex-1"
      >
        <Icon
          icon={Heart}
          size={18}
          className={liked ? "fill-current" : undefined}
        />
        {liked ? t("profile.liked") : t("profile.like")}
      </Button>
      {canGift && (
        <Button variant="ghost" onClick={() => setGifting(true)}>
          <Icon icon={Gift} size={18} />
          {t("gifts.give")}
        </Button>
      )}
      {gifting && (
        <GiftSheet
          recipientId={id}
          name={firstName}
          onClose={() => setGifting(false)}
        />
      )}
    </div>
  );
}
