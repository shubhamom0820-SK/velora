import { csrfCookieName, readCookie } from "@/lib/auth-cookies";
import { useSession } from "@/store/session";
import type { paths } from "@/types/api";

/**
 * The one way the web app talks to the API. Typed from `src/types/api.ts`, which
 * `make types` generates from the API's OpenAPI schema: a path or method the API
 * doesn't have won't compile, and each response has its schema's type.
 *
 * Components never call this directly; they use the TanStack Query hooks in
 * `src/lib/queries/` (CLAUDE.md rule 14, enforced by ESLint).
 */

type Method = "get" | "post" | "put" | "patch" | "delete";

/** Every path that has `method`, e.g. `PathsWith<"get">` is everything you can GET. */
type PathsWith<M extends Method> = {
  [P in keyof paths]: paths[P][M] extends undefined ? never : P;
}[keyof paths];

type Operation<P extends keyof paths, M extends Method> = NonNullable<
  paths[P][M]
>;

/** A field of an operation, or `never` when the API marks it `?: never`. */
type Field<T> = [NonNullable<T>] extends [never] ? never : NonNullable<T>;

type Data<O> = O extends { responses: infer R }
  ? {
      [S in keyof R]: S extends 204
        ? undefined
        : S extends 200 | 201 | 202
          ? R[S] extends { content: { "application/json": infer B } }
            ? B
            : undefined
          : never;
    }[keyof R]
  : never;

type Parameters<O> = O extends { parameters: infer Pa } ? Pa : never;
type PathParams<O> = Field<
  Parameters<O> extends { path?: infer X } ? X : never
>;
type QueryParams<O> = Field<
  Parameters<O> extends { query?: infer X } ? X : never
>;
type Body<O> =
  Field<O extends { requestBody?: infer X } ? X : never> extends {
    content: { "application/json": infer B };
  }
    ? B
    : never;

type Options<O> = {
  /** Fills `{name}` segments of the path. */
  params?: PathParams<O>;
  query?: QueryParams<O>;
  body?: Body<O>;
  signal?: AbortSignal;
  headers?: Readonly<Record<string, string>>;
};

/** What the API said went wrong: its error envelope (02-ARCHITECTURE §3), plus the HTTP status. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Readonly<Record<string, unknown>> | undefined;

  constructor(init: {
    code: string;
    message: string;
    status: number;
    details?: Record<string, unknown>;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.code = init.code;
    this.status = init.status;
    this.details = init.details;
  }
}

/** Where `make dev` runs the API. */
const LOCAL_API = "http://127.0.0.1:8000";

/**
 * The API's base URL. `next dev` falls back to the local API, so `make dev`
 * needs no setup; every other build must set `NEXT_PUBLIC_API_URL`. An
 * allowlist: a build that forgot it fails loudly instead of calling localhost.
 */
export function apiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (url) return url.replace(/\/+$/, "");
  if (process.env.NODE_ENV === "development") return LOCAL_API;
  throw new Error("NEXT_PUBLIC_API_URL is not set.");
}

type Envelope = {
  error: { code: string; message: string; details?: Record<string, unknown> };
};

function isEnvelope(value: unknown): value is Envelope {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const { error } = value;
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string" &&
    "message" in error &&
    typeof error.message === "string" &&
    (!("details" in error) ||
      (typeof error.details === "object" && error.details !== null))
  );
}

async function toApiError(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  if (isEnvelope(body)) {
    return new ApiError({ ...body.error, status: response.status });
  }
  // Not ours: a proxy's HTML 502, a platform timeout page.
  return new ApiError({
    code: "INTERNAL",
    message: `Request failed with status ${response.status}.`,
    status: response.status,
  });
}

function fillPath(path: string, params: object | undefined): string {
  return path.replace(/\{(\w+)\}/g, (_, name: string) => {
    const value: unknown = params?.[name as keyof typeof params];
    if (value === undefined) throw new Error(`Missing path param "${name}".`);
    return encodeURIComponent(String(value));
  });
}

/** `Options` once the types have done their job. */
type RawOptions = {
  params?: object;
  query?: object;
  body?: unknown;
  signal?: AbortSignal;
  headers?: Readonly<Record<string, string>>;
};

/**
 * The refresh cookie's path (D-054): the only requests that carry cookies.
 * Every other call sends none, said outright rather than left to `fetch`'s
 * default.
 */
const AUTH_PATHS = "/v1/auth/";

/** Authenticated by the refresh cookie and `X-CSRF`, never the access token (D-067). */
const COOKIE_AUTHENTICATED: ReadonlySet<string> = new Set([
  "/v1/auth/refresh",
  "/v1/auth/logout",
]);

/**
 * The answers that mean the session is over, not a wrong PIN or code: no valid
 * token (401), or an account that may not sign in (403, D-067).
 */
const SESSION_GONE: ReadonlySet<string> = new Set([
  "AUTH_REQUIRED",
  "SESSION_REVOKED",
  "TOKEN_EXPIRED",
  "ACCOUNT_BANNED",
  "ACCOUNT_FROZEN",
]);

/** The `X-CSRF` header the refresh and logout endpoints check (D-055). */
export function csrfHeader(): Record<string, string> {
  const value = readCookie(csrfCookieName());
  return value === null ? {} : { "X-CSRF": value };
}

async function request(
  method: Method,
  path: string,
  options: RawOptions,
  retried = false,
): Promise<unknown> {
  const { params, query, body, signal } = options;
  const url = new URL(apiBaseUrl() + fillPath(path, params));
  for (const [key, value] of Object.entries(query ?? {})) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== undefined && item !== null) {
        url.searchParams.append(key, String(item));
      }
    }
  }

  const headers: Record<string, string> = {
    ...options.headers,
    Accept: "application/json",
  };
  const token = useSession.getState().accessToken;
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  // A network failure (offline, DNS, CORS) rejects here as a TypeError and is
  // thrown as-is: it isn't the API's answer, so it isn't an ApiError.
  const response = await fetch(url, {
    method: method.toUpperCase(),
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
    credentials: path.startsWith(AUTH_PATHS) ? "include" : "omit",
  });

  if (!response.ok) {
    const error = await toApiError(response);
    if (!COOKIE_AUTHENTICATED.has(path)) {
      // An expired token is renewed once and the request tried again; any
      // other end of the session signs this tab out.
      if (error.code === "TOKEN_EXPIRED" && !retried) {
        await refreshAccessToken();
        return request(method, path, options, true);
      }
      if (SESSION_GONE.has(error.code)) useSession.getState().signOut();
    }
    throw error;
  }
  if (response.status === 204) return undefined;
  return response.json();
}

/** The Web Locks name every tab of this site queues refreshes under. */
export const REFRESH_LOCK = "auth-refresh";

let refreshing: Promise<string> | null = null;

/**
 * A new access token from the refresh cookie. One at a time in this tab (every
 * caller shares the refresh in flight), and one at a time across tabs, under a
 * Web Lock: two tabs must never present the same refresh token, or the second
 * is reuse (D-067's 10-second grace covers only what slips through).
 */
export function refreshAccessToken(): Promise<string> {
  refreshing ??= underRefreshLock(refreshOnce).finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function underRefreshLock<T>(work: () => Promise<T>): Promise<T> {
  const locks = typeof navigator === "undefined" ? undefined : navigator.locks;
  // Every browser we support has Web Locks; without them, the grace covers it.
  return locks ? await locks.request(REFRESH_LOCK, work) : work();
}

async function refreshOnce(): Promise<string> {
  // Read inside the lock: a refresh in another tab may have just replaced it.
  const headers = csrfHeader();
  try {
    const { access_token } = await api.post("/v1/auth/refresh", { headers });
    useSession.getState().signIn(access_token);
    return access_token;
  } catch (error) {
    // The API's answer that there's no session to restore. A network failure
    // or a 5xx says nothing about the session, so it stays as it was.
    if (error instanceof ApiError && error.status < 500) {
      useSession.getState().signOut();
    }
    throw error;
  }
}

function method<M extends Method>(m: M) {
  return <P extends PathsWith<M>>(
    path: P,
    options: Options<Operation<P, M>> = {},
  ): Promise<Data<Operation<P, M>>> =>
    request(m, path, options as RawOptions) as Promise<Data<Operation<P, M>>>;
}

/** `await api.get("/healthz")` → `{ status: "ok" }`. Throws `ApiError` on any non-2xx. */
export const api = {
  get: method("get"),
  post: method("post"),
  put: method("put"),
  patch: method("patch"),
  delete: method("delete"),
};
