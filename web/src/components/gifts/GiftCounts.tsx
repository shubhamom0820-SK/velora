"use client";

import { t } from "@/i18n/t";
import { useGiftCounts, useGifts } from "@/lib/queries/gifts";
import { useMe } from "@/lib/queries/me";

import { giftNamed } from "./giftNames";

/**
 * The gifts row on a profile (T-8.10, 08-DESIGN §6): how many of each she
 * received, never from whom or for what (D-016, D-652). Nothing while there
 * are none, which is also what everyone else is told when she turned
 * `show_gifts` off; on her own profile she still sees them, with a note that
 * only she can. A row inside the profile, so while loading or on a failure it
 * shows nothing and the profile stands without it.
 */
export function GiftCounts({ userId, own }: { userId: string; own: boolean }) {
  const counts = useGiftCounts(userId);
  const catalogue = useGifts();
  const me = useMe();
  const hidden = own && me.data?.profile.show_gifts === false;
  const rows = counts.data?.counts ?? [];
  if (rows.length === 0) return null;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-micro text-mute tracking-wide uppercase">
        {t("gifts.received")}
      </h2>
      <ul className="bg-surface rounded-card border-line grid grid-cols-2 gap-3 border p-4">
        {rows.map((row) => {
          const gift = giftNamed(catalogue.data?.gifts, row.gift_id);
          return (
            <li key={row.gift_id} className="flex flex-col">
              <span className="text-title-2 text-ink">{row.count}</span>
              <span className="text-small text-mute">
                {gift.asset && <span aria-hidden>{gift.asset} </span>}
                {gift.label}
              </span>
            </li>
          );
        })}
      </ul>
      {hidden && <p className="text-small text-mute">{t("gifts.onlyYou")}</p>}
    </section>
  );
}
