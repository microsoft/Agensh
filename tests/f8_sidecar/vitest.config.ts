import { defineConfig } from "vitest/config";

/**
 * Standalone vitest config for f8_sidecar/secret_service.
 *
 * Unlike the top-level config (../vitest.config.ts) this one does NOT
 * pull in ../setup.ts globalSetup — the secret-service test brings up
 * ONLY the `secret-service` compose service (no Gitea, no Hermes, no
 * bootstrap) and tears it down on its own, so the full-stack lifecycle
 * is irrelevant and would just slow iteration.
 *
 * Run with:
 *   cd tests && pnpm vitest run -c f8_sidecar/vitest.config.ts
 */
export default defineConfig({
  test: {
    fileParallelism: false,
    pool: "forks",
    poolOptions: { forks: { singleFork: true } },
    testTimeout: 2 * 60 * 1000,
    hookTimeout: 2 * 60 * 1000,
    include: ["**/*.test.ts"],
    reporters: ["default"],
  },
});
