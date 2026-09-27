import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `next dev` otherwise writes AGENTS.md and CLAUDE.md into web/ on every run.
  // The repo's root CLAUDE.md governs this project.
  agentRules: false,
};

export default nextConfig;
