import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import { WaitlistForm } from "./WaitlistForm";

// The real API client, with the network stubbed: what reaches `fetch` is what
// the API would receive.
const fetchMock = vi.fn<typeof fetch>();

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderForm() {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <WaitlistForm />
    </QueryClientProvider>,
  );
  return {
    email: screen.getByRole("textbox", { name: t("landing.waitlist.email") }),
    city: screen.getByRole("textbox", { name: t("landing.waitlist.city") }),
    join: screen.getByRole("button", { name: t("landing.waitlist.join") }),
  };
}

/** The JSON body of the one request the form sent. */
function sentBody(): unknown {
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, init] = fetchMock.mock.calls[0] ?? [];
  expect(String(url)).toBe("https://api.test/v1/waitlist");
  expect(init?.method).toBe("POST");
  return JSON.parse(String(init?.body));
}

describe("WaitlistForm", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("asks for an email and an optional city, and links the privacy policy", () => {
    const { email, city } = renderForm();

    expect(email).toHaveAttribute("type", "email");
    expect(email).toHaveAttribute("autocomplete", "email");
    expect(city).toHaveAttribute("maxlength", "40");
    expect(
      screen.getByRole("link", { name: t("landing.waitlist.privacyLink") }),
    ).toHaveAttribute("href", "/privacy");
  });

  it("joins, showing the wait, then the success in place of the form", async () => {
    let answer: (response: Response) => void = () => {};
    fetchMock.mockReturnValue(
      new Promise((resolve) => {
        answer = resolve;
      }),
    );
    const { email, city, join } = renderForm();

    await userEvent.type(email, "  priya@example.com ");
    await userEvent.type(city, " Pune ");
    await userEvent.click(join);

    expect(join).toHaveAttribute("aria-busy", "true");
    expect(sentBody()).toEqual({ email: "priya@example.com", city: "Pune" });

    answer(json(201, {}));

    const joined = await screen.findByText(t("landing.waitlist.joined"));
    // Inside the live region that was already in the page, so it's announced.
    expect(joined.closest('[role="status"]')).not.toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("leaves the city out when it's blank", async () => {
    fetchMock.mockResolvedValue(json(201, {}));
    const { email, city, join } = renderForm();

    await userEvent.type(email, "priya@example.com");
    await userEvent.type(city, "   ");
    await userEvent.click(join);

    expect(sentBody()).toEqual({ email: "priya@example.com" });
  });

  it.each(["priya", "priya@example", "priya @example.com", "   "])(
    "turns away %j without asking the API, and moves focus to the email",
    async (typed) => {
      const { email, join } = renderForm();

      await userEvent.type(email, typed);
      await userEvent.click(join);

      expect(fetchMock).not.toHaveBeenCalled();
      expect(email).toHaveAttribute("aria-invalid", "true");
      expect(email).toHaveAccessibleDescription(
        t("landing.waitlist.invalidEmail"),
      );
      expect(email).toHaveFocus();
    },
  );

  it("says to wait when the API says too many tries", async () => {
    fetchMock.mockResolvedValue(
      json(429, {
        error: {
          code: "RATE_LIMITED",
          message: "Too many tries. Wait a moment and try again.",
          details: { retry_after_s: 42 },
        },
      }),
    );
    const { email, join } = renderForm();

    await userEvent.type(email, "priya@example.com");
    await userEvent.click(join);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      t("landing.waitlist.rateLimited"),
    );
    expect(join).not.toHaveAttribute("aria-busy");
  });

  it("puts the API's validation error on the email", async () => {
    fetchMock.mockResolvedValue(
      json(400, {
        error: {
          code: "VALIDATION_ERROR",
          message: "Some of the information sent was not valid.",
          details: { fields: [{ field: "email", problem: "isn't an email" }] },
        },
      }),
    );
    const { email, join } = renderForm();

    await userEvent.type(email, "priya@example.com");
    await userEvent.click(join);

    expect(
      await screen.findByText(t("landing.waitlist.invalidEmail")),
    ).toBeInTheDocument();
    expect(email).toHaveAttribute("aria-invalid", "true");
  });

  it("says it didn't go through when the network fails, and clears that on edit", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const { email, join } = renderForm();

    await userEvent.type(email, "priya@example.com");
    await userEvent.click(join);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      t("landing.waitlist.failed"),
    );

    await userEvent.type(email, "m");

    expect(screen.queryByRole("alert")).toBeNull();
  });
});
