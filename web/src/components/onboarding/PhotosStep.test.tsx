import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Me } from "@/lib/queries/me";
import type { Photo } from "@/lib/queries/photos";
import { PHOTO_POLL_MS } from "@/lib/queries/photos";
import { envelope, fakeApi, json, type Route } from "@/lib/testing/fakeApi";
import { fakeXhr } from "@/lib/testing/fakeXhr";
import { resetSession } from "@/store/session";

import { PhotosStep } from "./PhotosStep";

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/onboarding/photos",
}));

// jsdom draws nothing: the resize is resize-image.test.ts's. Here it hands
// back a JPEG, or nothing for a file "the browser can't read".
const resize = vi.hoisted(() => ({
  next: "jpeg" as "jpeg" | "unreadable",
}));
vi.mock("@/lib/resize-image", () => ({
  resizeForUpload: vi.fn(async () =>
    resize.next === "jpeg"
      ? new Blob(["resized"], { type: "image/jpeg" })
      : null,
  ),
}));

const PUT_URL =
  "http://127.0.0.1:9000/velora-private/raw/u1/p1?X-Amz-Signature=sig";
const SIGNED = { "Content-Type": "image/jpeg" };

function me(overrides: Partial<Me> = {}): Me {
  return {
    id: "u1",
    role: "user",
    status: "active",
    onboarding_step: "photos",
    gender: "male",
    age: 27,
    is_verified: false,
    has_pin: false,
    referral_code: "ABCDEFGH",
    balance: 0,
    profile: {},
    ...overrides,
  } as Me;
}

function photo(overrides: Partial<Photo> = {}): Photo {
  return {
    id: "p1",
    kind: "public",
    position: 0,
    status: "approved",
    reject_reason: null,
    url: "https://cdn.test/p/p1.jpg",
    from_photo_id: null,
    ...overrides,
  };
}

/** The face photo (T-4.12): kind `verification`, no place, a signed link. */
function face(overrides: Partial<Photo> = {}): Photo {
  return photo({
    id: "f1",
    kind: "verification",
    position: null,
    url: "https://storage.test/velora-private/raw/u1/f1?sig=s",
    ...overrides,
  });
}

/** `GET /me/photos` answering each list in turn, the last one for good. */
function lists(...answers: Photo[][]): Route {
  let n = 0;
  return () => json(200, answers[Math.min(n++, answers.length - 1)]);
}

function renderStep(person: Me = me()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  client.setQueryData(["me"], person);
  return render(
    <QueryClientProvider client={client}>
      <PhotosStep me={person} />
    </QueryClientProvider>,
  );
}

function slot(n: number): HTMLElement {
  return screen.getByRole("listitem", { name: `Photo ${n}` });
}

/** What slot `n` says, once it says it: a slot's element can change with its state. */
async function slotAlert(n: number): Promise<HTMLElement> {
  return waitFor(() => within(slot(n)).getByRole("alert"));
}

/** Tap the first empty slot, then pick `file` in the picker it opened. */
async function pick(
  file = new File(["raw"], "me.jpg", { type: "image/jpeg" }),
) {
  const [empty] = await screen.findAllByRole("button", { name: "Add a photo" });
  await userEvent.click(empty as HTMLElement);
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("No file picker.");
  await userEvent.upload(input, file);
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  resize.next = "jpeg";
  nav.push.mockReset();
  URL.createObjectURL = vi.fn(() => "blob:http://127.0.0.1:3000/preview");
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  resetSession();
});

describe("loading, empty and error (CLAUDE.md rule 14)", () => {
  it("shows placeholders while the photos load", () => {
    fakeApi({ "GET /v1/me/photos": () => new Promise(() => undefined) });

    const { container } = renderStep();

    expect(container.querySelector("[aria-busy]")).not.toBeNull();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("with no photos: six empty slots and the face slot; a man may go on with none (D-392)", async () => {
    fakeApi({ "GET /v1/me/photos": () => json(200, []) });

    renderStep();

    expect(
      await screen.findAllByRole("button", { name: "Add a photo" }),
    ).toHaveLength(6);
    expect(
      screen.getByRole("button", { name: "Add your face photo" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Back" })).toHaveAttribute(
      "href",
      "/onboarding/about",
    );
  });

  it("a woman has no way on until her face photo is there, pending is enough (D-391)", async () => {
    fakeApi({ "GET /v1/me/photos": () => json(200, []) });
    const { unmount } = renderStep(me({ gender: "female" }));

    expect(
      await screen.findByText(/Needed for the selfie check/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add your face photo to continue" }),
    ).toBeDisabled();
    unmount();

    // Her face photo there, still being checked: enough to go on.
    fakeApi({
      "GET /v1/me/photos": () => json(200, [face({ status: "pending" })]),
    });
    renderStep(me({ gender: "female" }));
    expect(
      await screen.findByRole("button", { name: "Continue" }),
    ).toBeEnabled();
  });

  it("says so when the photos can't load, and tries again", async () => {
    const api_ = fakeApi({
      "GET /v1/me/photos": (() => {
        let n = 0;
        return () =>
          n++ === 0 ? envelope(500, "INTERNAL") : json(200, [photo()]);
      })(),
    });

    renderStep();
    await userEvent.click(
      await screen.findByRole("button", { name: "Try again" }),
    );

    expect(await screen.findByRole("list")).toBeInTheDocument();
    expect(api_.sent()).toEqual(["GET /v1/me/photos", "GET /v1/me/photos"]);
  });
});

describe("the picker (T-4.6)", () => {
  it("opens from an empty slot, for any image, never forcing the camera", async () => {
    fakeApi({ "GET /v1/me/photos": () => json(200, []) });
    renderStep();
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]');
    const click = vi.spyOn(input as HTMLInputElement, "click");

    await userEvent.click(
      (
        await screen.findAllByRole("button", { name: "Add a photo" })
      )[3] as HTMLElement,
    );

    expect(click).toHaveBeenCalledOnce();
    expect(input).toHaveAttribute("accept", "image/*");
    expect(input).not.toHaveAttribute("capture");
    expect(input).not.toHaveAttribute("multiple");
  });
});

describe("uploading (T-4.2's flow, from the browser)", () => {
  it("asks for a place, PUTs with exactly the signed headers and progress, then completes", async () => {
    const api_ = fakeApi({
      "GET /v1/me/photos": lists([], [photo({ status: "pending" })]),
      "POST /v1/photos/upload-url": () =>
        json(200, { photo_id: "p1", put_url: PUT_URL, headers: SIGNED }),
      "POST /v1/photos/p1/complete": () =>
        json(200, photo({ status: "pending" })),
      "GET /v1/me": () => json(200, me({ onboarding_step: "interests" })),
    });
    const xhr = fakeXhr();
    renderStep();
    await screen.findByRole("list");

    await pick();
    await waitFor(() => expect(xhr.requests).toHaveLength(1));
    xhr.last().progress(42, 100);

    await waitFor(() =>
      expect(within(slot(1)).getByText("Uploading 42%")).toBeInTheDocument(),
    );
    expect(
      within(slot(1)).getByRole("progressbar", { name: "Uploading 42%" }),
    ).toHaveAttribute("value", "42");

    xhr.last().progress(100, 100);
    await waitFor(() =>
      expect(within(slot(1)).getByText("Checking…")).toBeInTheDocument(),
    );
    xhr.last().respond(200);

    await waitFor(() =>
      expect(api_.sent()).toContain("POST /v1/photos/p1/complete"),
    );
    const put = xhr.last();
    expect([put.method, put.url, put.headers, put.withCredentials]).toEqual([
      "PUT",
      PUT_URL,
      SIGNED,
      false,
    ]);
    expect((put.body as Blob).type).toBe("image/jpeg");
    expect(
      api_.calls.find((c) => c.path === "/v1/photos/upload-url")?.body,
    ).toEqual({ kind: "public", position: 0, content_type: "image/jpeg" });
    // Uploaded and waiting for moderation: shown from this page's own preview.
    await waitFor(() =>
      expect(
        within(slot(1)).getByRole("img", { name: "Photo 1" }),
      ).toHaveAttribute("src", "blob:http://127.0.0.1:3000/preview"),
    );
    expect(within(slot(1)).getByRole("status")).toHaveTextContent("Checking…");
    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
  });

  it("puts a photo in the first free place, whichever empty slot was tapped", async () => {
    const api_ = fakeApi({
      "GET /v1/me/photos": () => json(200, [photo()]),
      "POST /v1/photos/upload-url": () => envelope(429, "RATE_LIMITED"),
    });
    renderStep();

    await userEvent.click(
      (
        await screen.findAllByRole("button", { name: "Add a photo" })
      )[4] as HTMLElement,
    );
    const input = document.querySelector('input[type="file"]');
    await userEvent.upload(
      input as HTMLInputElement,
      new File(["x"], "x.jpg", { type: "image/jpeg" }),
    );

    await waitFor(() =>
      expect(
        api_.calls.find((c) => c.path === "/v1/photos/upload-url")?.body,
      ).toMatchObject({ position: 1 }),
    );
  });

  it("sends a file the browser can't read as it is, and the API's refusal says what to do (D-089)", async () => {
    resize.next = "unreadable";
    const api_ = fakeApi({
      "GET /v1/me/photos": () => json(200, []),
      "POST /v1/photos/upload-url": () =>
        envelope(422, "UNSUPPORTED_IMAGE", { accepted: ["image/jpeg"] }),
    });
    renderStep();
    await screen.findByRole("list");

    await pick(new File(["heic"], "IMG_0001.HEIC", { type: "image/heic" }));

    expect(await slotAlert(1)).toHaveTextContent(
      "We can't use this file — choose a JPEG, PNG or WebP photo",
    );
    expect(
      api_.calls.find((c) => c.path === "/v1/photos/upload-url")?.body,
    ).toMatchObject({ content_type: "image/heic" });
    expect(
      within(slot(1)).getByRole("button", { name: "Choose another" }),
    ).toBeInTheDocument();
  });

  it("shows the server's refusal of what arrived, with a way to choose another", async () => {
    fakeApi({
      "GET /v1/me/photos": () => json(200, []),
      "POST /v1/photos/upload-url": () =>
        json(200, { photo_id: "p1", put_url: PUT_URL, headers: SIGNED }),
      "POST /v1/photos/p1/complete": () =>
        envelope(422, "IMAGE_TOO_LARGE", { max_bytes: 8388608 }),
      "GET /v1/me": () => json(200, me()),
    });
    fakeXhr((request) => queueMicrotask(() => request.respond(200)));
    renderStep();
    await screen.findByRole("list");

    await pick();

    expect(await slotAlert(1)).toHaveTextContent(
      "This photo is over 8 MB — choose a smaller one",
    );
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]');
    const click = vi.spyOn(input as HTMLInputElement, "click");
    await userEvent.click(
      within(slot(1)).getByRole("button", { name: "Choose another" }),
    );
    expect(click).toHaveBeenCalledOnce();
  });

  it("gives the place back when the upload never arrives, then tries the same photo again", async () => {
    let urls = 0;
    const api_ = fakeApi({
      "GET /v1/me/photos": () => json(200, []),
      "POST /v1/photos/upload-url": () =>
        json(200, {
          photo_id: `p${++urls}`,
          put_url: PUT_URL,
          headers: SIGNED,
        }),
      "DELETE /v1/photos/p1": () => json(204),
      "POST /v1/photos/p2/complete": () =>
        json(200, photo({ id: "p2", status: "pending" })),
      "GET /v1/me": () => json(200, me()),
    });
    const xhr = fakeXhr();
    renderStep();
    await screen.findByRole("list");

    await pick();
    await waitFor(() => expect(xhr.requests).toHaveLength(1));
    xhr.last().fail();

    expect(await slotAlert(1)).toHaveTextContent(
      "This photo didn't upload — check your connection and try again",
    );
    expect(api_.sent()).toContain("DELETE /v1/photos/p1");

    await userEvent.click(
      within(slot(1)).getByRole("button", { name: "Try again" }),
    );
    await waitFor(() => expect(xhr.requests).toHaveLength(2));
    expect(xhr.last().body).toBe(xhr.requests[0]?.body);
    xhr.last().respond(200);
    await waitFor(() =>
      expect(api_.sent()).toContain("POST /v1/photos/p2/complete"),
    );
  });
});

describe("each photo's state", () => {
  it("shows an approved photo plainly, the first as the main one", async () => {
    fakeApi({
      "GET /v1/me/photos": () =>
        json(200, [
          photo(),
          photo({ id: "p2", position: 1, url: "https://cdn.test/p/p2.jpg" }),
        ]),
    });

    renderStep();

    const first = await screen.findByRole("listitem", { name: "Photo 1" });
    expect(within(first).getByRole("img", { name: "Photo 1" })).toHaveAttribute(
      "src",
      "https://cdn.test/p/p1.jpg",
    );
    expect(within(first).getByText("Approved")).toBeInTheDocument();
    expect(within(first).getByText("Main")).toBeInTheDocument();
    expect(within(first).queryByRole("status")).toBeNull();
    expect(within(slot(2)).queryByText("Main")).toBeNull();
  });

  it("shows a pending photo by its signed link, blurred, as checking", async () => {
    const signed =
      "http://127.0.0.1:9000/velora-private/raw/u1/p1?X-Amz-Signature=a";
    fakeApi({
      "GET /v1/me/photos": () =>
        json(200, [photo({ status: "pending", url: signed })]),
    });

    renderStep();

    const image = await within(
      await screen.findByRole("listitem", {
        name: "Photo 1",
      }),
    ).findByRole("img", { name: "Photo 1" });
    expect(image).toHaveAttribute("src", signed);
    expect(image).toHaveClass("blur-sm");
    expect(within(slot(1)).getByRole("status")).toHaveTextContent("Checking…");
  });

  it("keeps a pending photo's first link while the list is asked again, so it isn't fetched again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let n = 0;
    const api_ = fakeApi({
      "GET /v1/me/photos": () =>
        json(200, [
          photo({
            status: "pending",
            url: `http://127.0.0.1:9000/velora-private/raw/u1/p1?sig=${++n}`,
          }),
        ]),
    });
    renderStep();
    const image = await screen.findByRole("img", { name: "Photo 1" });

    await vi.advanceTimersByTimeAsync(PHOTO_POLL_MS);
    await waitFor(() =>
      expect(api_.sent().filter((s) => s === "GET /v1/me/photos")).toHaveLength(
        2,
      ),
    );

    expect(image).toHaveAttribute(
      "src",
      "http://127.0.0.1:9000/velora-private/raw/u1/p1?sig=1",
    );
  });
});

describe("a rejection's reason reaches the slot that showed it (D-096)", () => {
  async function rejectedAs(reason: string) {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api_ = fakeApi({
      "GET /v1/me/photos": lists(
        [photo({ status: "pending" }), photo({ id: "p2", position: 1 })],
        [photo({ id: "p2", position: 1 })],
      ),
      "GET /v1/photos/p1": () =>
        json(
          200,
          photo({ status: "rejected", reject_reason: reason, url: null }),
        ),
      "PATCH /v1/me/photos/order": () =>
        json(200, [photo({ id: "p2", position: 0 })]),
    });
    renderStep();
    await within(
      await screen.findByRole("listitem", { name: "Photo 1" }),
    ).findByRole("status");

    await vi.advanceTimersByTimeAsync(PHOTO_POLL_MS);
    return api_;
  }

  it("says why in the place it was, and offers another", async () => {
    const api_ = await rejectedAs("no_face");

    expect(await slotAlert(1)).toHaveTextContent(
      "We couldn't find a face in this photo — try one that shows yours clearly",
    );
    expect(
      within(slot(1)).getByRole("button", { name: "Choose another" }),
    ).toBeInTheDocument();
    // The photo beside it stays where it was.
    expect(
      within(slot(2)).getByRole("img", { name: "Photo 2" }),
    ).toBeInTheDocument();
    expect(api_.sent()).toContain("GET /v1/photos/p1");
  });

  it.each(["other", "minor_suspected", "something_new"])(
    "reads %s in D-093's words, accusing nobody",
    async (reason) => {
      await rejectedAs(reason);

      expect(await slotAlert(1)).toHaveTextContent(
        "We couldn't verify this photo — try a different one",
      );
      expect(document.body.textContent).not.toMatch(
        /minor|under ?age|underage|too young|18/i,
      );
    },
  );

  it("clears the slot when asked, closing the gap so the next is the main one", async () => {
    const api_ = await rejectedAs("text_overlay");
    await slotAlert(1);

    await userEvent.click(
      screen.getByRole("button", { name: "Clear photo 1" }),
    );

    await waitFor(() =>
      expect(api_.sent().at(-1)).toBe("PATCH /v1/me/photos/order"),
    );
    expect(api_.calls.at(-1)?.body).toEqual({ photo_ids: ["p2"] });
    await waitFor(() =>
      expect(within(slot(1)).getByText("Main")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("says nothing of a photo removed in another tab", async () => {
    await rejectedAs("user_deleted");

    await waitFor(() =>
      expect(
        within(slot(1)).getByRole("button", { name: "Add a photo" }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("removing and reordering", () => {
  const two = [photo(), photo({ id: "p2", position: 1 })];

  it("removes a photo, then closes the gap so the next is the main one", async () => {
    let removed = false;
    const api_ = fakeApi({
      "GET /v1/me/photos": () =>
        json(200, removed ? [photo({ id: "p2", position: 1 })] : two),
      "DELETE /v1/photos/p1": () => {
        removed = true;
        return json(204);
      },
      "PATCH /v1/me/photos/order": () =>
        json(200, [photo({ id: "p2", position: 0 })]),
    });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Remove photo 1" }),
    );

    await waitFor(() =>
      expect(api_.sent()).toEqual([
        "GET /v1/me/photos",
        "DELETE /v1/photos/p1",
        "GET /v1/me/photos",
        "PATCH /v1/me/photos/order",
      ]),
    );
    expect(api_.calls.at(-1)?.body).toEqual({ photo_ids: ["p2"] });
    await waitFor(() =>
      expect(within(slot(1)).getByText("Main")).toBeInTheDocument(),
    );
  });

  it.each([
    ["Move photo 1 later", ["p2", "p1"]],
    ["Move photo 2 earlier", ["p2", "p1"]],
  ])("%s with the buttons beside it", async (name, order) => {
    const api_ = fakeApi({
      "GET /v1/me/photos": () => json(200, two),
      "PATCH /v1/me/photos/order": () => json(200, two),
    });
    renderStep();

    await userEvent.click(await screen.findByRole("button", { name }));

    await waitFor(() =>
      expect(api_.calls.at(-1)?.body).toEqual({ photo_ids: order }),
    );
  });

  it("can't move the first photo earlier or the last later", async () => {
    fakeApi({ "GET /v1/me/photos": () => json(200, two) });
    renderStep();

    expect(
      await screen.findByRole("button", { name: "Move photo 1 earlier" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Move photo 2 later" }),
    ).toBeDisabled();
  });

  it("drags one photo onto another's place", async () => {
    const api_ = fakeApi({
      "GET /v1/me/photos": () =>
        json(200, [...two, photo({ id: "p3", position: 2 })]),
      "PATCH /v1/me/photos/order": () => json(200, two),
    });
    renderStep();
    await screen.findByRole("img", { name: "Photo 3" });
    const data = { effectAllowed: "", setData: vi.fn() };

    fireEvent.dragStart(slot(3), { dataTransfer: data });
    fireEvent.dragOver(slot(1), { dataTransfer: data });
    fireEvent.drop(slot(1), { dataTransfer: data });

    await waitFor(() =>
      expect(api_.calls.at(-1)?.body).toEqual({
        photo_ids: ["p3", "p1", "p2"],
      }),
    );
  });
});

describe("going on", () => {
  it("leaves by the step's own exit and goes where its Me says, the gaps closed first (T-4.12)", async () => {
    const api_ = fakeApi({
      "GET /v1/me/photos": () => json(200, [photo()]),
      "POST /v1/me/photos/done": () =>
        json(200, me({ onboarding_step: "interests" })),
    });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Continue" }),
    );

    await waitFor(() =>
      expect(nav.push).toHaveBeenCalledWith("/onboarding/interests"),
    );
    expect(api_.sent()).toEqual([
      "GET /v1/me/photos",
      "GET /v1/me/photos",
      "POST /v1/me/photos/done",
    ]);
  });

  it("says so when the server refuses the exit, whatever this screen allowed", async () => {
    // The rule is the server's (FACE_PHOTO_REQUIRED): a screen that let a
    // woman tap Continue shows its answer, and nobody moves.
    fakeApi({
      "GET /v1/me/photos": () => json(200, []),
      "POST /v1/me/photos/done": () => envelope(403, "FACE_PHOTO_REQUIRED"),
    });
    renderStep();

    await userEvent.click(
      await screen.findByRole("button", { name: "Continue" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Add your face photo first.",
    );
    expect(nav.push).not.toHaveBeenCalled();
  });

  it("shows women the private-album note, and only women", async () => {
    fakeApi({ "GET /v1/me/photos": () => json(200, []) });
    const note = /You can add a private album later/;

    const { unmount } = renderStep(me({ gender: "female" }));
    expect(await screen.findByText(note)).toBeInTheDocument();
    unmount();

    renderStep(me({ gender: "male" }));
    await screen.findByRole("list");
    expect(screen.queryByText(note)).toBeNull();
  });
});

describe("the face photo's slot (T-4.12, D-391)", () => {
  function faceSlot(): HTMLElement {
    return screen.getByRole("region", { name: "Your face photo" });
  }

  async function pickFace(
    file = new File(["raw"], "face.jpg", { type: "image/jpeg" }),
  ) {
    await userEvent.click(
      await screen.findByRole("button", { name: "Add your face photo" }),
    );
    const inputs =
      document.querySelectorAll<HTMLInputElement>('input[type="file"]');
    const input = inputs[inputs.length - 1];
    if (!input) throw new Error("No file picker.");
    await userEvent.upload(input, file);
  }

  it("uploads it as kind verification with no place, shows it checking, then approved", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api_ = fakeApi({
      "GET /v1/me/photos": lists(
        [],
        [face({ status: "pending" })],
        [face({ status: "approved" })],
      ),
      "POST /v1/photos/upload-url": () =>
        json(200, { photo_id: "f1", put_url: PUT_URL, headers: SIGNED }),
      "POST /v1/photos/f1/complete": () =>
        json(200, face({ status: "pending" })),
    });
    const xhr = fakeXhr();
    renderStep(me({ gender: "female" }));
    await screen.findByRole("list");

    await pickFace();
    await waitFor(() => expect(xhr.requests).toHaveLength(1));
    xhr.last().respond(200);

    await waitFor(() =>
      expect(api_.sent()).toContain("POST /v1/photos/f1/complete"),
    );
    expect(
      api_.calls.find((c) => c.path === "/v1/photos/upload-url")?.body,
    ).toEqual({ kind: "verification", content_type: "image/jpeg" });
    expect(
      await within(faceSlot()).findByRole("status", {
        name: "Checking your face photo…",
      }),
    ).toBeInTheDocument();
    // Never in the grid: the six places are the public photos' alone; and
    // nothing to show on the profile until it is approved.
    expect(screen.getAllByRole("button", { name: "Add a photo" })).toHaveLength(
      6,
    );
    expect(
      within(faceSlot()).getByRole("switch", {
        name: "Also show it on my profile",
      }),
    ).toBeDisabled();
    await vi.advanceTimersByTimeAsync(PHOTO_POLL_MS);
    expect(
      await within(faceSlot()).findByText("Face photo approved"),
    ).toBeInTheDocument();
    expect(
      within(faceSlot()).getByRole("switch", {
        name: "Also show it on my profile",
      }),
    ).toBeEnabled();
  });

  it("says why it was refused, in its own slot, and offers another (D-096)", async () => {
    fakeApi({
      "GET /v1/me/photos": lists([face({ status: "pending" })], []),
      "GET /v1/photos/f1": () =>
        json(200, face({ status: "rejected", reject_reason: "no_face" })),
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderStep(me({ gender: "female" }));
    await within(
      await screen.findByRole("region", { name: "Your face photo" }),
    ).findByRole("status", { name: "Checking your face photo…" });

    await vi.advanceTimersByTimeAsync(PHOTO_POLL_MS);

    expect(await within(faceSlot()).findByRole("alert")).toHaveTextContent(
      "We couldn't find a face in this photo — try one that shows yours clearly",
    );
    expect(
      within(faceSlot()).getByRole("button", { name: "Choose another" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add your face photo to continue" }),
    ).toBeDisabled();
  });

  it("the toggle shows it on the profile as a public copy, and takes it down again", async () => {
    const api_ = fakeApi({
      "GET /v1/me/photos": lists(
        [face()],
        [face(), photo({ id: "c1", status: "pending", from_photo_id: "f1" })],
        [face()],
      ),
      "POST /v1/photos/f1/show": () =>
        json(200, photo({ id: "c1", status: "pending", from_photo_id: "f1" })),
      "DELETE /v1/photos/c1": () => json(204, null),
    });
    renderStep(me({ gender: "female" }));
    const toggle = await screen.findByRole("switch", {
      name: "Also show it on my profile",
    });
    expect(toggle).toHaveAttribute("aria-checked", "false");

    await userEvent.click(toggle);

    await waitFor(() =>
      expect(screen.getByRole("switch")).toHaveAttribute(
        "aria-checked",
        "true",
      ),
    );
    // The copy is a public photo like any other, checking in the grid.
    expect(within(slot(1)).getByRole("status")).toHaveTextContent("Checking…");

    await userEvent.click(screen.getByRole("switch"));

    await waitFor(() =>
      expect(screen.getByRole("switch")).toHaveAttribute(
        "aria-checked",
        "false",
      ),
    );
    expect(api_.sent()).toContain("POST /v1/photos/f1/show");
    expect(api_.sent()).toContain("DELETE /v1/photos/c1");
  });

  it("says when the toggle is refused, with the server's reason", async () => {
    fakeApi({
      "GET /v1/me/photos": () => json(200, [face()]),
      "POST /v1/photos/f1/show": () => envelope(422, "NOT_ALLOWED", { max: 6 }),
    });
    renderStep(me({ gender: "female" }));

    await userEvent.click(
      await screen.findByRole("switch", { name: "Also show it on my profile" }),
    );

    expect(await within(faceSlot()).findByRole("alert")).toHaveTextContent(
      "Remove a photo to make room first.",
    );
  });

  it("can't change once the selfie matched, and says so", async () => {
    fakeApi({ "GET /v1/me/photos": () => json(200, [face()]) });

    renderStep(me({ gender: "female", is_verified: true }));

    expect(
      await within(
        await screen.findByRole("region", { name: "Your face photo" }),
      ).findByText("It can't change now that your selfie has matched it."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Change your face photo" }),
    ).toBeNull();
  });

  it("tells a man it's optional, and a woman that it's needed", async () => {
    fakeApi({ "GET /v1/me/photos": () => json(200, []) });

    const { unmount } = renderStep(me({ gender: "male" }));
    expect(
      await screen.findByText(/Optional, and only for the selfie check/),
    ).toBeInTheDocument();
    unmount();

    renderStep(me({ gender: "female" }));
    expect(
      await screen.findByText(/Needed for the selfie check/),
    ).toBeInTheDocument();
  });
});
