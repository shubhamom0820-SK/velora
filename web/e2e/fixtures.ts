import {
  expect,
  test as base,
  type APIRequestContext,
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
