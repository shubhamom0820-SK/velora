import type { NextConfig } from "next";

import { securityHeaders } from "./src/lib/security-headers";

const nextConfig: NextConfig = {
  // `next dev` otherwise writes AGENTS.md and CLAUDE.md into web/ on every run.
  // The repo's root CLAUDE.md governs this project.
  agentRules: false,
  // No `X-Powered-By: Next.js`. Staging lacked it only because Vercel strips
  // it, a platform's behaviour we never verified or control; asked for here,
  // it's gone wherever the app runs (T-2.5).
  poweredByHeader: false,
  // On every response, pages and assets alike (T-2.5, D-059). Computed at
  // build time, so the CSP names the API this build calls.
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders() }];
  },
};

export default nextConfig;
