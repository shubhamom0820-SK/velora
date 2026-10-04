import { afterEach, describe, expect, it, vi } from "vitest";

import { fakeXhr } from "./testing/fakeXhr";
import { putToStorage, UploadError } from "./upload";

const URL_ = "https://storage.test/velora-private/raw/u1/p1?X-Amz-Signature=s";
const SIGNED = { "Content-Type": "image/jpeg" };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("putToStorage (T-4.6)", () => {
  it("PUTs the body to the URL with exactly the signed headers and no credentials", async () => {
    const xhr = fakeXhr();
    const body = new Blob(["jpeg bytes"], { type: "image/jpeg" });

    const done = putToStorage(URL_, body, SIGNED);
    xhr.last().respond(200);
    await done;

    const sent = xhr.last();
    expect(sent.method).toBe("PUT");
    expect(sent.url).toBe(URL_);
    expect(sent.headers).toEqual(SIGNED);
    expect(sent.withCredentials).toBe(false);
    expect(sent.body).toBe(body);
  });

  it("reports progress as whole percentages, then 100 once stored", async () => {
    const xhr = fakeXhr();
    const seen: number[] = [];

    const done = putToStorage(URL_, new Blob(["x"]), SIGNED, {
      onProgress: (percent) => seen.push(percent),
    });
    xhr.last().progress(0, 1000);
    xhr.last().progress(333, 1000);
    xhr.last().progress(1000, 1000);
    xhr.last().respond(200);
    await done;

    expect(seen).toEqual([0, 33, 100, 100]);
  });

  it("ignores progress the browser can't measure", async () => {
    const xhr = fakeXhr();
    const seen: number[] = [];

    const done = putToStorage(URL_, new Blob(["x"]), SIGNED, {
      onProgress: (percent) => seen.push(percent),
    });
    xhr.last().progress(10, 0, false);
    xhr.last().respond(204);
    await done;

    expect(seen).toEqual([100]);
  });

  it("rejects with storage's status when it refuses", async () => {
    const xhr = fakeXhr();

    const done = putToStorage(URL_, new Blob(["x"]), SIGNED);
    xhr.last().respond(403);

    const error = await done.catch((e: unknown) => e);
    expect(error).toBeInstanceOf(UploadError);
    expect(error).toMatchObject({ failure: "refused", status: 403 });
  });

  it("rejects as a network failure when nothing answers: a CORS or CSP refusal looks the same", async () => {
    const xhr = fakeXhr();

    const done = putToStorage(URL_, new Blob(["x"]), SIGNED);
    xhr.last().fail();

    await expect(done).rejects.toMatchObject({
      failure: "network",
      status: null,
    });
  });

  it("aborts the request when its signal does", async () => {
    const xhr = fakeXhr();
    const controller = new AbortController();

    const done = putToStorage(URL_, new Blob(["x"]), SIGNED, {
      signal: controller.signal,
    });
    controller.abort();

    await expect(done).rejects.toMatchObject({ failure: "aborted" });
    expect(xhr.last().aborted).toBe(true);
  });

  it("never starts when its signal has already aborted", async () => {
    const xhr = fakeXhr();
    const controller = new AbortController();
    controller.abort();

    await expect(
      putToStorage(URL_, new Blob(["x"]), SIGNED, {
        signal: controller.signal,
      }),
    ).rejects.toMatchObject({ failure: "aborted" });
    expect(xhr.requests).toHaveLength(0);
  });
});
