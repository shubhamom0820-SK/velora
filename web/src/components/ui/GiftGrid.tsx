"use client";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

export type GiftTile = {
  id: string;
  label: string;
  /** The gift's picture, an emoji from its `gifts` row. */
  asset: string;
  /** The price in words, as the caller worked it out: "Free" or "10 Velas". */
  price: string;
};

type GiftGridProps = {
  gifts: GiftTile[];
  selected: string | null;
  onSelect: (id: string) => void;
  /** The free sends left this week, said above the gifts. */
  note?: string;
  disabled?: boolean;
};

/**
 * D-231's four gifts, two by two, each with its price, and the free sends left
 * this week above them (08-DESIGN §4, T-8.10; it was six tiles, 3×2). One is
 * chosen at a time; the sheet holding it sends. A man's alone: a woman is
 * never shown a price (D-002), which is the caller's to decide.
 */
export function GiftGrid({
  gifts,
  selected,
  onSelect,
  note,
  disabled = false,
}: GiftGridProps) {
  return (
    <div className="flex flex-col gap-3">
      {note && <p className="text-small text-mute">{note}</p>}
      <ul className="grid grid-cols-2 gap-3">
        {gifts.map((gift) => {
          const chosen = gift.id === selected;
          return (
            <li key={gift.id}>
              <button
                type="button"
                aria-pressed={chosen}
                aria-label={t("gifts.tile", {
                  label: gift.label,
                  price: gift.price,
                })}
                disabled={disabled}
                onClick={() => onSelect(gift.id)}
                className={cx(
                  "rounded-card focus-visible:outline-accent flex w-full flex-col items-center gap-1 border p-4 transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
                  chosen ? "border-accent bg-accent-soft" : "border-line",
                )}
              >
                <span aria-hidden className="text-title-1">
                  {gift.asset}
                </span>
                <span aria-hidden className="text-ui text-ink">
                  {gift.label}
                </span>
                <span
                  aria-hidden
                  className={cx(
                    "text-small",
                    chosen ? "text-accent" : "text-mute",
                  )}
                >
                  {gift.price}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
