import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CheckoutUnavailable,
  RAZORPAY_SCRIPT,
  loadRazorpay,
  openRazorpay,
  resetRazorpayForTests,
  type CheckoutOrder,
} from "./razorpay";

const ORDER: CheckoutOrder = {
  keyId: "rzp_test_aaaaaaaa",
  orderId: "order_Abc",
  amountPaise: 150_000,
  name: "Zephyrine",
  description: "30 Velas",
};

function scripts(): HTMLScriptElement[] {
  return [
    ...document.head.querySelectorAll<HTMLScriptElement>(
      `script[src="${RAZORPAY_SCRIPT}"]`,
    ),
  ];
}

type Options = {
  key: string;
  order_id: string;
  amount: number;
  currency: string;
  handler: () => void;
  modal: { ondismiss: () => void };
} & Record<string, unknown>;

/** Razorpay's script as it lands: it defines `window.Razorpay`, then loads. */
function scriptLoads(): { opened: Options[] } {
  const opened: Options[] = [];
  window.Razorpay = class {
    constructor(private readonly options: Options) {}
    open() {
      opened.push(this.options);
    }
  } as unknown as Window["Razorpay"];
  const [script] = scripts();
  script?.dispatchEvent(new Event("load"));
  return { opened };
}

afterEach(() => {
  for (const script of scripts()) script.remove();
  resetRazorpayForTests();
});

describe("Razorpay's script loads on demand, once (T-8.7)", () => {
  it("is not in the page until something asks for it", () => {
    expect(scripts()).toHaveLength(0);
  });

  it("is added once, from Razorpay's own address, however often it is asked for", async () => {
    const first = loadRazorpay();
    const second = loadRazorpay();
    expect(scripts()).toHaveLength(1);
    scriptLoads();
    await expect(Promise.all([first, second])).resolves.toBeDefined();
    expect(scripts()[0]?.async).toBe(true);
  });

  it("a script that fails is CheckoutUnavailable, and the next try loads it afresh", async () => {
    const first = loadRazorpay();
    scripts()[0]?.dispatchEvent(new Event("error"));
    await expect(first).rejects.toBeInstanceOf(CheckoutUnavailable);
    expect(scripts()).toHaveLength(0);

    const second = loadRazorpay();
    expect(scripts()).toHaveLength(1);
    scriptLoads();
    await expect(second).resolves.toBeUndefined();
  });
});

describe("Checkout opens on the API's order, and reports only finished or closed", () => {
  it("opens with the order's key, id and amount, in rupees, and nothing about the man", async () => {
    const opening = openRazorpay(ORDER, {
      onPaid: vi.fn(),
      onDismiss: vi.fn(),
    });
    const { opened } = scriptLoads();
    await opening;

    expect(opened).toHaveLength(1);
    const options = opened[0];
    expect(options).toMatchObject({
      key: "rzp_test_aaaaaaaa",
      order_id: "order_Abc",
      amount: 150_000,
      currency: "INR",
      name: "Zephyrine",
      description: "30 Velas",
    });
    // No prefill: the web never hands his number or name to the gateway.
    expect(Object.keys(options ?? {}).sort()).toEqual(
      [
        "amount",
        "currency",
        "description",
        "handler",
        "key",
        "modal",
        "name",
        "order_id",
      ].sort(),
    );
  });

  it("finished: onPaid, and closing the window afterwards isn't a dismissal", async () => {
    const onPaid = vi.fn();
    const onDismiss = vi.fn();
    const opening = openRazorpay(ORDER, { onPaid, onDismiss });
    const { opened } = scriptLoads();
    await opening;

    opened[0]?.handler();
    opened[0]?.modal.ondismiss();

    expect(onPaid).toHaveBeenCalledTimes(1);
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("closed without paying: onDismiss", async () => {
    const onPaid = vi.fn();
    const onDismiss = vi.fn();
    const opening = openRazorpay(ORDER, { onPaid, onDismiss });
    const { opened } = scriptLoads();
    await opening;

    opened[0]?.modal.ondismiss();

    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onPaid).not.toHaveBeenCalled();
  });

  it("a script that won't load rejects, and no window opens", async () => {
    const opening = openRazorpay(ORDER, {
      onPaid: vi.fn(),
      onDismiss: vi.fn(),
    });
    scripts()[0]?.dispatchEvent(new Event("error"));
    await expect(opening).rejects.toBeInstanceOf(CheckoutUnavailable);
  });
});
