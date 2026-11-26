import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const shim = fileURLToPath(new URL("../mcp_notice_shim.cjs", import.meta.url));
const upstream = `
    const readline = require("node:readline");
    readline.createInterface({ input: process.stdin }).on("line", (line) => {
        const { id, method, params } = JSON.parse(line);
        const result = method === "tools/list"
            ? { tools: [{ name: "read" }, { name: "write" }, { name: "unreviewed" }] }
            : { name: params.name };
        console.log(JSON.stringify({ jsonrpc: "2.0", id, result }));
    });
`;
const args = [shim, "--", process.execPath, "-e", upstream];
const shared = { board: ["read", "write"], gitea: ["read"] };
const policy = {
    ...shared,
    worker_overrides: {
        "test-worker1": { board: ["read"] },
        "test-worker2": { board: [] },
    },
};

function environment(t, config, agent, server = "board") {
    const dir = mkdtempSync(join(tmpdir(), "agensh-mcp-"));
    t.after(() => rmSync(dir, { recursive: true, force: true }));
    const path = join(dir, "policy.json");
    writeFileSync(path, JSON.stringify(config));
    return {
        ...process.env,
        AGENT_NAME: agent,
        AGENT_HARNESS: "",
        BOARD_SERVICE_URL: "",
        MCP_SERVER_NAME: server,
        MCP_TOOL_METADATA_FILE: "",
        MCP_TOOL_POLICY_FILE: path,
    };
}

function startShim(t, config, agent, server) {
    const child = spawn(process.execPath, args, {
        env: environment(t, config, agent, server),
        stdio: ["pipe", "pipe", "inherit"],
    });
    const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]();
    t.after(() => child.stdin.end());
    let id = 0;
    return async (method, params) => {
        child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: ++id, method, params }) + "\n");
        const { value } = await lines.next();
        const response = JSON.parse(value);
        assert.equal(response.id, id);
        return response;
    };
}

test("worker override narrows MCP discovery and calls", { timeout: 10000 }, async (t) => {
    const request = startShim(t, policy, "test-worker1");
    assert.deepEqual((await request("tools/list")).result.tools, [{ name: "read" }]);
    assert.equal((await request("tools/call", { name: "read" })).result.name, "read");
    assert.equal((await request("tools/call", { name: "write" })).error.code, -32602);
});

test("empty worker override disables all tools for that server", { timeout: 10000 }, async (t) => {
    const request = startShim(t, policy, "test-worker2");
    assert.deepEqual((await request("tools/list")).result.tools, []);
    assert.equal((await request("tools/call", { name: "read" })).error.code, -32602);
});

test("shared allowlists apply when a worker or server has no override", { timeout: 10000 }, async (t) => {
    const unrestricted = startShim(t, policy, "test-worker3");
    const otherServer = startShim(t, policy, "test-worker1", "gitea");
    const sharedOnly = startShim(t, shared, "");
    assert.deepEqual((await unrestricted("tools/list")).result.tools, [{ name: "read" }, { name: "write" }]);
    assert.equal((await unrestricted("tools/call", { name: "write" })).result.name, "write");
    assert.deepEqual((await otherServer("tools/list")).result.tools, [{ name: "read" }]);
    assert.deepEqual((await sharedOnly("tools/list")).result.tools, [{ name: "read" }, { name: "write" }]);
});

test("worker overrides reject unknown tools, unknown servers and missing worker identity", (t) => {
    const cases = [
        [{ ...shared, worker_overrides: { "test-worker1": { board: ["unreviewed"] } } }, "test-worker1", /must be a subset/],
        [{ ...shared, worker_overrides: { "test-worker1": { other: [] } } }, "test-worker1", /must be a subset/],
        [policy, "", /configured AGENT_NAME/],
    ];
    for (const [config, agent, message] of cases) {
        const result = spawnSync(process.execPath, args, {
            env: environment(t, config, agent), encoding: "utf8", timeout: 5000,
        });
        assert.equal(result.status, 1, result.error?.message);
        assert.match(result.stderr, message);
    }
});
