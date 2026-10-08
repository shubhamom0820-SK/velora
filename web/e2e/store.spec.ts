import type { APIRequestContext, BrowserContext, Page } from "@playwright/test";

import { expect, freshNumber, signIn, test } from "./fixtures";

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
 * Each man signs up through the screens (J1's way, shortened: an area picked,
 * no photo, no selfie), so he starts with T-8.11's 5 welcome Velas.
 */

const API = "http://127.0.0.1:8100";
const PIN = "4719";
const INTERESTS = ["Filter coffee", "Trekking", "Reading", "Cricket", "Travel"];

async function tapPin(page: Page, pin: string) {
  for (const digit of pin) {
    await page.getByRole("button", { name: digit, exact: true }).click();
  }
}

/** A new man, through every onboarding screen, into the app. */
async function signUpMan(
  page: Page,
  context: BrowserContext,
  request: APIRequestContext,
): Promise<void> {
  await context.clearPermissions();
  const phone = freshNumber();
  await signIn(page, request, phone);

  await page.getByLabel("Date of birth").fill("1998-03-02");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Yes, that's right" }).click();
  await expect(page).toHaveURL(/\/onboarding\/gender$/);
  await page.getByRole("radio", { name: /^Man/ }).check();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/looking-for$/);
  await page.getByRole("button", { name: "Women", exact: true }).click();
  await page.getByRole("button", { name: "Something serious" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/name$/);
  await page.getByLabel("First name").fill("Kabir");
  await page.getByLabel("Hometown, where you're from").fill("Jalandhar");
  await page.getByLabel("Where you live now").fill("Phagwara");
  await page.getByRole("button", { name: "Continue" }).click();

  // No position shared: he picks an area, as J1's twin does.
  await expect(page).toHaveURL(/\/onboarding\/location$/);
  await page.getByRole("button", { name: "Share my location" }).click();
  await expect(
    page.getByRole("heading", { name: "Pick your area" }),
  ).toBeVisible();
  await page.getByRole("radio", { name: "Model Town" }).check();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page).toHaveURL(/\/onboarding\/username$/);
  await page.getByLabel("Username").fill(`kabir_${phone.slice(-6)}`);
  await expect(page.getByText("That one's free.")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/about$/);
  await page
    .getByLabel("About you")
    .fill("Cricket on Sundays and chai with too much ginger.");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/photos$/);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/interests$/);
  for (const label of INTERESTS) {
    await page.getByRole("button", { name: label, exact: true }).click();
  }
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/onboarding\/pin$/);
  await tapPin(page, PIN);
  await expect(
    page.getByRole("heading", { name: "Confirm your PIN" }),
  ).toBeVisible();
  await tapPin(page, PIN);
  await expect(page).toHaveURL(/\/onboarding\/selfie$/);
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page).toHaveURL(/\/discover$/);
}

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
