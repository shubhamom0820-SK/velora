import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SELFIE_CONSTRAINTS } from "@/lib/camera";
import type { Me } from "@/lib/queries/me";
import {
  VERIFICATION_POLL_FOR_MS,
  VERIFICATION_POLL_MS,
  type Verification,
} from "@/lib/queries/verification";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";
import { fakeXhr } from "@/lib/testing/fakeXhr";
import { resetSession } from "@/store/session";

import { SelfieStep } from "./SelfieStep";
import { COMPARING_LONG_MS } from "./useSelfie";

const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: nav.push,
    replace: nav.replace,
    prefetch: vi.fn(),
  }),
  usePathname: () => "/onboarding/selfie",
}));

// The toast lives in the root layout; here, what the step asks it to show.
const toast = vi.hoisted(() => ({ show: vi.fn(), dismiss: vi.fn() }));
vi.mock("@/components/ui/useToast", () => ({ useToast: () => toast }));

// jsdom draws nothing: taking a frame is camera.test.ts's. Here it hands back
// a JPEG once the camera has shown one.
vi.mock("@/lib/camera", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/camera")>()),
  captureFrame: vi.fn(async () => new Blob(["selfie"], { type: "image/jpeg" })),
}));

const PUT_URL =
  "http://127.0.0.1:9000/velora-private/raw/u1/s1?X-Amz-Signature=sig";
const SIGNED = { "Content-Type": "image/jpeg" };
const PREVIEW = "blob:http://127.0.0.1:3000/selfie";

function me(overrides: Partial<Me> = {}): Me {
  return {
    id: "u1",
    role: "user",
    status: "active",
    onboarding_step: "selfie",
    gender: "female",
    age: 24,
    is_verified: false,
    has_pin: true,
    referral_code: "ABCDEFGH",
    balance: 0,
    profile: {},
    ...overrides,
  } as Me;
}

function verification(overrides: Partial<Verification> = {}): Verification {
  return {
    id: "v1",
    status: "pending",
    submitted: false,
    reject_reason: null,
    attempts_left: 5,
    ...overrides,
  };
}

const NONE: Route = () => envelope(404, "NOT_FOUND");
const COMPLETE = "POST /v1/me/onboarding/complete";

/** `GET /verification/latest` answering each in turn, the last for good. */
function latests(...answers: (Verification | null)[]): Route {
  let n = 0;
  return () => {
    const answer = answers[Math.min(n++, answers.length - 1)];
    return answer ? json(200, answer) : envelope(404, "NOT_FOUND");
  };
}

/** The whole way through: start, upload, complete, submit. */
function sendingRoutes(): Record<string, Route> {
  return {
    "POST /v1/verification/start": () => json(200, verification()),
    "POST /v1/photos/upload-url": () =>
      json(200, { photo_id: "s1", put_url: PUT_URL, headers: SIGNED }),
    "POST /v1/photos/s1/complete": () =>
      json(200, {
        id: "s1",
        kind: "selfie",
        position: null,
        status: "pending",
        reject_reason: null,
        url: null,
      }),
    "POST /v1/verification/v1/submit": () =>
      json(200, verification({ submitted: true, attempts_left: 4 })),
  };
}

let client: QueryClient;

function renderStep(person: Me = me()) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["me"], person);
  return render(
    <QueryClientProvider client={client}>
      <SelfieStep me={person} />
    </QueryClientProvider>,
  );
}

type Camera = {
  getUserMedia: ReturnType<typeof vi.fn>;
  /** Each stream's stop, in the order opened. */
  stops: ReturnType<typeof vi.fn>[];
};

/** A front camera that opens, or refuses with `refusal`'s name. */
function fakeCamera(refusal?: string): Camera {
  const stops: ReturnType<typeof vi.fn>[] = [];
  const getUserMedia = vi.fn(async () => {
    if (refusal) throw new DOMException("refused", refusal);
    const stop = vi.fn();
    stops.push(stop);
    return { getTracks: () => [{ stop }] } as unknown as MediaStream;
  });
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia },
    configurable: true,
  });
  return { getUserMedia, stops };
}

function userAgent(value: string) {
  vi.spyOn(navigator, "userAgent", "get").mockReturnValue(value);
}

/** Open the camera, and let it show its first frame. */
async function openCamera() {
  await userEvent.click(
    await screen.findByRole("button", { name: "Open camera" }),
  );
  const video = await screen.findByLabelText("Your camera");
  fireEvent.loadedData(video);
  return video;
}

async function takeSelfie() {
  await openCamera();
  await userEvent.click(screen.getByRole("button", { name: "Take selfie" }));
  await screen.findByRole("button", { name: "Use this selfie" });
}

const calls = (api: ReturnType<typeof fakeApi>, route: string) =>
  api.sent().filter((sent) => sent === route).length;

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  nav.push.mockReset();
  toast.show.mockReset();
  URL.createObjectURL = vi.fn(() => PREVIEW);
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  Reflect.deleteProperty(navigator, "mediaDevices");
  resetSession();
});

describe("loading, empty and error (CLAUDE.md rule 14)", () => {
  it("shows a placeholder while the latest verification loads", () => {
    fakeApi({ "GET /v1/verification/latest": () => new Promise(() => {}) });
    const { container } = renderStep();

    expect(container.querySelector("[aria-busy]")).not.toBeNull();
    expect(screen.queryByRole("button", { name: "Open camera" })).toBeNull();
  });

  it("with none yet: says what happens to the selfie, and offers the camera", async () => {
    fakeApi({ "GET /v1/verification/latest": NONE });
    renderStep();

    expect(
      await screen.findByRole("button", { name: "Open camera" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("We'll open your front camera"),
    ).toBeInTheDocument();
    // /privacy's words (D-262, D-264): our team may look.
    expect(
      screen.getByText(/Our team may look at it to check a comparison\./),
    ).toBeInTheDocument();
  });

  it("says so when the latest can't be read, and asks again", async () => {
    let n = 0;
    fakeApi({
      "GET /v1/verification/latest": () =>
        n++ === 0 ? envelope(500, "INTERNAL") : envelope(404, "NOT_FOUND"),
    });
    renderStep();

    expect(
      await screen.findByText("We couldn't load your selfie check."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("button", { name: "Open camera" }),
    ).toBeInTheDocument();
  });
});

describe("who may skip it (D-008)", () => {
  it("a woman can't: there's no way past it but a matched selfie", async () => {
    fakeApi({ "GET /v1/verification/latest": NONE });
    renderStep(me({ gender: "female" }));

    await screen.findByRole("button", { name: "Open camera" });
    expect(screen.queryByRole("button", { name: "Skip for now" })).toBeNull();
    expect(
      screen.getByText(/^Needed before your profile goes live\./),
    ).toBeInTheDocument();
  });

  it("a man can: the server finishes sign-up, and he goes to the app (T-4.8)", async () => {
    const api = fakeApi({
      "GET /v1/verification/latest": NONE,
      [COMPLETE]: () =>
        json(200, me({ gender: "male", onboarding_step: "done" })),
    });
    renderStep(me({ gender: "male" }));

    expect(screen.getByText(/^Optional\./)).toBeInTheDocument();
    await userEvent.click(
      await screen.findByRole("button", { name: "Skip for now" }),
    );

    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/discover"));
    expect(api.sent()).toEqual(["GET /v1/verification/latest", COMPLETE]);
    expect(client.getQueryData<Me>(["me"])?.onboarding_step).toBe("done");
  });

  it("a new man is told of his welcome Velas, the number the server's (T-8.11)", async () => {
    fakeApi({
      "GET /v1/verification/latest": NONE,
      [COMPLETE]: () =>
        json(200, me({ gender: "male", onboarding_step: "done", balance: 5 })),
    });
    renderStep(me({ gender: "male" }));

    await userEvent.click(
      await screen.findByRole("button", { name: "Skip for now" }),
    );

    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/discover"));
    expect(toast.show).toHaveBeenCalledExactlyOnceWith({
      message: "5 Velas are in your wallet, to start you off.",
    });
  });

  it("one Vela is one, in the singular", async () => {
    fakeApi({
      "GET /v1/verification/latest": NONE,
      [COMPLETE]: () =>
        json(200, me({ gender: "male", onboarding_step: "done", balance: 1 })),
    });
    renderStep(me({ gender: "male" }));

    await userEvent.click(
      await screen.findByRole("button", { name: "Skip for now" }),
    );

    await waitFor(() =>
      expect(toast.show).toHaveBeenCalledExactlyOnceWith({
        message: "1 Vela is in your wallet, to start you off.",
      }),
    );
  });

  it("a number that had its welcome finishes with no toast (P-371)", async () => {
    fakeApi({
      "GET /v1/verification/latest": NONE,
      [COMPLETE]: () =>
        json(200, me({ gender: "male", onboarding_step: "done", balance: 0 })),
    });
    renderStep(me({ gender: "male" }));

    await userEvent.click(
      await screen.findByRole("button", { name: "Skip for now" }),
    );

    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/discover"));
    expect(toast.show).not.toHaveBeenCalled();
  });

  it("can skip after a rejection too", async () => {
    fakeApi({
      "GET /v1/verification/latest": latests(
        verification({
          status: "rejected",
          reject_reason: "no_match",
          submitted: true,
        }),
      ),
    });
    renderStep(me({ gender: "male" }));

    expect(
      await screen.findByRole("button", { name: "Skip for now" }),
    ).toBeInTheDocument();
  });
});

describe("the words claim the comparison only (D-262)", () => {
  it("says the selfie is compared with the face photo (D-391), and never 'verified'", async () => {
    fakeApi({ "GET /v1/verification/latest": NONE });
    const { container } = renderStep();
    await screen.findByRole("button", { name: "Open camera" });

    expect(container.textContent).toMatch(
      /We compare your selfie with your face photo\./,
    );
    expect(container.textContent).not.toMatch(
      /your photos|photos on your profile/,
    );
    expect(container.textContent).not.toMatch(/verif|real person|live person/i);
  });
});

describe("the camera (T-4.7)", () => {
  it("starts the verification, then opens the front camera, mirrored, and can take a picture once it shows one", async () => {
    const camera = fakeCamera();
    const api = fakeApi({
      "GET /v1/verification/latest": NONE,
      ...sendingRoutes(),
    });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Open camera" }),
    );
    const video = await screen.findByLabelText("Your camera");

    expect(api.sent()).toContain("POST /v1/verification/start");
    expect(camera.getUserMedia).toHaveBeenCalledWith(SELFIE_CONSTRAINTS);
    expect(video).toHaveClass("-scale-x-100");
    expect(screen.getByRole("button", { name: "Take selfie" })).toBeDisabled();
    expect(screen.getByText("Opening your camera…")).toBeInTheDocument();

    fireEvent.loadedData(video);

    expect(screen.getByRole("button", { name: "Take selfie" })).toBeEnabled();
    expect(
      screen.getByText(
        "Face the camera in good light, with your whole face in the frame.",
      ),
    ).toBeInTheDocument();
  });

  it("switches the camera off on cancel", async () => {
    const camera = fakeCamera();
    fakeApi({ "GET /v1/verification/latest": NONE, ...sendingRoutes() });
    renderStep();
    await openCamera();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(camera.stops[0]).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("button", { name: "Open camera" }),
    ).toBeInTheDocument();
  });

  it("switches the camera off when the page goes", async () => {
    const camera = fakeCamera();
    fakeApi({ "GET /v1/verification/latest": NONE, ...sendingRoutes() });
    const { unmount } = renderStep();
    await openCamera();

    unmount();

    expect(camera.stops[0]).toHaveBeenCalledOnce();
  });

  it("switches the camera off once the picture is taken", async () => {
    const camera = fakeCamera();
    fakeApi({ "GET /v1/verification/latest": NONE, ...sendingRoutes() });
    renderStep();

    await takeSelfie();

    expect(camera.stops[0]).toHaveBeenCalledOnce();
    expect(screen.queryByLabelText("Your camera")).toBeNull();
  });

  it.each([
    [
      "Chrome on Android",
      "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
      /Tap ⋮ to the right of the address bar, then Settings, Site settings and Camera\. Find localhost:3000 under Blocked/,
    ],
    [
      "Safari on an iPhone",
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1",
      /In Safari, tap aA in the address bar, then Website Settings, and set Camera to Allow\./,
    ],
    [
      "Chrome on a computer",
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
      /Privacy and security, Site settings and Camera\. Under "Not allowed to use your camera", choose localhost:3000/,
    ],
    [
      "Safari on a Mac",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
      /Choose Safari > Settings, click Websites, then Camera, and set localhost:3000 to Allow\./,
    ],
    [
      "Firefox",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:143.0) Gecko/20100101 Firefox/143.0",
      /Click the permissions icon at the left of the address bar/,
    ],
    [
      "anything else",
      "SomeBrowser/1.0",
      /Allow the camera for localhost:3000 in your browser's settings/,
    ],
  ])(
    "when it's blocked, says where %s allows it, then tries again",
    async (_name, agent, how) => {
      userAgent(agent);
      const camera = fakeCamera("NotAllowedError");
      fakeApi({ "GET /v1/verification/latest": NONE, ...sendingRoutes() });
      renderStep();

      await userEvent.click(
        await screen.findByRole("button", { name: "Open camera" }),
      );

      expect(await screen.findByRole("alert")).toHaveTextContent(
        /^Your camera is blocked for /,
      );
      expect(screen.getByText(how)).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Try again" }));
      await waitFor(() => expect(camera.getUserMedia).toHaveBeenCalledTimes(2));
    },
  );

  it.each([
    ["NotFoundError", "We couldn't find a camera."],
    ["NotReadableError", "Your camera is in use by another app."],
    ["TypeError", "Your camera didn't open. Try again."],
  ])("says what a %s means", async (name, said) => {
    fakeCamera(name);
    fakeApi({ "GET /v1/verification/latest": NONE, ...sendingRoutes() });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Open camera" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(said);
  });

  it("says so where the browser has no camera to give", async () => {
    fakeApi({ "GET /v1/verification/latest": NONE, ...sendingRoutes() });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Open camera" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /^This browser can't open a camera here\./,
    );
  });
});

describe("checking the picture before it's sent (T-4.7's plan, question 2)", () => {
  it("shows the picture, mirrored as it was seen, and sends nothing yet", async () => {
    fakeCamera();
    const api = fakeApi({
      "GET /v1/verification/latest": NONE,
      ...sendingRoutes(),
    });
    renderStep();

    await takeSelfie();

    const shot = screen.getByRole("img", { name: "Your selfie" });
    expect(shot).toHaveAttribute("src", PREVIEW);
    expect(shot).toHaveClass("-scale-x-100");
    expect(
      screen.getByText(/Each selfie you send uses one of today's tries\./),
    ).toBeInTheDocument();
    expect(calls(api, "POST /v1/photos/upload-url")).toBe(0);
  });

  it("retakes without sending, letting the picture go", async () => {
    const camera = fakeCamera();
    const api = fakeApi({
      "GET /v1/verification/latest": NONE,
      ...sendingRoutes(),
    });
    renderStep();
    await takeSelfie();

    await userEvent.click(screen.getByRole("button", { name: "Retake" }));

    expect(await screen.findByLabelText("Your camera")).toBeInTheDocument();
    expect(camera.getUserMedia).toHaveBeenCalledTimes(2);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(PREVIEW);
    expect(calls(api, "POST /v1/photos/upload-url")).toBe(0);
  });
});

describe("sending (T-4.2's flow, kind=selfie)", () => {
  it("asks for a selfie's URL, PUTs with exactly the signed headers and progress, completes, then submits", async () => {
    fakeCamera();
    const xhr = fakeXhr();
    const api = fakeApi({
      "GET /v1/verification/latest": latests(
        null,
        verification({ submitted: true, attempts_left: 4 }),
      ),
      ...sendingRoutes(),
    });
    renderStep();
    await takeSelfie();

    await userEvent.click(
      screen.getByRole("button", { name: "Use this selfie" }),
    );
    await waitFor(() => expect(xhr.requests).toHaveLength(1));

    const upload = api.calls.find(
      (call) => call.path === "/v1/photos/upload-url",
    );
    expect(upload?.body).toEqual({
      kind: "selfie",
      content_type: "image/jpeg",
    });
    const put = xhr.last();
    expect(put.method).toBe("PUT");
    expect(put.url).toBe(PUT_URL);
    expect(put.headers).toEqual(SIGNED);
    expect((put.body as Blob).type).toBe("image/jpeg");

    act(() => put.progress(40, 100));
    expect(screen.getByText("Sending your selfie… 40%")).toBeInTheDocument();
    act(() => put.respond(200));

    expect(
      await screen.findByText("Comparing your selfie with your face photo…"),
    ).toBeInTheDocument();
    const submit = api.calls.find(
      (call) => call.path === "/v1/verification/v1/submit",
    );
    expect(submit?.body).toEqual({ photo_id: "s1" });
    expect(api.sent()).toEqual([
      "GET /v1/verification/latest",
      "POST /v1/verification/start",
      "POST /v1/photos/upload-url",
      "POST /v1/photos/s1/complete",
      "POST /v1/verification/v1/submit",
    ]);
    // The selfie this page sent, shown while it's compared.
    expect(screen.getByRole("img", { name: "Your selfie" })).toHaveAttribute(
      "src",
      PREVIEW,
    );
  });

  it("says when it didn't get there, and sends the same picture again", async () => {
    const camera = fakeCamera();
    const xhr = fakeXhr();
    fakeApi({ "GET /v1/verification/latest": NONE, ...sendingRoutes() });
    renderStep();
    await takeSelfie();

    await userEvent.click(
      screen.getByRole("button", { name: "Use this selfie" }),
    );
    await waitFor(() => expect(xhr.requests).toHaveLength(1));
    act(() => xhr.last().fail());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your selfie didn't send — check your connection and try again.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(xhr.requests).toHaveLength(2));
    expect(xhr.requests[1]?.body).toBe(xhr.requests[0]?.body);
    expect(camera.getUserMedia).toHaveBeenCalledOnce();
  });

  it("says how long to wait when today's selfies are used up, before any camera opens (RATE_LIMITED)", async () => {
    const camera = fakeCamera();
    fakeApi({
      "GET /v1/verification/latest": NONE,
      "POST /v1/verification/start": () =>
        envelope(429, "RATE_LIMITED", { retry_after_s: 4.5 * 3600 }),
    });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Open camera" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You can't send another selfie yet. Try again in about 5 hours.",
    );
    expect(camera.getUserMedia).not.toHaveBeenCalled();
  });

  it("says minutes when the wait is under an hour", async () => {
    fakeCamera();
    fakeApi({
      "GET /v1/verification/latest": NONE,
      "POST /v1/verification/start": () =>
        envelope(429, "RATE_LIMITED", { retry_after_s: 125 }),
    });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Open camera" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Try again in about 3 minutes.",
    );
  });

  it("goes back to the start, with the wait, when the submit is refused as the day's sixth (RATE_LIMITED)", async () => {
    fakeCamera();
    const xhr = fakeXhr((request) => request.respond(200));
    fakeApi({
      "GET /v1/verification/latest": NONE,
      ...sendingRoutes(),
      "POST /v1/verification/v1/submit": () =>
        envelope(429, "RATE_LIMITED", { retry_after_s: 7200 }),
    });
    renderStep();
    await takeSelfie();

    await userEvent.click(
      screen.getByRole("button", { name: "Use this selfie" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Try again in about 2 hours.",
    );
    expect(xhr.requests).toHaveLength(1);
    expect(
      screen.getByRole("button", { name: "Open camera" }),
    ).toBeInTheDocument();
  });

  it("follows the latest when starting is refused because one is being compared already (NOT_ALLOWED)", async () => {
    const camera = fakeCamera();
    fakeApi({
      "GET /v1/verification/latest": latests(
        null,
        verification({ submitted: true }),
      ),
      "POST /v1/verification/start": () => envelope(422, "NOT_ALLOWED"),
    });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Open camera" }),
    );

    expect(
      await screen.findByText("Comparing your selfie with your face photo…"),
    ).toBeInTheDocument();
    expect(camera.getUserMedia).not.toHaveBeenCalled();
  });

  it("says something went wrong on any other failure to start", async () => {
    fakeCamera();
    fakeApi({
      "GET /v1/verification/latest": NONE,
      "POST /v1/verification/start": () => envelope(500, "INTERNAL"),
    });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Open camera" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
  });
});

describe("while it's compared (D-261): never a bare spinner", () => {
  const COMPARING = verification({ submitted: true, attempts_left: 4 });

  it("asks every 2 s, and says after about 15 s that it can take a minute and she can leave", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api = fakeApi({ "GET /v1/verification/latest": latests(COMPARING) });
    renderStep();

    expect(
      await screen.findByText("Comparing your selfie with your face photo…"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/This can take up to a minute/)).toBeNull();

    await vi.advanceTimersByTimeAsync(VERIFICATION_POLL_MS);
    await waitFor(() =>
      expect(calls(api, "GET /v1/verification/latest")).toBe(2),
    );
    await vi.advanceTimersByTimeAsync(COMPARING_LONG_MS);

    expect(
      await screen.findByText(
        "This can take up to a minute. You can leave this page — your result will be here when you come back.",
      ),
    ).toBeInTheDocument();
  });

  it("stops asking after a minute, says so, and asks again for another on 'Check again'", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api = fakeApi({ "GET /v1/verification/latest": latests(COMPARING) });
    renderStep();
    await screen.findByText("Comparing your selfie with your face photo…");

    await vi.advanceTimersByTimeAsync(VERIFICATION_POLL_FOR_MS + 100);
    expect(
      await screen.findByText(
        "Still comparing. Come back in a few minutes — your result will be waiting here.",
      ),
    ).toBeInTheDocument();
    const asked = calls(api, "GET /v1/verification/latest");
    expect(asked).toBeLessThanOrEqual(
      1 + VERIFICATION_POLL_FOR_MS / VERIFICATION_POLL_MS,
    );

    await vi.advanceTimersByTimeAsync(10 * VERIFICATION_POLL_MS);
    expect(calls(api, "GET /v1/verification/latest")).toBe(asked);

    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    await waitFor(() =>
      expect(calls(api, "GET /v1/verification/latest")).toBe(asked + 1),
    );
    await vi.advanceTimersByTimeAsync(VERIFICATION_POLL_MS);
    await waitFor(() =>
      expect(calls(api, "GET /v1/verification/latest")).toBeGreaterThanOrEqual(
        asked + 2,
      ),
    );
    expect(
      screen.getByText("Comparing your selfie with your face photo…"),
    ).toBeInTheDocument();
    // The second minute says from the start that she can leave.
    expect(screen.getByText(/You can leave this page/)).toBeInTheDocument();
  });

  it("picks up where it was when she comes back mid-comparison", async () => {
    fakeApi({ "GET /v1/verification/latest": latests(COMPARING) });
    renderStep();

    expect(
      await screen.findByText("Comparing your selfie with your face photo…"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open camera" })).toBeNull();
  });

  it("says a match plainly, reads Me afresh, and Continue finishes sign-up (T-4.8)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api = fakeApi({
      "GET /v1/verification/latest": latests(
        COMPARING,
        verification({ status: "approved", submitted: true }),
      ),
      "GET /v1/me": () => json(200, me({ is_verified: true })),
      [COMPLETE]: () =>
        json(200, me({ is_verified: true, onboarding_step: "done" })),
    });
    renderStep();
    await screen.findByText("Comparing your selfie with your face photo…");

    await vi.advanceTimersByTimeAsync(VERIFICATION_POLL_MS);

    expect(
      await screen.findByText("Your selfie matched your face photo."),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(client.getQueryState(["me"])?.isInvalidated).toBe(true),
    );
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/discover"));
    expect(calls(api, COMPLETE)).toBe(1);
  });

  it("shows a selfie matched before as matched, with no way to send another", async () => {
    fakeApi({ "GET /v1/verification/latest": NONE });
    renderStep(me({ is_verified: true }));

    expect(
      await screen.findByText("Your selfie matched your face photo."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open camera" })).toBeNull();
  });
});

describe("a rejection says what to change, and how many tries are left (D-263)", () => {
  it.each([
    [
      "no_face",
      "We couldn't find a face in your selfie. Face the camera in good light, with your whole face in the frame, and try again.",
    ],
    [
      "many_faces",
      "We found more than one face. Take your selfie with only you in the frame.",
    ],
    [
      "no_match",
      "Your selfie didn't match your face photo closely enough. Try again facing the camera in good light, or add a clearer face photo.",
    ],
    ["unreadable", "We couldn't read that picture. Take your selfie again."],
    [
      "unavailable",
      "We couldn't compare your selfie just now. Try again in a few minutes.",
    ],
    ["other", "We couldn't use this selfie. Try again."],
    ["anything_new", "We couldn't use this selfie. Try again."],
    [null, "We couldn't use this selfie. Try again."],
  ])("%s", async (reason, said) => {
    fakeApi({
      "GET /v1/verification/latest": latests(
        verification({
          status: "rejected",
          submitted: true,
          reject_reason: reason,
          attempts_left: 3,
        }),
      ),
    });
    renderStep();

    expect(await screen.findByRole("alert")).toHaveTextContent(said);
    expect(screen.getByText("3 tries left today.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Open camera" }),
    ).toBeInTheDocument();
  });

  it("no_photos: says to add one, with the way back to the photos", async () => {
    fakeApi({
      "GET /v1/verification/latest": latests(
        verification({
          status: "rejected",
          submitted: true,
          reject_reason: "no_photos",
        }),
      ),
    });
    renderStep();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your face photo isn't ready to compare with: it may still be being checked, or it was refused. Add one that shows your face clearly, then take your selfie.",
    );
    expect(
      screen.getByRole("link", { name: "Go to your photos" }),
    ).toHaveAttribute("href", "/onboarding/photos");
  });

  it.each([
    [1, "1 try left today."],
    [0, "No tries left today."],
  ])("with %i left: %s", async (left, said) => {
    fakeApi({
      "GET /v1/verification/latest": latests(
        verification({
          status: "rejected",
          submitted: true,
          reject_reason: "no_match",
          attempts_left: left,
        }),
      ),
    });
    renderStep();

    expect(await screen.findByText(said)).toBeInTheDocument();
  });
});

describe("the frame (T-3.11)", () => {
  it("is the selfie's place: the last of 13, back to the PIN", async () => {
    fakeApi({ "GET /v1/verification/latest": NONE });
    renderStep();

    expect(
      await screen.findByRole("heading", { name: "Quick selfie check" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "13",
    );
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuemax",
      "13",
    );
    expect(screen.getByRole("link", { name: "Back" })).toHaveAttribute(
      "href",
      "/onboarding/pin",
    );
  });
});

describe("finishing sign-up: the server says what's still needed (T-4.8, D-310)", () => {
  async function skipRefused(details: Record<string, unknown>) {
    const api = fakeApi({
      "GET /v1/verification/latest": NONE,
      [COMPLETE]: () => envelope(403, "PROFILE_INCOMPLETE", details),
    });
    renderStep(me({ gender: "male" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Skip for now" }),
    );
    return api;
  }

  it.each([
    [["location"], "Add your location first.", "/onboarding/location"],
    [
      ["seeking", "username"],
      "Say who you're looking for first.",
      "/onboarding/looking-for",
    ],
    [
      ["intents"],
      "Say who you're looking for first.",
      "/onboarding/looking-for",
    ],
    [
      ["first_name"],
      "Add your name, hometown and city first.",
      "/onboarding/name",
    ],
    [
      ["hometown"],
      "Add your name, hometown and city first.",
      "/onboarding/name",
    ],
    [["city"], "Add your name, hometown and city first.", "/onboarding/name"],
    [["username"], "Choose a username first.", "/onboarding/username"],
    [["interests"], "Pick your 5 interests first.", "/onboarding/interests"],
  ])(
    "names the first of %j, with the way back, and stays",
    async (missing, message, href) => {
      await skipRefused({ missing });

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(message);
      expect(
        screen.getByRole("link", { name: "Take me there" }),
      ).toHaveAttribute("href", href);
      expect(nav.push).not.toHaveBeenCalled();
      // Still here, and still able to try again.
      expect(
        screen.getByRole("button", { name: "Skip for now" }),
      ).toBeEnabled();
    },
  );

  it("a name it doesn't know reads as the general line, with nowhere to go", async () => {
    await skipRefused({ missing: ["height"] });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something on your profile isn't finished yet.",
    );
    expect(screen.queryByRole("link", { name: "Take me there" })).toBeNull();
  });

  it("a match the server doesn't know of: said, and Me and the latest read afresh", async () => {
    const api = fakeApi({
      "GET /v1/verification/latest": NONE,
      "GET /v1/me": () => json(200, me()),
      [COMPLETE]: () => envelope(403, "VERIFICATION_REQUIRED"),
    });
    renderStep(me({ is_verified: true }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Continue" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your selfie has to match your face photo before you can finish.",
    );
    await waitFor(() =>
      expect(calls(api, "GET /v1/verification/latest")).toBe(2),
    );
    expect(client.getQueryState(["me"])?.isInvalidated).toBe(true);
    expect(nav.push).not.toHaveBeenCalled();
  });

  it("anything else gets the shared wording, and the button works again", async () => {
    let n = 0;
    const api = fakeApi({
      "GET /v1/verification/latest": NONE,
      [COMPLETE]: () =>
        n++ === 0
          ? envelope(500, "INTERNAL")
          : json(200, me({ gender: "male", onboarding_step: "done" })),
    });
    renderStep(me({ gender: "male" }));
    const skip = await screen.findByRole("button", { name: "Skip for now" });
    await userEvent.click(skip);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
    await userEvent.click(skip);
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/discover"));
    expect(calls(api, COMPLETE)).toBe(2);
  });

  it("can't be asked twice at once", async () => {
    const api = fakeApi({
      "GET /v1/verification/latest": NONE,
      [COMPLETE]: () => new Promise(() => {}),
    });
    renderStep(me({ gender: "male" }));
    const skip = await screen.findByRole("button", { name: "Skip for now" });
    await userEvent.click(skip);

    await waitFor(() => expect(skip).toBeDisabled());
    await userEvent.click(skip);
    expect(calls(api, COMPLETE)).toBe(1);
  });
});
