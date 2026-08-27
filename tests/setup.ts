import { loadEnv } from "./lib/env.ts";
import { bringUp, bringDown } from "./lib/cluster.ts";

/**
 * Vitest globalSetup. Runs once before all test files; the returned
 * function runs once after all test files.
 *
 * Env vars:
 *   OMC_TEST_NO_UP=1   skip `make up` (assume cluster already running)
 *   OMC_TEST_KEEP_UP=1 skip `make down` after the run
 */
export default async function setup(): Promise<() => Promise<void>> {
  const env = loadEnv();
  console.log("[setup] bringing cluster up…");
  await bringUp(env);
  console.log("[setup] cluster ready");

  return async () => {
    if (process.env.OMC_TEST_KEEP_UP === "1") {
      console.log("[teardown] OMC_TEST_KEEP_UP=1 — leaving cluster up");
      return;
    }
    if (process.env.OMC_TEST_NO_UP === "1") {
      console.log("[teardown] OMC_TEST_NO_UP=1 — leaving cluster up");
      return;
    }
    console.log("[teardown] bringing cluster down…");
    bringDown();
  };
}
