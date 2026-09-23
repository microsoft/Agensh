import { defineConfig } from "vitest/config";

/**
 * Static contract tests for the ProgramBench harness: compose rendering,
 * image selection, submission packing. Like the F9 config, this deliberately
 * skips tests/setup.ts — none of these need the shared Gitea stack, and
 * bringing it up would make a 300ms check take minutes.
 *
 * The real-integration ProgramBench tests are the shell scripts alongside
 * this file (test_net_isolation.sh, pbench-board/test_board_service.sh);
 * those run against live containers and are not in scope here.
 */
export default defineConfig({
  test: {
    fileParallelism: false,
    pool: "forks",
    maxWorkers: 1,
    testTimeout: 2 * 60 * 1000,
    hookTimeout: 2 * 60 * 1000,
    include: ["pbench/**/*.test.ts"],
    reporters: ["default"],
  },
});
