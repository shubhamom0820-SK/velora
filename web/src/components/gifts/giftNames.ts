import { t } from "@/i18n/t";
import type { Gift } from "@/lib/queries/gifts";

/**
 * A gift's label and picture by its id, from `GET /gifts`. A gift no longer
 * on sale isn't in the catalogue, so it reads "A gift" with no picture.
 */
export function giftNamed(
  gifts: readonly Gift[] | undefined,
  id: string,
): { label: string; asset: string | null } {
  const gift = gifts?.find((each) => each.id === id);
  return gift
    ? { label: gift.label, asset: gift.asset }
    : { label: t("gifts.someGift"), asset: null };
}
