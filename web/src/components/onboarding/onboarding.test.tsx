import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Me } from "@/lib/queries/me";
import { queryKeys } from "@/lib/queries/keys";
import {
  clearCookies,
  envelope,
  fakeApi,
  json,
  setCookie,
} from "@/lib/testing/fakeApi";
import { resetSession, useSession } from "@/store/session";

import { WaitlistBox } from "@/components/marketing/WaitlistBox";

import { AboutStep } from "./AboutStep";
import { BirthdayStep } from "./BirthdayStep";
import { GenderStep } from "./GenderStep";
import { InterestsStep } from "./InterestsStep";
import { LocationStep } from "./LocationStep";
import { LookingForStep } from "./LookingForStep";
import { NameStep } from "./NameStep";
import { PhotosStep } from "./PhotosStep";
import { PinStep } from "./PinStep";
import { SelfieStep } from "./SelfieStep";
import { SignIn } from "./SignIn";
import { USERNAME_CHECK_DELAY_MS, UsernameStep } from "./UsernameStep";

const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
// The toast lives in the root layout (the selfie step's welcome, T-8.11).
vi.mock("@/components/ui/useToast", () => ({
  useToast: () => ({ show: vi.fn(), dismiss: vi.fn() }),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: nav.push,
    replace: nav.replace,
    prefetch: vi.fn(),
  }),
  usePathname: () => "/",
}));

const PHONE_DIGITS = "9876543210";

function me(
  overrides: Partial<Me> = {},
  profile: Partial<Me["profile"]> = {},
): Me {
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
    ...overrides,
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
      ...profile,
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

/** Every URL the screens asked the router for. */
function navigated(): string[] {
  return [...nav.push.mock.calls, ...nav.replace.mock.calls].map((c) =>
    String(c[0]),
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  vi.stubEnv("AUTH_COOKIE_SUFFIX", "local");
  vi.stubEnv("SIGN_IN_PATH", "otp");
  setCookie("csrf_local", "c1");
  nav.push.mockReset();
  nav.replace.mockReset();
  // jsdom keeps one URL for the whole file: start each test from the same one,
  // so no test inherits another's.
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  clearCookies();
  resetSession();
});

describe("which way /login signs in (D-081)", () => {
  // A Firebase build is open since T-3.14 (SignIn.firebase.test.tsx).
  it.each(["", "msg91"])(
    "a \"%s\" build says sign-in isn't open yet, never a form that can't work",
    (path) => {
      vi.stubEnv("SIGN_IN_PATH", path);
      const api_ = fakeApi({});

      renderUi(<SignIn />);

      expect(
        screen.getByRole("heading", { name: "Sign-in isn't open yet" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "Join the waitlist" }),
      ).toHaveAttribute("href", "/#waitlist");
      expect(screen.queryByLabelText("Mobile number")).not.toBeInTheDocument();
      expect(api_.calls).toHaveLength(0);
    },
  );

  it("links to a waitlist box that is there on the home page", () => {
    const { container } = renderUi(<WaitlistBox />);
    expect(container.querySelector("section#waitlist")).not.toBeNull();
  });
});

describe("signing in by code (T-3.11, Path B)", () => {
  // /login's restore has answered: nobody is signed in here (P-850).
  beforeEach(() => useSession.setState({ status: "signed-out" }));

  function signInApi(
    verify = () => json(200, { access_token: "t", user: me() }),
  ) {
    return fakeApi({
      "POST /v1/auth/otp/send": () => json(200, { resend_after_s: 45 }),
      "POST /v1/auth/otp/verify": verify,
    });
  }

  async function sendCode(typed = "98765 43210") {
    await userEvent.type(screen.getByLabelText("Mobile number"), typed);
    await userEvent.click(screen.getByRole("button", { name: "Send code" }));
    await screen.findByRole("heading", { name: "Enter the code" });
  }

  async function enterCode(code: string) {
    await userEvent.click(
      screen.getByRole("textbox", { name: "Digit 1 of 6" }),
    );
    await userEvent.keyboard(code);
  }

  // P-70: a foreign number's ten digits behind the fixed +91 would text a
  // stranger in India, so the screen says so before anything is typed.
  it("says it takes Indian numbers only before anything is typed, with +91 fixed outside the field", () => {
    signInApi();
    renderUi(<SignIn />);

    const field = screen.getByLabelText("Mobile number");
    expect(field).toHaveValue("");
    expect(field).toHaveAccessibleDescription(
      "Velora takes Indian mobile numbers only. We're starting in Phagwara.",
    );
    expect(
      screen.getByText(
        "Velora takes Indian mobile numbers only. We're starting in Phagwara.",
      ),
    ).toBeVisible();
    const prefix = screen.getByText("+91");
    expect(field).not.toContainElement(prefix);
    expect(prefix.tagName).not.toBe("INPUT");
  });

  it("needs ten digits before it sends, and sends them as +91", async () => {
    const api_ = signInApi();
    renderUi(<SignIn />);

    await userEvent.type(screen.getByLabelText("Mobile number"), "98765 4321");
    expect(screen.getByRole("button", { name: "Send code" })).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Mobile number"), "0");
    await userEvent.click(screen.getByRole("button", { name: "Send code" }));

    await screen.findByText(`Sent to +91 ${PHONE_DIGITS}.`);
    expect(api_.calls[0]?.body).toEqual({ phone: `+91${PHONE_DIGITS}` });
  });

  it.each(["+91 98765 43210", "098765 43210"])(
    "takes %s as people paste it",
    async (typed) => {
      const api_ = signInApi();
      renderUi(<SignIn />);

      await sendCode(typed);

      expect(api_.calls[0]?.body).toEqual({ phone: `+91${PHONE_DIGITS}` });
    },
  );

  it("signs in with the six digits, fresh, and never puts the number in a URL (D-080)", async () => {
    const api_ = signInApi();
    const before = window.location.href;
    renderUi(<SignIn />);
    await sendCode();

    await enterCode("123456");

    await waitFor(() => expect(useSession.getState().status).toBe("signed-in"));
    expect(api_.calls[1]?.body).toEqual({
      phone: `+91${PHONE_DIGITS}`,
      otp: "123456",
    });
    expect(useSession.getState().lockDecided).toBe(true);
    expect(client.getQueryData(queryKeys.me())).toMatchObject({ id: "u1" });
    expect(window.location.href).toBe(before);
    expect(window.location.href).not.toContain(PHONE_DIGITS);
    for (const url of navigated()) {
      expect(url).not.toMatch(/[0-9]{4}/);
    }
  });

  it("says how many tries are left, and clears the boxes", async () => {
    signInApi(() => envelope(400, "OTP_INVALID", { attempts_left: 3 }));
    renderUi(<SignIn />);
    await sendCode();

    await enterCode("111111");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That code isn't right. 3 tries left.",
    );
    expect(screen.getByRole("textbox", { name: "Digit 1 of 6" })).toHaveValue(
      "",
    );
  });

  it.each(["ACCOUNT_BANNED", "ACCOUNT_FROZEN", "FORBIDDEN"])(
    "%s at sign-in: one neutral line and a way to a person",
    async (code) => {
      signInApi(() => envelope(403, code));
      renderUi(<SignIn />);
      await sendCode();

      await enterCode("123456");

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent("This account can't sign in.");
      expect(screen.getByRole("link", { name: "Contact us" })).toHaveAttribute(
        "href",
        "/contact",
      );
    },
  );

  it("shows the server's refusal of the number beside it", async () => {
    fakeApi({
      "POST /v1/auth/otp/send": () =>
        envelope(400, "VALIDATION_ERROR", {
          fields: [{ field: "phone", problem: "isn't a mobile number" }],
        }),
    });
    renderUi(<SignIn />);

    // Ten digits, so the shape passes; a landline, so the server refuses it (D-070).
    await userEvent.type(screen.getByLabelText("Mobile number"), "22222 22222");
    await userEvent.click(screen.getByRole("button", { name: "Send code" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a 10-digit Indian mobile number.",
    );
  });

  it("waits out resend_after_s before offering a new code", async () => {
    let now = 1_000_000;
    vi.spyOn(Date, "now").mockImplementation(() => now);
    const api_ = signInApi();
    renderUi(<SignIn />);
    await sendCode();

    expect(screen.getByText("Send a new code in 45s")).toBeInTheDocument();
    now += 45_000;
    expect(
      await screen.findByRole(
        "button",
        { name: "Send a new code" },
        { timeout: 2000 },
      ),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Send a new code" }),
    );
    await waitFor(() =>
      expect(api_.sent()).toEqual([
        "POST /v1/auth/otp/send",
        "POST /v1/auth/otp/send",
      ]),
    );
  });

  it("goes back to the number with 'Back'", async () => {
    signInApi();
    renderUi(<SignIn />);
    await sendCode();

    await userEvent.click(screen.getByRole("button", { name: "Back" }));

    expect(screen.getByLabelText("Mobile number")).toBeInTheDocument();
  });

  it("says what happened after an under-18 date of birth", () => {
    useSession.getState().endForUnderage();
    renderUi(<SignIn />);

    expect(
      screen.getByRole("heading", { name: "You need to be 18 to use Velora" }),
    ).toBeInTheDocument();
  });
});

describe("the date of birth (D-079)", () => {
  async function chooseDate(value: string) {
    const input = screen.getByLabelText("Date of birth");
    await userEvent.clear(input);
    await userEvent.type(input, value);
  }

  it("asks before it sends, and sends an under-18 date for the server to judge", async () => {
    const api_ = fakeApi({
      "POST /v1/me/dob": () => envelope(422, "UNDERAGE"),
    });
    useSession.getState().signIn("t", { fresh: true });
    renderUi(<BirthdayStep me={me()} />);

    await chooseDate("2015-01-01");
    // No age worked out in the browser, and no refusal there.
    expect(screen.queryByText(/You're|appear as/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(api_.calls).toHaveLength(0);
    expect(await screen.findByRole("dialog")).toHaveTextContent(
      "You were born on 1 January 2015.",
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Yes, that's right" }),
    );

    await waitFor(() =>
      expect(useSession.getState().farewell).toBe("underage"),
    );
    expect(api_.calls[0]?.body).toEqual({ dob: "2015-01-01" });
    expect(useSession.getState().status).toBe("signed-out");
  });

  it("sends nothing when the person changes their mind", async () => {
    const api_ = fakeApi({});
    renderUi(<BirthdayStep me={me()} />);

    await chooseDate("2001-03-14");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Change it" }),
    );

    expect(api_.calls).toHaveLength(0);
  });

  it("moves on to the next step once saved", async () => {
    fakeApi({
      "POST /v1/me/dob": () =>
        json(200, me({ onboarding_step: "gender", age: 25 })),
    });
    renderUi(<BirthdayStep me={me()} />);

    await chooseDate("2001-03-14");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Yes, that's right" }),
    );

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/gender"),
    );
  });

  it("shows an answered date as the age only, read-only", async () => {
    renderUi(<BirthdayStep me={me({ onboarding_step: "seeking", age: 25 })} />);

    expect(
      screen.getByText("You're 25. Your date of birth can't be changed."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Date of birth")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(nav.push).toHaveBeenCalledWith("/onboarding/looking-for");
  });

  it("has no back arrow: behind it is sign-in (D-080)", () => {
    renderUi(<BirthdayStep me={me()} />);
    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Back" })).toBeNull();
  });
});

describe("gender, once (D-008)", () => {
  it("saves the choice and moves on", async () => {
    const api_ = fakeApi({
      "POST /v1/me/gender": () =>
        json(200, me({ onboarding_step: "seeking", gender: "female" })),
    });
    renderUi(<GenderStep me={me({ onboarding_step: "gender" })} />);

    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: /Woman/ }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/looking-for"),
    );
    expect(api_.calls[0]?.body).toEqual({ gender: "female" });
  });

  it("shows an answered gender read-only, with no back arrow", () => {
    renderUi(
      <GenderStep me={me({ onboarding_step: "seeking", gender: "male" })} />,
    );

    expect(
      screen.getByText("You signed up as a man. This can't be changed."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();
  });
});

describe("who they're here to meet (T-3.6, D-041)", () => {
  const INTENTS = Array.from({ length: 10 }, (_, i) => ({
    id: i + 1,
    slug: `i${i + 1}`,
    label: `database label ${i + 1}`,
  }));

  it("takes one seeking and 1 to 3 intents, in en.ts's words", async () => {
    const api_ = fakeApi({
      "GET /v1/intents": () => json(200, INTENTS),
      "POST /v1/me/seeking": () =>
        json(200, me({ onboarding_step: "profile" })),
    });
    renderUi(
      <LookingForStep
        me={me({ onboarding_step: "seeking", gender: "male" })}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Women" }));
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    for (const label of [
      "Something serious",
      "Long term",
      "Situationship",
      "Friendship",
    ]) {
      await userEvent.click(await screen.findByRole("button", { name: label }));
    }
    expect(screen.getByRole("button", { name: "Friendship" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.queryByText(/database label/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/name"),
    );
    expect(api_.calls.find((c) => c.method === "POST")?.body).toEqual({
      seeking: "women",
      intent_ids: [1, 2, 3],
    });
  });

  it("has no back arrow: behind it is a gender that can't change (D-080)", () => {
    fakeApi({ "GET /v1/intents": () => json(200, INTENTS) });
    renderUi(<LookingForStep me={me({ onboarding_step: "seeking" })} />);
    expect(screen.queryByRole("link", { name: "Back" })).toBeNull();
  });
});

describe("name and places (T-3.7)", () => {
  async function fill(first: string) {
    await userEvent.type(screen.getByLabelText("First name"), first);
    await userEvent.type(
      screen.getByLabelText("Hometown, where you're from"),
      "Amritsar",
    );
    await userEvent.type(
      screen.getByLabelText("Where you live now"),
      "Phagwara",
    );
  }

  it("leaves what counts as a letter to the server, and shows its answer (D-082)", async () => {
    const api_ = fakeApi({
      "PATCH /v1/me/profile": () =>
        envelope(400, "VALIDATION_ERROR", {
          fields: [{ field: "first_name", problem: "can only hold letters" }],
        }),
    });
    renderUi(<NameStep me={me({ onboarding_step: "profile" })} />);

    await fill("R2D2");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await screen.findByText("Use letters only, with single spaces.");
    expect(api_.calls[0]?.body).toEqual({
      first_name: "R2D2",
      hometown: "Amritsar",
      city: "Phagwara",
    });
  });

  it("goes on to the location question while none is set (D-220)", async () => {
    fakeApi({
      "PATCH /v1/me/profile": () =>
        json(200, me({ onboarding_step: "username" }, { location: "none" })),
    });
    renderUi(<NameStep me={me({ onboarding_step: "profile" })} />);

    await fill("Rohit");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/location"),
    );
  });

  it("goes back to the editable step before it", () => {
    renderUi(<NameStep me={me({ onboarding_step: "profile" })} />);
    expect(screen.getByRole("link", { name: "Back" })).toHaveAttribute(
      "href",
      "/onboarding/looking-for",
    );
  });
});

describe("the username (T-3.7)", () => {
  it("goes back to the location question (D-220)", () => {
    renderUi(
      <UsernameStep me={me({ onboarding_step: "username" })} host="h" />,
    );
    expect(screen.getByRole("link", { name: "Back" })).toHaveAttribute(
      "href",
      "/onboarding/location",
    );
  });

  it("asks the server once typing settles, and shows the page on this site's host", async () => {
    const api_ = fakeApi({
      "GET /v1/usernames/rohit_a/available": () =>
        json(200, { available: true }),
      "PUT /v1/me/username": () => json(200, me({ onboarding_step: "about" })),
    });
    renderUi(
      <UsernameStep
        me={me({ onboarding_step: "username" })}
        host="staging.veloraapp.co.in"
      />,
    );

    await userEvent.type(screen.getByLabelText("Username"), "Rohit_A");

    expect(await screen.findByText("That one's free.")).toBeInTheDocument();
    expect(
      screen.getByText("Your page: staging.veloraapp.co.in/@rohit_a"),
    ).toBeInTheDocument();
    expect(api_.sent().filter((s) => s.startsWith("GET"))).toEqual([
      "GET /v1/usernames/rohit_a/available",
    ]);
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/about"),
    );
    expect(api_.calls.at(-1)?.body).toEqual({ username: "rohit_a" });
  });

  it("asks the server about a reserved name too: the list is the server's (D-082)", async () => {
    const api_ = fakeApi({
      "GET /v1/usernames/admin/available": () =>
        json(200, { available: false }),
    });
    renderUi(
      <UsernameStep me={me({ onboarding_step: "username" })} host="h" />,
    );

    await userEvent.type(screen.getByLabelText("Username"), "admin");

    expect(await screen.findByText("That one's taken.")).toBeInTheDocument();
    expect(api_.sent()).toEqual(["GET /v1/usernames/admin/available"]);
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });

  it("offers the server's suggestion", async () => {
    fakeApi({
      "GET /v1/usernames/rohit/available": () =>
        json(200, { available: false, suggestion: "rohit42" }),
      "GET /v1/usernames/rohit42/available": () =>
        json(200, { available: true }),
    });
    renderUi(
      <UsernameStep me={me({ onboarding_step: "username" })} host="h" />,
    );

    await userEvent.type(screen.getByLabelText("Username"), "rohit");
    await userEvent.click(
      await screen.findByRole("button", { name: "Try rohit42" }),
    );

    expect(screen.getByLabelText("Username")).toHaveValue("rohit42");
    expect(await screen.findByText("That one's free.")).toBeInTheDocument();
  });

  it("shows USERNAME_TAKEN, the race the check can't win, beside the field", async () => {
    fakeApi({
      "GET /v1/usernames/rohit_a/available": () =>
        json(200, { available: true }),
      "PUT /v1/me/username": () => envelope(409, "USERNAME_TAKEN"),
    });
    renderUi(
      <UsernameStep me={me({ onboarding_step: "username" })} host="h" />,
    );

    await userEvent.type(screen.getByLabelText("Username"), "rohit_a");
    await screen.findByText("That one's free.");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(
      await screen.findByText("That username is taken."),
    ).toBeInTheDocument();
  });

  it("waits 400 ms", () => {
    expect(USERNAME_CHECK_DELAY_MS).toBe(400);
  });
});

describe("about (T-3.12, T-3.7)", () => {
  const LONG = "  Weekend trekker, filter coffee loyalist, and slow reader.  ";

  it("counts down to 40 characters, then sends the text trimmed", async () => {
    const api_ = fakeApi({
      "PATCH /v1/me/profile": () =>
        json(200, me({ onboarding_step: "photos" })),
    });
    renderUi(<AboutStep me={me({ onboarding_step: "about" })} />);

    await userEvent.type(screen.getByLabelText("About you"), "Short one.");
    expect(
      screen.getByRole("button", { name: "30 more characters" }),
    ).toBeDisabled();

    await userEvent.clear(screen.getByLabelText("About you"));
    await userEvent.type(screen.getByLabelText("About you"), LONG);
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/photos"),
    );
    expect(api_.calls[0]?.body).toEqual({ about: LONG.trim() });
  });

  it("leaves links and phone numbers to the server, and shows its refusal (D-082)", async () => {
    const api_ = fakeApi({
      "PATCH /v1/me/profile": () =>
        envelope(400, "VALIDATION_ERROR", {
          fields: [{ field: "about", problem: "can't hold a phone number" }],
        }),
    });
    renderUi(<AboutStep me={me({ onboarding_step: "about" })} />);
    const about = "Call me on 98765 43210 any evening after work, I promise.";

    await userEvent.type(screen.getByLabelText("About you"), about);
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(
      await screen.findByText("Leave out links and phone numbers."),
    ).toBeInTheDocument();
    expect(api_.calls[0]?.body).toEqual({ about });
  });

  it("goes back to the username", () => {
    renderUi(<AboutStep me={me({ onboarding_step: "about" })} />);
    expect(screen.getByRole("link", { name: "Back" })).toHaveAttribute(
      "href",
      "/onboarding/username",
    );
  });
});

describe("interests (T-3.12, T-3.8)", () => {
  const INTERESTS = Array.from({ length: 24 }, (_, i) => ({
    id: i + 1,
    slug: `i${i + 1}`,
    label: `database label ${i + 1}`,
  }));

  it("takes exactly five, in en.ts's words", async () => {
    const api_ = fakeApi({
      "GET /v1/interests": () => json(200, INTERESTS),
      "PUT /v1/me/interests": () => json(200, me({ onboarding_step: "pin" })),
    });
    renderUi(<InterestsStep me={me({ onboarding_step: "interests" })} />);

    for (const label of [
      "Filter coffee",
      "Trekking",
      "Indie music",
      "Pottery",
    ]) {
      await userEvent.click(await screen.findByRole("button", { name: label }));
    }
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Dogs" }));
    await userEvent.click(screen.getByRole("button", { name: "Cats" }));
    expect(screen.getByRole("button", { name: "Cats" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByText("Pick 5. 5/5 chosen.")).toBeInTheDocument();
    expect(screen.queryByText(/database label/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/pin"),
    );
    expect(api_.calls.find((c) => c.method === "PUT")?.body).toEqual({
      interest_ids: [1, 2, 3, 4, 5],
    });
  });

  it("goes back to photos", () => {
    fakeApi({ "GET /v1/interests": () => json(200, INTERESTS) });
    renderUi(<InterestsStep me={me({ onboarding_step: "interests" })} />);
    expect(screen.getByRole("link", { name: "Back" })).toHaveAttribute(
      "href",
      "/onboarding/photos",
    );
  });
});

describe("the PIN (T-3.12, D-069)", () => {
  async function enter(pin: string) {
    for (const digit of pin) {
      await userEvent.click(screen.getByRole("button", { name: digit }));
    }
  }

  it("says when it will be asked: on open, and after 5 minutes away (T-3.10)", () => {
    renderUi(<PinStep me={me({ onboarding_step: "pin" })} />);

    expect(
      screen.getByText(
        "You'll enter it when you open Velora, and when you come back after 5 minutes away.",
      ),
    ).toBeInTheDocument();
  });

  it("asks twice, and starts again when the two don't match, sending nothing", async () => {
    const api_ = fakeApi({});
    renderUi(<PinStep me={me({ onboarding_step: "pin" })} />);

    await enter("4829");
    expect(
      screen.getByRole("heading", { name: "Confirm your PIN" }),
    ).toBeInTheDocument();
    await enter("4828");

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Those PINs didn't match. Try again.",
    );
    expect(
      screen.getByRole("heading", { name: "Set a 4-digit PIN" }),
    ).toBeInTheDocument();
    expect(api_.calls).toHaveLength(0);
  });

  it("sends a confirmed PIN, then reads Me afresh to move on", async () => {
    const api_ = fakeApi({
      "POST /v1/auth/pin/set": () => json(204),
      "GET /v1/me": () =>
        json(200, me({ onboarding_step: "selfie", has_pin: true })),
    });
    renderUi(<PinStep me={me({ onboarding_step: "pin" })} />);
    // As in the app: the gate has the pre-PIN Me cached, still at `pin`.
    client.setQueryData(queryKeys.me(), me({ onboarding_step: "pin" }));

    await enter("4829");
    await enter("4829");

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/selfie"),
    );
    expect(api_.sent()).toEqual(["POST /v1/auth/pin/set", "GET /v1/me"]);
    expect(api_.calls[0]?.body).toEqual({ pin: "4829" });
  });

  it("sends even an easy PIN: the list is the server's, and its refusal comes back (D-082)", async () => {
    const api_ = fakeApi({
      "POST /v1/auth/pin/set": () =>
        envelope(400, "VALIDATION_ERROR", {
          fields: [{ field: "pin", problem: "is too common" }],
        }),
    });
    renderUi(<PinStep me={me({ onboarding_step: "pin" })} />);

    await enter("1234");
    await enter("1234");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That PIN is too easy to guess. Pick another.",
    );
    expect(
      screen.getByRole("heading", { name: "Set a 4-digit PIN" }),
    ).toBeInTheDocument();
    expect(api_.calls[0]?.body).toEqual({ pin: "1234" });
  });

  it("can be skipped", async () => {
    const api_ = fakeApi({
      "POST /v1/me/pin/skip": () =>
        json(200, me({ onboarding_step: "selfie" })),
    });
    renderUi(<PinStep me={me({ onboarding_step: "pin" })} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Skip, I'll set it later" }),
    );

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/selfie"),
    );
    expect(api_.sent()).toEqual(["POST /v1/me/pin/skip"]);
  });

  it("doesn't change a PIN already set: that needs the current one", () => {
    renderUi(<PinStep me={me({ onboarding_step: "selfie", has_pin: true })} />);
    expect(screen.getByText("Your PIN is set.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "1" })).toBeNull();
  });
});

describe("production's CSP allows no inline style (P-41)", () => {
  it("no screen renders a style attribute", async () => {
    fakeApi({
      "GET /v1/me/photos": () =>
        json(200, [
          {
            id: "p1",
            kind: "public",
            position: 0,
            status: "approved",
            reject_reason: null,
            url: "https://cdn.test/p/p1.jpg",
          },
        ]),
      "GET /v1/verification/latest": () => envelope(404, "NOT_FOUND"),
    });
    const screens = [
      <SignIn key="s" />,
      <BirthdayStep key="b" me={me()} />,
      <GenderStep key="g" me={me({ onboarding_step: "gender" })} />,
      <LookingForStep key="l" me={me({ onboarding_step: "seeking" })} />,
      <NameStep key="n" me={me({ onboarding_step: "profile" })} />,
      <LocationStep key="loc" me={me({ onboarding_step: "username" })} />,
      <UsernameStep
        key="u"
        me={me({ onboarding_step: "username" })}
        host="h"
      />,
      <AboutStep key="a" me={me({ onboarding_step: "about" })} />,
      <PhotosStep key="p" me={me({ onboarding_step: "photos" })} />,
      <InterestsStep key="i" me={me({ onboarding_step: "interests" })} />,
      <PinStep key="pin" me={me({ onboarding_step: "pin" })} />,
      <SelfieStep key="selfie" me={me({ onboarding_step: "selfie" })} />,
    ];
    for (const ui of screens) {
      const { container, unmount } = renderUi(ui);
      if (ui.key === "p") await screen.findByRole("list");
      if (ui.key === "selfie")
        await screen.findByRole("button", { name: "Open camera" });
      expect(container.querySelector("[style]")).toBeNull();
      unmount();
    }
  });
});
