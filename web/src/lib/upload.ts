/**
 * The upload itself (T-4.6): the browser's PUT of a photo straight to storage,
 * at the presigned URL `POST /photos/upload-url` returned. `fetch` can't report
 * upload progress, so this is an XMLHttpRequest: the only one in the web, and,
 * like `api.ts`'s fetch, kept in src/lib, where ESLint allows it (CLAUDE.md
 * rule 14). Components reach it only through `useUploadPhoto()`.
 *
 * It sends exactly the headers the API signed and nothing else: the
 * Content-Type is part of the signature (T-4.1), and storage refuses a PUT
 * whose headers differ. No cookies or token: the URL is the whole authority,
 * and storage is another origin, which the private bucket's CORS rule admits
 * for PUT and Content-Type only (T-4.6).
 */

/** How an upload failed: storage's refusal, no answer at all, or cancelled. */
export type UploadFailure = "refused" | "network" | "aborted";

export class UploadError extends Error {
  readonly failure: UploadFailure;
  /** Storage's HTTP status, when it answered. */
  readonly status: number | null;

  constructor(failure: UploadFailure, status: number | null = null) {
    super(
      status === null
        ? `The upload failed: ${failure}.`
        : `Storage refused the upload with status ${status}.`,
    );
    this.name = "UploadError";
    this.failure = failure;
    this.status = status;
  }
}

type PutOptions = {
  /** Called with the share sent so far, 0 to 100, as the browser reports it. */
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
};

/**
 * PUT `body` to `url` with exactly `headers`. Resolves once storage answers
 * 2xx; rejects with `UploadError` otherwise. A CORS or CSP refusal reaches
 * script only as a network failure: the browser says which in its console.
 */
export function putToStorage(
  url: string,
  body: Blob,
  headers: Readonly<Record<string, string>>,
  { onProgress, signal }: PutOptions = {},
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new UploadError("aborted"));
      return;
    }
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.withCredentials = false;
    for (const [name, value] of Object.entries(headers)) {
      xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress?.(
          Math.min(100, Math.floor((event.loaded / event.total) * 100)),
        );
      }
    };
    const abort = () => xhr.abort();
    const settle = () => signal?.removeEventListener("abort", abort);
    xhr.onload = () => {
      settle();
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100);
        resolve();
      } else {
        reject(new UploadError("refused", xhr.status));
      }
    };
    xhr.onerror = () => {
      settle();
      reject(new UploadError("network"));
    };
    xhr.onabort = () => {
      settle();
      reject(new UploadError("aborted"));
    };
    signal?.addEventListener("abort", abort, { once: true });
    xhr.send(body);
  });
}
