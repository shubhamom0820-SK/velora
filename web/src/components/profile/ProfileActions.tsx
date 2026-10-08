"use client";

import { Heart } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { useLike } from "@/lib/queries/profiles";

/**
 * The sticky bar at the profile's foot (08-DESIGN §8): Like. "Open thread"
 * joins it with the chats' screens (P-440). A like already given, here or in
 * the deck, reads as given; one the API refuses says why.
 */
export function ProfileActions({ id }: { id: string }) {
  const toast = useToast();
  const like = useLike();
  const [liked, setLiked] = useState(false);

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
    </div>
  );
}
