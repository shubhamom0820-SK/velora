/**
 * How a build takes a man's payment (T-8.7, D-761), fixed at build time from
 * `APP_ENV`: `next.config` puts it in `CHECKOUT_PATH`. An allowlist (CLAUDE.md
 * rule 16), like the sign-in path; the web never reads `PAYMENTS_PROVIDER`.
 *
 * - `standin`: local and CI, where the API's gateway is the fake (T-8.1). No
 *   Razorpay script loads; a sheet of our own stands in for its window, and
 *   the fake gateway's local-only webhook pays the order (J8, J9).
 * - `razorpay`: staging and production. Razorpay's Checkout script, loaded on
 *   demand (razorpay.ts), under the CSP's Razorpay hosts (security-headers.ts).
 *
 * A build with neither takes no payment: the store says so, never a guess.
 */
export type CheckoutPath = "standin" | "razorpay";

type BuildEnv = Readonly<Record<string, string | undefined>>;

const PATH_FOR: ReadonlyMap<string, CheckoutPath> = new Map([
  ["local", "standin"],
  ["ci", "standin"],
  ["staging", "razorpay"],
  ["production", "razorpay"],
]);

export function checkoutPathFor(
  env: BuildEnv,
  { dev }: { dev: boolean },
): CheckoutPath | null {
  const appEnv = env.APP_ENV;
  if (appEnv === undefined) return dev ? "standin" : null;
  return PATH_FOR.get(appEnv) ?? null;
}

/** This build's path, read from the build: only the two values it knows. */
export function checkoutPath(
  value: string | undefined = process.env.CHECKOUT_PATH,
): CheckoutPath | null {
  return value === "standin" || value === "razorpay" ? value : null;
}

/**
 * The fake gateway's public key (api/app/core/providers/payments.py). An
 * order carrying it was made by the fake, and only the stand-in can pay it;
 * Razorpay's window would refuse it.
 */
export const FAKE_KEY_ID = "rzp_fake_local_only";

/**
 * Which window pays an order: the stand-in only on a stand-in build and only
 * for the fake's key, Razorpay's only on a Razorpay build and never for the
 * fake's key. Anything else is none, and the store says payments aren't
 * available: a staging build never opens the stand-in, whatever the API
 * answers, and a local build never sends a real key to a stand-in that can't
 * take a payment.
 */
export function checkoutWindowFor(
  path: CheckoutPath | null,
  keyId: string,
): CheckoutPath | null {
  if (path === "standin") return keyId === FAKE_KEY_ID ? "standin" : null;
  if (path === "razorpay") return keyId === FAKE_KEY_ID ? null : "razorpay";
  return null;
}
