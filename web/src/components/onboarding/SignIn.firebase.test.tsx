import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/lib/queries/keys";
import type { Me } from "@/lib/queries/me";
import {
  clearCookies,
  envelope,
  fakeApi,
  json,
  setCookie,
} from "@/lib/testing/fakeApi";
import { resetSession, useSession } from "@/store/session";

import { SignIn } from "./SignIn";

/**
 * /login on a Firebase build (T-3.14, Path A). Firebase is played by a stand-in
 * for `@/lib/firebase`, the one module that touches the SDK: what reaches it,
 * and what the screen says for each answer it gives.
 */

const firebase = vi.hoisted(() => ({
  started: [] as HTMLElement[],
  sent: [] as string[],
  confirmed: [] as string[],
  signOuts: 0,
  disposed: 0,
  startError: null as Error | null,
  sendError: null as Error | null,
  confirmError: null as Error | null,
}));

vi.mock("@/lib/firebase", () => ({
  startFirebaseSignIn: vi.fn(async (container: HTMLElement) => {
    if (firebase.startError) throw firebase.startError;
    firebase.started.push(container);
    return {
      sendCode: async (phone: string) => {
        if (firebase.sendError) throw firebase.sendError;
        firebase.sent.push(phone);
      },
      confirm: async (code: string) => {
        firebase.confirmed.push(code);
        if (firebase.confirmError) throw firebase.confirmError;
        return "firebase-id-token";
      },
      signOut: async () => {
        firebase.signOuts += 1;
      },
      dispose: () => {
        firebase.disposed += 1;
      },
    };
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/login",
}));

/** An error as Firebase's SDK throws it: a FirebaseError with an auth/ code. */
function firebaseError(code: string): Error {
  return Object.assign(new Error(`Firebase: (${code}).`), {
    name: "FirebaseError",
    code,
  });
}

const PHONE_DIGITS = "9876543210";

function me(): Me {
  return {
    id: "u1",
    role: "user",
    status: "active",
    onboarding_step: "dob",
    gender: null,
    age: null,
    is_verified: false,
    has_pin: false,
    referral_code: "ABCDEFGH",
    balance: 0,
    profile: {
      first_name: null,
      username: null,
      about: null,
      hometown: null,
      city: null,
      seeking: null,
      intent_ids: [],
      interest_ids: [],
      is_hidden: false,
      hide_age: false,
      hide_distance: false,
      show_kudos: true,
      show_gifts: true,
      public_link: false,
      location: "fresh",
    },
  } as Me;
}

let client: QueryClient;
function renderUi(ui: ReactElement) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

function exchangeApi(
  exchange = () => json(200, { access_token: "t", user: me() }),
) {
  return fakeApi({ "POST /v1/auth/firebase": exchange });
}

async function ready() {
  await waitFor(() => expect(firebase.started).toHaveLength(1));
}

async function sendCode(typed = "98765 43210") {
  await ready();
  await userEvent.type(screen.getByLabelText("Mobile number"), typed);
  await userEvent.click(screen.getByRole("button", { name: "Send code" }));
}

async function enterCode(code: string) {
  await screen.findByRole("heading", { name: "Enter the code" });
  await userEvent.click(screen.getByRole("textbox", { name: "Digit 1 of 6" }));
  await userEvent.keyboard(code);
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "staging");
  vi.stubEnv("SIGN_IN_PATH", "firebase");
  setCookie("csrf_staging", "c1");
  // /login's restore has answered: nobody is signed in here (P-850).
  useSession.setState({ status: "signed-out" });
  Object.assign(firebase, {
    started: [],
    sent: [],
    confirmed: [],
    signOuts: 0,
    disposed: 0,
    startError: null,
    sendError: null,
    confirmError: null,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  clearCookies();
  resetSession();
});

describe("a Firebase build's /login (T-3.14)", () => {
  it("is open, and names Google before anything is sent (D-048)", async () => {
    const api_ = exchangeApi();
    renderUi(<SignIn />);
    await ready();

    expect(
      screen.getByRole("heading", { name: "What's your number?" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "By tapping Send code, you agree that Google's Firebase sends it. Google processes your number in the United States and keeps it to prevent spam and abuse.",
        { exact: false },
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "How we use your number" }),
    ).toHaveAttribute("href", "/privacy");
    expect(firebase.sent).toEqual([]);
    expect(api_.calls).toHaveLength(0);
  });

  it("starts Firebase into an element of its own as the screen opens", async () => {
    const { container } = renderUi(<SignIn />);
    await ready();

    expect(container.contains(firebase.started[0] ?? null)).toBe(true);
  });

  it("asks Firebase, not our API, to text +91 and the ten digits", async () => {
    const api_ = exchangeApi();
    renderUi(<SignIn />);

    await sendCode("+91 98765 43210");

    expect(
      await screen.findByText(`Sent to +91 ${PHONE_DIGITS}.`),
    ).toBeVisible();
    expect(firebase.sent).toEqual([`+91${PHONE_DIGITS}`]);
    expect(api_.calls).toHaveLength(0);
  });

  it("swaps Firebase's token for our session, fresh, then signs out of Firebase", async () => {
    const api_ = exchangeApi();
    renderUi(<SignIn />);
    await sendCode();

    await enterCode("123456");

    await waitFor(() => expect(useSession.getState().status).toBe("signed-in"));
    expect(firebase.confirmed).toEqual(["123456"]);
    expect(api_.sent()).toEqual(["POST /v1/auth/firebase"]);
    expect(api_.calls[0]?.body).toEqual({ id_token: "firebase-id-token" });
    expect(api_.calls[0]?.credentials).toBe("include");
    expect(useSession.getState().accessToken).toBe("t");
    expect(useSession.getState().lockDecided).toBe(true);
    expect(client.getQueryData(queryKeys.me())).toMatchObject({ id: "u1" });
    expect(firebase.signOuts).toBe(1);
  });

  it("signs out of Firebase when our API refuses the token too", async () => {
    exchangeApi(() => envelope(401, "FIREBASE_TOKEN_INVALID"));
    renderUi(<SignIn />);
    await sendCode();

    await enterCode("123456");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That sign-in didn't work. Send a new code.",
    );
    expect(firebase.signOuts).toBe(1);
    expect(useSession.getState().status).not.toBe("signed-in");
  });

  it.each([
    ["ACCOUNT_BANNED", 403, "This account can't sign in.", true],
    [
      "PHONE_NOT_SUPPORTED",
      422,
      "Only Indian mobile numbers can sign in for now.",
      false,
    ],
    [
      "RATE_LIMITED",
      429,
      "Too many tries. Wait a moment, then try again.",
      false,
    ],
  ])(
    "says our API's %s at the exchange",
    async (code, status, message, contact) => {
      exchangeApi(() => envelope(status, code));
      renderUi(<SignIn />);
      await sendCode();

      await enterCode("123456");

      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(Boolean(screen.queryByRole("link", { name: "Contact us" }))).toBe(
        contact,
      );
    },
  );

  it.each([
    [
      "auth/operation-not-allowed",
      // The region policy's refusal (8b of T-3.14's plan): the number, not them.
      "Only Indian mobile numbers can sign in for now.",
    ],
    ["auth/too-many-requests", "Too many tries. Wait a while, then try again."],
    ["auth/quota-exceeded", "We can't send codes right now. Try again later."],
    [
      "auth/captcha-check-failed",
      "We couldn't check this browser. Reload the page and try again.",
    ],
    [
      "auth/network-request-failed",
      "We couldn't reach Velora. Check your connection and try again.",
    ],
    ["auth/internal-error", "Something went wrong. Try again."],
  ])("says Firebase's %s when sending", async (code, message) => {
    exchangeApi();
    firebase.sendError = firebaseError(code);
    renderUi(<SignIn />);

    await sendCode();

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(
      screen.queryByRole("heading", { name: "Enter the code" }),
    ).not.toBeInTheDocument();
  });

  it("shows Firebase's refusal of the number beside it", async () => {
    exchangeApi();
    firebase.sendError = firebaseError("auth/invalid-phone-number");
    renderUi(<SignIn />);

    await sendCode();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a 10-digit Indian mobile number.",
    );
    expect(screen.getByLabelText("Mobile number")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it.each([
    ["auth/invalid-verification-code", "That code isn't right."],
    ["auth/code-expired", "That code has expired. Send a new one."],
  ])(
    "says Firebase's %s at the code, clears the boxes, and asks our API nothing",
    async (code, message) => {
      const api_ = exchangeApi();
      firebase.confirmError = firebaseError(code);
      renderUi(<SignIn />);
      await sendCode();

      await enterCode("111111");

      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(screen.getByRole("textbox", { name: "Digit 1 of 6" })).toHaveValue(
        "",
      );
      expect(api_.calls).toHaveLength(0);
    },
  );

  it("waits 45 s, as Path B does, then asks Firebase for a new code", async () => {
    let now = 1_000_000;
    vi.spyOn(Date, "now").mockImplementation(() => now);
    exchangeApi();
    renderUi(<SignIn />);
    await sendCode();

    expect(
      await screen.findByText("Send a new code in 45s"),
    ).toBeInTheDocument();
    now += 45_000;
    await userEvent.click(
      await screen.findByRole(
        "button",
        { name: "Send a new code" },
        { timeout: 2000 },
      ),
    );

    await waitFor(() =>
      expect(firebase.sent).toEqual([
        `+91${PHONE_DIGITS}`,
        `+91${PHONE_DIGITS}`,
      ]),
    );
  });

  it("says it can't reach us when Firebase never started (its script blocked)", async () => {
    exchangeApi();
    firebase.startError = new Error("chunk failed to load");
    renderUi(<SignIn />);

    await userEvent.type(screen.getByLabelText("Mobile number"), "98765 43210");
    await userEvent.click(screen.getByRole("button", { name: "Send code" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't reach Velora. Check your connection and try again.",
    );
    expect(firebase.sent).toEqual([]);
  });

  it("takes Firebase down when the screen goes", async () => {
    const { unmount } = renderUi(<SignIn />);
    await ready();

    unmount();

    expect(firebase.disposed).toBe(1);
  });
});

describe("a Path B build's /login never starts Firebase (D-081)", () => {
  it("and never names Google", async () => {
    vi.stubEnv("SIGN_IN_PATH", "otp");
    renderUi(<SignIn />);

    expect(
      screen.getByRole("heading", { name: "What's your number?" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Google/)).not.toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(firebase.started).toEqual([]);
  });
});
