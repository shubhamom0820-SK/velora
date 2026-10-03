import { vi } from "vitest";

/**
 * A stand-in API for tests: `fetch` answers by "METHOD /path" and records every
 * request as the api client sent it. Test-only; nothing in the app imports it.
 */

export type Call = {
  method: string;
  path: string;
  headers: Headers;
  credentials: RequestCredentials | undefined;
  body: unknown;
};

export type Route = (call: Call) => Response | Promise<Response>;

export function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The API's error envelope (02-ARCHITECTURE §3). */
export function envelope(
  status: number,
  code: string,
  details?: Record<string, unknown>,
): Response {
  return json(status, {
    error: {
      code,
      message: `The API says ${code}.`,
      ...(details && { details }),
    },
  });
}

export function fakeApi(routes: Record<string, Route>) {
  const calls: Call[] = [];
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = {
        method: init?.method ?? "GET",
        path: new URL(String(input)).pathname,
        headers: new Headers(init?.headers),
        credentials: init?.credentials,
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      };
      calls.push(call);
      const route = routes[`${call.method} ${call.path}`];
      if (!route)
        throw new Error(`No fake route for ${call.method} ${call.path}`);
      return route(call);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return {
    calls,
    /** "METHOD /path" of every request, in order. */
    sent: () => calls.map((call) => `${call.method} ${call.path}`),
  };
}

/**
 * `navigator.locks`, which jsdom lacks: one holder at a time per page, in
 * order, like a browser's. `beforeEachGrant` runs as each request is granted,
 * before its callback: another tab's work that happened while this one waited.
 */
export function fakeLocks(beforeEachGrant?: () => void) {
  const requested: string[] = [];
  let held = false;
  let queue: Promise<unknown> = Promise.resolve();
  const locks = {
    request: <T>(name: string, callback: () => Promise<T>): Promise<T> => {
      requested.push(name);
      const run = queue.then(async () => {
        beforeEachGrant?.();
        held = true;
        try {
          return await callback();
        } finally {
          held = false;
        }
      });
      queue = run.catch(() => undefined);
      return run;
    },
  };
  Object.defineProperty(navigator, "locks", {
    value: locks,
    configurable: true,
  });
  return {
    requested,
    isHeld: () => held,
    uninstall: () => {
      Reflect.deleteProperty(navigator, "locks");
    },
  };
}

/** Set a cookie the way the API's Set-Cookie would leave it readable. */
export function setCookie(name: string, value: string): void {
  document.cookie = `${name}=${value}; path=/`;
}

export function clearCookies(): void {
  for (const pair of document.cookie.split(";")) {
    const name = pair.split("=")[0]?.trim();
    if (name) document.cookie = `${name}=; path=/; max-age=0`;
  }
}
