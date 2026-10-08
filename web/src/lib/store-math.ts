/**
 * The store's arithmetic (T-8.7), from the packs `GET /packs` sends and the
 * Thread's price `GET /prices` sends: nothing here holds a price of its own.
 */

type PackPrice = { id: string; credits: number; price_paise: number };

const RUPEES = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

const WHOLE_RUPEES = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

/** "₹1,500", or "₹22.22" when the paise don't round to a rupee. */
export function rupees(paise: number): string {
  return RUPEES.format(paise / 100);
}

/** What one Vela costs in this pack: "₹50", "₹22.22". */
export function perVela(pack: PackPrice): string {
  return rupees(pack.price_paise / pack.credits);
}

/**
 * What opening one Thread costs at this pack's rate, to the rupee: "₹250",
 * "₹111" (D-099's table). `threadPrice` is `/prices`' `thread_open`.
 */
export function perThread(pack: PackPrice, threadPrice: number): string {
  return WHOLE_RUPEES.format(
    (pack.price_paise * threadPrice) / pack.credits / 100,
  );
}

/**
 * The pack whose Vela costs the least, which is what "Best value" says
 * (D-760): worked out from the rows, never a pack named in the code. None when
 * two packs tie for it, or there's nothing to compare: the words must be true.
 * Compared by cross-multiplying, so no rounding decides it.
 */
export function bestValue(packs: readonly PackPrice[]): string | null {
  if (packs.length < 2) return null;
  let best: PackPrice | null = null;
  let tied = false;
  for (const pack of packs) {
    if (best === null) {
      best = pack;
      continue;
    }
    // pack's rate < best's rate  ⇔  pack.price / pack.credits < best.price / best.credits
    const cheaper =
      pack.price_paise * best.credits - best.price_paise * pack.credits;
    if (cheaper < 0) {
      best = pack;
      tied = false;
    } else if (cheaper === 0) {
      tied = true;
    }
  }
  return tied || best === null ? null : best.id;
}
