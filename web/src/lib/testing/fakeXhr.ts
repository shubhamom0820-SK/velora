import { vi } from "vitest";

/**
 * A stand-in `XMLHttpRequest` for tests of the upload (src/lib/upload.ts): it
 * records what was sent and lets the test answer, report progress, fail or
 * abort. Test-only; nothing in the app imports it.
 */

type Handler = ((event: ProgressEvent) => void) | null;

export class FakeRequest {
  method = "";
  url = "";
  headers: Record<string, string> = {};
  withCredentials = false;
  body: unknown = undefined;
  status = 0;
  aborted = false;
  onload: Handler = null;
  onerror: Handler = null;
  onabort: Handler = null;
  upload: { onprogress: Handler } = { onprogress: null };

  constructor(private readonly onSend: (request: FakeRequest) => void) {}

  open(method: string, url: string): void {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string): void {
    this.headers[name] = value;
  }

  send(body: unknown): void {
    this.body = body;
    this.onSend(this);
  }

  abort(): void {
    this.aborted = true;
    this.onabort?.(new ProgressEvent("abort"));
  }

  /** The browser's upload progress event. */
  progress(loaded: number, total: number, lengthComputable = true): void {
    this.upload.onprogress?.(
      new ProgressEvent("progress", { loaded, total, lengthComputable }),
    );
  }

  /** Storage answered with `status`. */
  respond(status: number): void {
    this.status = status;
    this.onload?.(new ProgressEvent("load"));
  }

  /** No answer at all: offline, or refused by CORS or the CSP. */
  fail(): void {
    this.onerror?.(new ProgressEvent("error"));
  }
}

/** Install the fake; `requests` holds every request sent, in order. */
export function fakeXhr(onSend?: (request: FakeRequest) => void) {
  const requests: FakeRequest[] = [];
  vi.stubGlobal(
    "XMLHttpRequest",
    class extends FakeRequest {
      constructor() {
        super((request) => {
          requests.push(request);
          onSend?.(request);
        });
      }
    },
  );
  return {
    requests,
    last(): FakeRequest {
      const request = requests.at(-1);
      if (!request) throw new Error("No upload was sent.");
      return request;
    },
  };
}
