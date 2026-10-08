import type { APIRequestContext, Page } from "@playwright/test";

import { expect, signUpMan, test } from "./fixtures";

/**
 * J8 and J9 (06-TESTING), T-8.7: a man buys Velas on the fake gateway, and a
 * payment that fails is tried again on the same order.
 *
 * On a local build the store pays by the stand-in (D-761): no Razorpay
 * script, and the fake gateway's local-only webhook stands in for Razorpay's
 * (api/app/modules/e2e), asked from Node as Razorpay would call the API,
 * never by the page. The Velas still come from T-8.2's verified webhook
 * alone, and the page learns of them only by polling, as it would on
 * production.
 *
 * Each man signs up through the screens (`signUpMan`, J1's way shortened), so
 * he starts with T-8.11's 5 welcome Velas.
 */

const API = "http://127.0.0.1:8100";
/** The balance on the wallet's card: his Velas, as the API holds them. */
async function balanceIs(page: Page, velas: number) {
  await expect(
    page.getByRole("heading", { name: "Your balance" }).locator(".."),
  ).toContainText(String(velas));
}

/** Taps a pack and returns the order the API made for it. */
async function buy(page: Page, velas: string): Promise<string> {
  const ordered = page.waitForResponse(
    (response) =>
      response.url() === `${API}/v1/payments/orders` &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("dialog", { name: "Buy Velas" })
    .getByRole("button", { name: new RegExp(`^${velas}`) })
    .click();
  const response = await ordered;
  expect(response.status()).toBe(200);
  return ((await response.json()) as { payment_id: string }).payment_id;
}

/** The fake gateway's webhook for the payment, as Razorpay would send it. */
async function gatewaySays(
  request: APIRequestContext,
  paymentId: string,
  outcome: "captured" | "failed",
) {
  const response = await request.post(`${API}/v1/test/payments/webhook`, {
    data: { payment_id: paymentId, outcome },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ delivered_status: 200 });
}

async function openStore(page: Page) {
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Wallet" })
    .click();
  await expect(page).toHaveURL(/\/wallet$/);
  await balanceIs(page, 5);
  // "Buy Velas" under the card; the header's pill is "5 Velas. Buy Velas".
  await page.getByRole("button", { name: "Buy Velas", exact: true }).click();
  const store = page.getByRole("dialog", { name: "Buy Velas" });
  await expect(store.getByRole("listitem")).toHaveCount(4);
  await expect(store).toContainText("Best value");
  await expect(store).not.toContainText(/popular|gst/i);
}

test("J8: a man buys Velas on the fake gateway, and his balance shows them", async ({
  page,
  context,
  request,
}) => {
  await signUpMan(page, context, request);
  await openStore(page);

  const paymentId = await buy(page, "30 Velas");
  const standin = page.getByRole("dialog", { name: "Test checkout" });
  await expect(standin).toBeVisible();

  // Razorpay captures the payment and tells the API; the window says done.
  await gatewaySays(request, paymentId, "captured");
  await standin.getByRole("button", { name: "Payment went through" }).click();

  // 30, and the first purchase's 6 (D-231).
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "36 Velas added to your balance" }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await balanceIs(page, 41);
  await expect(
    page.getByRole("button", { name: "41 Velas. Buy Velas" }),
  ).toBeVisible();
});

test("J9: a payment that fails is tried again on the same order, and goes through", async ({
  page,
  context,
  request,
}) => {
  await signUpMan(page, context, request);
  await openStore(page);
  const orders: string[] = [];
  page.on("request", (sent) => {
    if (
      sent.method() === "POST" &&
      sent.url() === `${API}/v1/payments/orders`
    ) {
      orders.push(sent.url());
    }
  });

  const paymentId = await buy(page, "30 Velas");
  await gatewaySays(request, paymentId, "failed");
  await page
    .getByRole("dialog", { name: "Test checkout" })
    .getByRole("button", { name: "Close without paying" })
    .click();

  const notPaid = page.getByRole("dialog", {
    name: "Payment didn't go through",
  });
  await expect(notPaid).toBeVisible();
  await expect(notPaid).not.toContainText(/no money was taken/i);
  await notPaid.getByRole("button", { name: "Try again" }).click();

  // The same order, opened again: never a second one to pay for.
  const standin = page.getByRole("dialog", { name: "Test checkout" });
  await expect(standin).toBeVisible();
  await gatewaySays(request, paymentId, "captured");
  await standin.getByRole("button", { name: "Payment went through" }).click();

  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "36 Velas added to your balance" }),
  ).toBeVisible();
  await balanceIs(page, 41);
  expect(orders).toHaveLength(1);
});
