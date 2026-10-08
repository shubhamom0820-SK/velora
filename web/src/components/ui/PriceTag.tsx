import { creditsCount } from "@/lib/credits";

type PriceTagProps = {
  /** The price from `/prices`, never a literal (D-004). */
  credits: number;
};

/**
 * A price badge on a button: the number alone, "5" (08-DESIGN §8). Hidden from
 * screen readers: the button it sits on says the price in words ("Super Like,
 * 5 Velas"). A woman's buttons carry none (D-002); the caller leaves it out.
 */
export function PriceTag({ credits }: PriceTagProps) {
  return (
    <span
      aria-hidden
      className="rounded-pill bg-accent text-micro text-on-accent border-surface inline-flex min-w-5 items-center justify-center border-2 px-1.5 py-0.5"
    >
      {creditsCount(credits)}
    </span>
  );
}
