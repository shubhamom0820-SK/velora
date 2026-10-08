/**
 * Razorpay's Checkout (T-8.7): the only code that loads its script, and only
 * when a man taps a pack on a Razorpay build (checkout-path.ts), never on page
 * load. Its hosts are in the CSP of the app's routes (security-headers.ts,
 * RAZORPAY): a CSP error at checkout is that list, not Razorpay's bug.
 *
 * Checkout's window says only that the man finished or closed it. Neither is
 * the payment's outcome: the Velas come from the verified webhook alone (T-8.2),
 * which the store learns by polling `GET /payments/{id}` (queries/store.ts).
 * So `onPaid` hands back nothing of Razorpay's reply, and nothing of it is
 * sent anywhere.
 */

/** Razorpay's script, from its own docs (Standard Checkout, read 9 October 2026). */
export const RAZORPAY_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

/** What Checkout opens with: the API's order, as `POST /payments/orders` gave it. */
export type CheckoutOrder = {
  keyId: string;
  orderId: string;
  amountPaise: number;
  /** Shown in Razorpay's window: the brand. */
  name: string;
  /** Shown under it: what he is buying, "30 Velas". */
  description: string;
};

export type CheckoutCallbacks = {
  /** Razorpay says the payment went through: start waiting for the webhook. */
  onPaid: () => void;
  /** He closed the window without paying. Never called after `onPaid`. */
  onDismiss: () => void;
};

type RazorpayOptions = {
  key: string;
  order_id: string;
  amount: number;
  currency: "INR";
  name: string;
  description: string;
  handler: () => void;
  modal: { ondismiss: () => void };
};

type RazorpayInstance = { open: () => void };

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayInstance;
  }
}

/** The script didn't load: offline, blocked, or Razorpay down. Nothing was charged. */
export class CheckoutUnavailable extends Error {
  constructor() {
    super("Razorpay's Checkout script didn't load.");
    this.name = "CheckoutUnavailable";
  }
}

let loading: Promise<void> | null = null;

/** Loads the script once; a failed load is forgotten, so "Try again" loads it afresh. */
export function loadRazorpay(): Promise<void> {
  if (typeof window !== "undefined" && window.Razorpay)
    return Promise.resolve();
  loading ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = RAZORPAY_SCRIPT;
    script.async = true;
    script.onload = () => {
      if (window.Razorpay) resolve();
      else reject(new CheckoutUnavailable());
    };
    script.onerror = () => {
      script.remove();
      reject(new CheckoutUnavailable());
    };
    document.head.append(script);
  }).catch((error: unknown) => {
    loading = null;
    throw error;
  });
  return loading;
}

/**
 * Opens Razorpay's window on the order. Rejects with `CheckoutUnavailable`
 * if the script can't load. Razorpay lets a man try another method inside its
 * window after a failure, so a failure isn't reported here: closing the window
 * without paying is.
 */
export async function openRazorpay(
  order: CheckoutOrder,
  { onPaid, onDismiss }: CheckoutCallbacks,
): Promise<void> {
  await loadRazorpay();
  const Razorpay = window.Razorpay;
  if (!Razorpay) throw new CheckoutUnavailable();
  let paid = false;
  new Razorpay({
    key: order.keyId,
    order_id: order.orderId,
    amount: order.amountPaise,
    currency: "INR",
    name: order.name,
    description: order.description,
    handler: () => {
      paid = true;
      onPaid();
    },
    modal: {
      ondismiss: () => {
        if (!paid) onDismiss();
      },
    },
  }).open();
}

/** For tests: forget a loaded script. */
export function resetRazorpayForTests(): void {
  loading = null;
  delete window.Razorpay;
}
