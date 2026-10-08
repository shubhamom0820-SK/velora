import {
  expect,
  test as base,
  type APIRequestContext,
  type BrowserContext,
  type Page,
} from "@playwright/test";

export { expect };

const API = "http://127.0.0.1:8100";

let issued = 0;

/** A mobile number no other journey in this run uses: "98" and eight digits. */
export function freshNumber(): string {
  const n = (Date.now() + issued++) % 100_000_000;
  return `98${String(n).padStart(8, "0")}`;
}

/**
 * The code the fake SMS last sent the number, as its phone would have it, or
 * null if it never sent one (api/app/modules/e2e). Asked from Node, never the
 * page: the browser has no business with this endpoint.
 */
export async function codeFor(
  request: APIRequestContext,
  phone: string,
): Promise<string | null> {
  const response = await request.post(`${API}/v1/test/sms/last-code`, {
    data: { phone },
  });
  expect(response.status()).toBe(200);
  return ((await response.json()) as { code: string | null }).code;
}

/** Sign in through the screens, as a person would, ending on the birthday step. */
export async function signIn(
  page: Page,
  request: APIRequestContext,
  phone: string,
): Promise<string> {
  await page.goto("/login");
  await page.getByLabel("Mobile number").fill(phone);
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(
    page.getByRole("heading", { name: "Enter the code" }),
  ).toBeVisible();
  const code = await codeFor(request, phone);
  expect(code).toMatch(/^[0-9]{6}$/);
  // The phone's autofill puts all six into the first box.
  await page.getByRole("textbox", { name: "Digit 1 of 6" }).fill(code ?? "");
  await expect(page).toHaveURL(/\/onboarding\/birthday$/);
  return code ?? "";
}

const PIN = "4719";
const INTERESTS = ["Filter coffee", "Trekking", "Reading", "Cricket", "Travel"];

async function tapPin(page: Page, pin: string) {
  for (const digit of pin) {
    await page.getByRole("button", { name: digit, exact: true }).click();
  }
}

/**
 * A new man, through every onboarding screen, into the app (J1's way,
 * shortened: an area picked, no photo, no selfie). His username, which is
 * his number's last six digits after `kabir_`.
 */
export async function signUpMan(
  page: Page,
  context: BrowserContext,
  request: APIRequestContext,
): Promise<string> {
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
  const username = `kabir_${phone.slice(-6)}`;
  await page.getByLabel("Username").fill(username);
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
  return username;
}

type Watch = {
  /** Every URL the page went to, for "no phone number in a URL" (D-080). */
  urls: string[];
};

/**
 * Every journey fails on any CSP violation (P-41's lesson: an inline style or
 * zod's eval probe works under `next dev` and is blocked in production), and
 * records the URLs it visited.
 */
export const test = base.extend<Watch & { cspViolations: string[] }>({
  cspViolations: [
    async ({ page }, provide) => {
      const violations: string[] = [];
      await page.addInitScript(() => {
        document.addEventListener("securitypolicyviolation", (event) => {
          console.error(
            `CSP-VIOLATION ${event.violatedDirective} ${event.blockedURI}`,
          );
        });
      });
      page.on("console", (message) => {
        const text = message.text();
        if (
          text.startsWith("CSP-VIOLATION") ||
          text.includes("Content Security Policy")
        ) {
          violations.push(text);
        }
      });
      await provide(violations);
      expect(violations, "no CSP violation on any page").toEqual([]);
    },
    { auto: true },
  ],
  urls: async ({ page }, provide) => {
    const urls: string[] = [];
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame()) urls.push(frame.url());
    });
    await provide(urls);
  },
});
