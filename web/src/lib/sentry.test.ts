// The one test besides src/lib/sentry.ts allowed the SDK (eslint.config.mjs):
// it reads what the SDK would send, through a transport that keeps it.
import * as Sentry from "@sentry/nextjs";
import type { ErrorEvent } from "@sentry/nextjs";
import { afterEach, describe, expect, it } from "vitest";

import {
  KEPT_INTEGRATIONS,
  captureRequestError,
  initOptions,
  scrub,
} from "./sentry";
import { sentryConfigFor } from "./sentry-config";
import { SENTRY_BUILD } from "./testing/sentryEnv";

const config = sentryConfigFor({ APP_ENV: "staging", ...SENTRY_BUILD });
if (config === null) throw new Error("the test's config must report");

const PHONE = "+919812345678";

/** Starts the SDK as a runtime starts it, keeping each event it would send. */
function start(runtime: "browser" | "server"): unknown[] {
  if (config === null) throw new Error("unreachable");
  const sent: unknown[] = [];
  // The transport's envelope, as the SDK hands it over: [headers, items], each
  // item [its header, its payload].
  type Transport = ReturnType<NonNullable<Sentry.BrowserOptions["transport"]>>;
  type Envelope = Parameters<Transport["send"]>[0];
  Sentry.init({
    ...initOptions(config, runtime),
    transport: (): Transport => ({
      send: async (envelope: Envelope) => {
        for (const [header, payload] of envelope[1]) {
          if (header.type === "event") sent.push(payload);
        }
        return {};
      },
      flush: async () => true,
    }),
  });
  return sent;
}

afterEach(async () => {
  await Sentry.close();
});

describe("what an event may carry (T-9.12, D-1003)", () => {
  it("errors only: no tracing, no breadcrumbs, nothing collected by itself", () => {
    const options = initOptions(config, "browser");
    expect(options.tracesSampleRate).toBeUndefined();
    expect(options.maxBreadcrumbs).toBe(0);
    expect(options.dataCollection).toEqual({
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
    });
    expect(options.initialScope).toEqual({
      tags: { component: "web-browser" },
    });
  });

  it("keeps exactly these of the SDK's own integrations, whatever it offers", () => {
    const offered = [
      ...KEPT_INTEGRATIONS,
      "Breadcrumbs",
      "HttpContext",
      "BrowserSession",
      "Http",
      "NodeFetch",
      "Console",
      "BrowserTracing",
      "Replay",
    ].map((name) => ({ name }));
    const integrations = initOptions(config, "server").integrations;
    if (typeof integrations !== "function") throw new Error("a filter");
    expect(
      integrations(offered as Parameters<typeof integrations>[0])
        .map((i) => i.name)
        .sort(),
    ).toEqual([...KEPT_INTEGRATIONS].sort());
  });

  it("the scrubber drops the request, the user, breadcrumbs and messages", () => {
    const event = {
      type: undefined,
      request: { url: "https://staging.veloraapp.co.in/share/priya" },
      user: { ip_address: "203.0.113.9" },
      breadcrumbs: [{ message: PHONE }],
      extra: { phone: PHONE },
      exception: { values: [{ type: "TypeError", value: PHONE }] },
      contexts: {
        nextjs: {
          request_path: "/share/priya",
          router_path: "/share/[username]",
        },
      },
    } as unknown as ErrorEvent;

    const scrubbed = scrub(event);

    expect(Object.keys(scrubbed).sort()).toEqual([
      "contexts",
      "exception",
      "type",
    ]);
    expect(scrubbed.exception?.values?.[0]).toEqual({
      type: "TypeError",
      value: "",
    });
    expect(scrubbed.contexts?.nextjs).toEqual({
      router_path: "/share/[username]",
    });
  });

  it("a browser error reaches the transport by its type and stack, and nothing of the page", async () => {
    const sent = start("browser");
    Sentry.addBreadcrumb({ message: `typed ${PHONE}` });

    Sentry.captureException(new TypeError(`no such user ${PHONE}`));
    await Sentry.flush(2000);

    expect(sent).toHaveLength(1);
    const event = sent[0] as ErrorEvent;
    expect(event.exception?.values?.[0]?.type).toBe("TypeError");
    expect(event.exception?.values?.[0]?.value).toBe("");
    expect(event.release).toBe(SENTRY_BUILD.NEXT_PUBLIC_SENTRY_RELEASE);
    expect(event.environment).toBe("staging");
    expect(event.tags?.component).toBe("web-browser");
    expect(event.request).toBeUndefined();
    expect(event.user).toBeUndefined();
    expect(JSON.stringify(event)).not.toContain(PHONE);
  });

  it("a server's request error goes by its route's pattern, never the path or its headers", async () => {
    const sent = start("server");

    captureRequestError(
      new Error(`render failed for ${PHONE}`),
      {
        path: "/share/priya?ref=PHONE",
        method: "GET",
        headers: {
          cookie: "refresh=secret-cookie",
          "x-forwarded-for": "203.0.113.9",
        },
      },
      {
        routerKind: "App Router",
        routePath: "/share/[username]",
        routeType: "render",
      },
    );
    await Sentry.flush(2000);

    expect(sent).toHaveLength(1);
    const text = JSON.stringify(sent[0]);
    expect(text).toContain("/share/[username]");
    for (const leaked of [
      "/share/priya",
      "secret-cookie",
      "203.0.113.9",
      PHONE,
    ]) {
      expect(text).not.toContain(leaked);
    }
  });
});
