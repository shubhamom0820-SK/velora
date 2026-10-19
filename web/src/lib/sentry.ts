/**
 * The only code that touches the Sentry SDK (T-9.12; ESLint enforces it).
 * Loaded on demand, and only by a build that reports (sentry-config.ts):
 * instrumentation-client.ts in the browser, instrumentation.ts on the server.
 *
 * **Errors only, and nothing personal** (D-1003, as the API's): no tracing,
 * no replay, no sessions, no breadcrumbs (clicks, console lines and fetched
 * URLs would name people and what they did), no request (its headers, its
 * address, its cookies), no user, and an exception by its type and stack,
 * never its message, which can carry what the page was showing. The route a
 * server error happened on goes by its pattern (`/people/[id]`), never the
 * path asked for (`/share/<a username>`).
 */

import * as Sentry from "@sentry/nextjs";
import type { ErrorEvent } from "@sentry/nextjs";

import type { SentryWebConfig } from "./sentry-config";

/** The SDK's own integrations a build keeps; every other default is dropped:
 *  breadcrumbs, the page's URL and user agent (HttpContext), sessions, and on
 *  the server its HTTP, fetch and console instrumentation. */
export const KEPT_INTEGRATIONS: ReadonlySet<string> = new Set([
  "InboundFilters",
  "FunctionToString",
  "LinkedErrors",
  "Dedupe",
  // The browser's: errors the page didn't catch, and those in timers and events.
  "GlobalHandlers",
  "BrowserApiErrors",
  // The server's: errors the process didn't catch.
  "OnUncaughtException",
  "OnUnhandledRejection",
]);

export type Runtime = "browser" | "server";

/** The last step before an event leaves. */
export function scrub(event: ErrorEvent): ErrorEvent {
  delete event.request;
  delete event.user;
  delete event.breadcrumbs;
  delete event.extra;
  for (const exception of event.exception?.values ?? []) {
    exception.value = "";
  }
  const nextjs = event.contexts?.nextjs;
  if (nextjs) delete nextjs.request_path;
  return event;
}

/** What `Sentry.init` is given: one place, read by both runtimes and the tests. */
export function initOptions(
  config: SentryWebConfig,
  runtime: Runtime,
): Sentry.BrowserOptions & Sentry.NodeOptions {
  return {
    dsn: config.dsn,
    release: config.release,
    environment: config.environment,
    // Nothing the SDK collects by itself (11.x's successor to sendDefaultPii).
    // With HttpContext and the server's request instrumentation dropped most of
    // it has nothing to act on; it is set so a later integration can't start
    // collecting by default.
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
      graphQL: { document: false, variables: false },
      genAI: { inputs: false, outputs: false },
      databaseQueryData: false,
      queues: false,
      stackFrameVariables: false,
    },
    integrations: (defaults) =>
      defaults.filter((integration) => KEPT_INTEGRATIONS.has(integration.name)),
    maxBreadcrumbs: 0,
    beforeBreadcrumb: () => null,
    beforeSend: scrub,
    // Errors only: no tracing, no replay (D-1000).
    tracesSampleRate: undefined,
    initialScope: { tags: { component: `web-${runtime}` } },
  };
}

export function startSentry(config: SentryWebConfig, runtime: Runtime): void {
  Sentry.init(initOptions(config, runtime));
}

/** Next's `onRequestError`: a Server Component's, a route handler's or the
 *  proxy's error, reported as the SDK reports it, then scrubbed above. */
export function captureRequestError(
  ...args: Parameters<typeof Sentry.captureRequestError>
): void {
  Sentry.captureRequestError(...args);
}
