import { defineConfig } from "vitest/config";

/**
 * Unit-only vitest config: no globalSetup, so no `make up`.
 *
 * The default config brings the whole docker stack up in globalSetup, which is
 * right for the f2/f4/f8 integration suites and wrong for pure-logic tests like
 * pbench/dispatcher_serial.test.ts — those exercise a class with fakes and need
 * no cluster. Run with:
 *   npx vitest run --config vitest.unit.config.ts
 */
export default defineConfig({
  test: {
    include: [
      "pbench/dispatcher_serial.test.ts",
      // Pure-logic too: fake fetch, no board-service, no MySQL.
      "f8_sidecar/board_forcing.test.ts",
      "f8_sidecar/board_unreachable.test.ts",
    ],
    reporters: ["default"],
    testTimeout: 30_000,
  },
});
