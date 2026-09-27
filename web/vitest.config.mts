import { defineConfig } from "vitest/config";

// Unit tests (06-TESTING): primitives, hooks, formatters. Vite compiles JSX from
// tsconfig's `jsx` setting and resolves `@/` from its `paths`, so neither
// @vitejs/plugin-react nor vite-tsconfig-paths is needed (D-042).
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
  },
});
