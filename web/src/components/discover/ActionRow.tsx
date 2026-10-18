import { Heart, Star, X } from "lucide-react";

import { IconButton } from "@/components/ui/IconButton";
import { PriceTag } from "@/components/ui/PriceTag";
import { t } from "@/i18n/t";
import { creditsText } from "@/lib/credits";
import type { SwipeDirection } from "@/lib/queries/discover";

type ActionRowProps = {
  onSwipe: (direction: SwipeDirection) => void;
  /** Nothing to swipe: every button is off. */
  disabled: boolean;
  /**
   * The Super Like's price as `/prices` says it: a number for a man, null for
   * a woman, who pays nothing and sees no price (D-002); undefined while the
   * price loads (his button waits for it) or when the action is switched off,
   * which hides the button for everyone.
   */
  superPrice: number | null | undefined;
  superAvailable: boolean;
  /** A man's swipes left today; null for a woman or before it is known. */
  swipesLeft: number | null;
  /** The first name on the top card, which each button names; null with none. */
  name: string | null;
};

/**
 * Pass, Super and Like (08-DESIGN §8), each naming who is on top ("Like
 * Priya", T-9.11), and under them a man's swipes left today. His Super carries its price as a number, "5", from `/prices`, never
 * a literal; hers carries none.
 */
export function ActionRow({
  onSwipe,
  disabled,
  superPrice,
  superAvailable,
  swipesLeft,
  name,
}: ActionRowProps) {
  const superWaits = superPrice === undefined;
  const priced = typeof superPrice === "number";
  const velas: Record<string, string> = priced
    ? { velas: creditsText(superPrice) }
    : {};
  const superLabel =
    name === null
      ? t(
          priced ? "discover.actions.superPriced" : "discover.actions.super",
          velas,
        )
      : t(
          priced
            ? "discover.actions.named.superPriced"
            : "discover.actions.named.super",
          { name, ...velas },
        );
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        role="group"
        aria-label={t("discover.actions.label")}
        className="flex items-center gap-5"
      >
        <IconButton
          icon={X}
          label={
            name === null
              ? t("discover.actions.pass")
              : t("discover.actions.named.pass", { name })
          }
          size={46}
          tone="ink"
          disabled={disabled}
          onClick={() => onSwipe("pass")}
        />
        {superAvailable && (
          <IconButton
            icon={Star}
            label={superLabel}
            size={46}
            tone="accent"
            disabled={disabled || superWaits}
            badge={
              typeof superPrice === "number" ? (
                <PriceTag credits={superPrice} />
              ) : undefined
            }
            onClick={() => onSwipe("super")}
          />
        )}
        <IconButton
          icon={Heart}
          label={
            name === null
              ? t("discover.actions.like")
              : t("discover.actions.named.like", { name })
          }
          size={56}
          tone="filled"
          disabled={disabled}
          onClick={() => onSwipe("like")}
        />
      </div>
      {swipesLeft !== null && (
        <p className="text-small text-mute" role="status">
          {swipesLeft === 1
            ? t("discover.swipesLeft.one")
            : t("discover.swipesLeft.other", { count: swipesLeft })}
        </p>
      )}
    </div>
  );
}
