import { type NextRequest, NextResponse } from "next/server";

import { newNonce, policyWithNonce } from "@/lib/security-headers";

/**
 * The CSP for the sign-in and app routes (T-6.6, D-541): a fresh nonce per
 * response in place of 'unsafe-inline', since these pages render other
 * people's text. The policy is the build's (`CSP_WITH_NONCE`, next.config), so
 * it names exactly the hosts the static one does.
 *
 * Next reads the nonce from the request's CSP and puts it on its own scripts,
 * which is why the policy is set on the request as well as the response.
 * Their pages render per request (their layouts await `connection()`): a
 * static page's scripts would carry no nonce and be refused.
 */
export function proxy(request: NextRequest) {
  const policy = policyWithNonce(process.env.CSP_WITH_NONCE ?? "", newNonce());
  const headers = new Headers(request.headers);
  headers.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", policy);
  return response;
}

/**
 * `NONCE_ROUTES` (security-headers.ts), each and all beneath it, and
 * `AT_USERNAME`; a test holds the two equal.
 */
export const config = {
  matcher: [
    "/login/:path*",
    "/onboarding/:path*",
    "/discover/:path*",
    "/chats/:path*",
    "/wallet/:path*",
    "/you/:path*",
    "/people/:path*",
    "/share/:path*",
    "/@:username([A-Za-z0-9._]{4,20})",
  ],
};
