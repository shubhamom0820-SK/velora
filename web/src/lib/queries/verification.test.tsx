import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";
import { fakeXhr } from "@/lib/testing/fakeXhr";
import { UploadError } from "@/lib/upload";
import { resetSession } from "@/store/session";

import { queryKeys } from "./keys";
import {
  isBeingCompared,
  useLatestVerification,
  useStartVerification,
  useSubmitSelfie,
  useUploadSelfie,
  type Verification,
} from "./verification";

const PUT_URL = "https://storage.test/velora-private/raw/u1/s1?sig=s";

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

let client: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const asked = (api: ReturnType<typeof fakeApi>) =>
  api.sent().filter((sent) => sent === "GET /v1/verification/latest").length;

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  resetSession();
});

describe("isBeingCompared", () => {
  it("is pending with a selfie attached, and nothing else", () => {
    expect(isBeingCompared(verification({ submitted: true }))).toBe(true);
    expect(isBeingCompared(verification())).toBe(false);
    expect(
      isBeingCompared(verification({ status: "approved", submitted: true })),
    ).toBe(false);
    expect(
      isBeingCompared(verification({ status: "rejected", submitted: true })),
    ).toBe(false);
    expect(isBeingCompared(null)).toBe(false);
  });
});

describe("useLatestVerification (GET /verification/latest)", () => {
  it("reads none (NOT_FOUND) as null, not an error", async () => {
    fakeApi({
      "GET /v1/verification/latest": () => envelope(404, "NOT_FOUND"),
    });
    const { result } = renderHook(() => useLatestVerification({ poll: true }), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it("is an error on anything else", async () => {
    fakeApi({ "GET /v1/verification/latest": () => envelope(500, "INTERNAL") });
    const { result } = renderHook(() => useLatestVerification({ poll: true }), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it.each([
    [
      "being compared, asked to poll",
      verification({ submitted: true }),
      true,
      4,
    ],
    [
      "being compared, told to stop",
      verification({ submitted: true }),
      false,
      1,
    ],
    ["waiting for its selfie", verification(), true, 1],
    ["decided", verification({ status: "approved", submitted: true }), true, 1],
  ])("asks every 2 s only while %s", async (_name, answer, poll, times) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api = fakeApi({
      "GET /v1/verification/latest": () => json(200, answer),
    });
    renderHook(() => useLatestVerification({ poll }), { wrapper });
    await waitFor(() => expect(asked(api)).toBe(1));

    // Six seconds, in the plan's own number (every 2 s), not the constant: a
    // slower poll would otherwise slow this test with it and pass.
    await act(() => vi.advanceTimersByTimeAsync(6_000));

    await waitFor(() => expect(asked(api)).toBe(times));
  });
});

describe("starting and submitting keep the latest in step", () => {
  it("start's answer is the latest", async () => {
    fakeApi({
      "POST /v1/verification/start": () => json(200, verification()),
    });
    const { result } = renderHook(() => useStartVerification(), { wrapper });

    await act(() => result.current.mutateAsync());

    expect(client.getQueryData(queryKeys.verificationLatest())).toEqual(
      verification(),
    );
  });

  it("submit sends the selfie's id, and its answer is the latest", async () => {
    const api = fakeApi({
      "POST /v1/verification/v1/submit": () =>
        json(200, verification({ submitted: true })),
    });
    const { result } = renderHook(() => useSubmitSelfie(), { wrapper });

    await act(() =>
      result.current.mutateAsync({ verificationId: "v1", photoId: "s1" }),
    );

    expect(api.calls[0]?.body).toEqual({ photo_id: "s1" });
    expect(client.getQueryData(queryKeys.verificationLatest())).toEqual(
      verification({ submitted: true }),
    );
  });
});

describe("useUploadSelfie (T-4.2's flow, kind=selfie)", () => {
  const routes = {
    "POST /v1/photos/upload-url": () =>
      json(200, {
        photo_id: "s1",
        put_url: PUT_URL,
        headers: { "Content-Type": "image/jpeg" },
      }),
    "POST /v1/photos/s1/complete": () =>
      json(200, {
        id: "s1",
        kind: "selfie",
        position: null,
        status: "pending",
        reject_reason: null,
        url: null,
      }),
  };

  it("asks for a selfie's URL with no place, PUTs it, then completes it", async () => {
    const xhr = fakeXhr((request) => request.respond(200));
    const api = fakeApi(routes);
    const { result } = renderHook(() => useUploadSelfie(), { wrapper });
    const body = new Blob(["selfie"], { type: "image/jpeg" });

    const photo = await act(() => result.current.mutateAsync({ body }));

    expect(api.calls[0]?.body).toEqual({
      kind: "selfie",
      content_type: "image/jpeg",
    });
    expect(xhr.last().url).toBe(PUT_URL);
    expect(xhr.last().body).toBe(body);
    expect(photo.id).toBe("s1");
    expect(api.sent()).toEqual([
      "POST /v1/photos/upload-url",
      "POST /v1/photos/s1/complete",
    ]);
  });

  it("deletes nothing when the PUT fails: the next upload replaces it (D-263)", async () => {
    fakeXhr((request) => request.fail());
    const api = fakeApi(routes);
    const { result } = renderHook(() => useUploadSelfie(), { wrapper });

    const failure = await act(() =>
      result.current
        .mutateAsync({ body: new Blob(["selfie"], { type: "image/jpeg" }) })
        .catch((error: unknown) => error),
    );

    expect(failure).toBeInstanceOf(UploadError);
    expect(api.sent()).toEqual(["POST /v1/photos/upload-url"]);
  });
});
