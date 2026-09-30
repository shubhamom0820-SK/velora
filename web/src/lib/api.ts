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
};

async function request(
  method: Method,
  path: string,
  { params, query, body, signal }: RawOptions,
): Promise<unknown> {
  const url = new URL(apiBaseUrl() + fillPath(path, params));
  for (const [key, value] of Object.entries(query ?? {})) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== undefined && item !== null) {
        url.searchParams.append(key, String(item));
      }
    }
  }

  const headers: Record<string, string> = { Accept: "application/json" };
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
  });

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined;
  return response.json();
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
