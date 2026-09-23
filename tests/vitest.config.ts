import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globalSetup: ["./setup.ts"],
    // Whole stack lifecycle is expensive; run files serially in a single
    // worker so we don't try to bring the cluster up multiple times.
    fileParallelism: false,
    pool: "forks",
    maxWorkers: 1,
    testTimeout: 5 * 60 * 1000,
    hookTimeout: 5 * 60 * 1000,
    // Test discovery
    include: ["**/*.test.ts"],
    reporters: ["default"],
  },
});
