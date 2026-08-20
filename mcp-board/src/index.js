#!/usr/bin/env node
// mcp-board — copilot-CLI MCP stdio server that proxies to board-service HTTP.
//
// Reads env:
//   BOARD_SERVICE_URL  (required) — e.g. http://board-service:8660
//   AGENT_NAME         (required) — the identity used as thread_id / viewer
//   BOARD_IDS          (optional) — CSV of boards this agent can access
//                                    (only used as a hint in tool descriptions;
//                                    real auth is enforced by board-service)
//   BOARD_QUEUE_ID     (optional) — default queue id
//
// Protocol: stdio JSON-RPC 2.0 line-delimited (one JSON object per line).
// Implements only what copilot-CLI needs at startup + call time:
//   - initialize
//   - notifications/initialized (server ignores)
//   - tools/list
//   - tools/call
//   - shutdown (server exits)
"use strict";

const readline = require("node:readline");
const http = require("node:http");
const https = require("node:https");
const { URL } = require("node:url");

const BOARD_URL = process.env.BOARD_SERVICE_URL || "http://board-service:8660";
const AGENT = process.env.AGENT_NAME || "unknown-agent";
const DEFAULT_QUEUE = process.env.BOARD_QUEUE_ID || null;
const BOARD_IDS = (process.env.BOARD_IDS || "").split(",").map((s) => s.trim()).filter(Boolean);

function log(...args) {
    // stderr only — stdout is reserved for JSON-RPC.
    process.stderr.write("[mcp-board] " + args.map(String).join(" ") + "\n");
}

// --- HTTP helper -----------------------------------------------------------
function httpRequest(method, path, body) {
    return new Promise((resolve, reject) => {
        const u = new URL(path, BOARD_URL);
        const client = u.protocol === "https:" ? https : http;
        const payload = body ? Buffer.from(JSON.stringify(body)) : null;
        const req = client.request(
            {
                method,
                hostname: u.hostname,
                port: u.port,
                path: u.pathname + u.search,
                headers: {
                    "Content-Type": "application/json",
                    ...(payload ? { "Content-Length": String(payload.length) } : {}),
                },
            },
            (res) => {
                const chunks = [];
                res.on("data", (c) => chunks.push(c));
                res.on("end", () => {
                    const text = Buffer.concat(chunks).toString("utf8");
                    let json = null;
                    try {
                        json = text ? JSON.parse(text) : null;
                    } catch (_) {
                        // Leave json=null; caller sees status + text.
                    }
                    resolve({ status: res.statusCode || 0, text, json });
                });
            }
        );
        req.on("error", reject);
        if (payload) req.write(payload);
        req.end();
    });
}

// --- Tool definitions -------------------------------------------------------

// board_id schema shared by every board tool. With BOARD_IDS set this is an
// enum, which makes an inaccessible board unrepresentable instead of a
// runtime 403 (measured: 21 refused calls in one 25-agent run, every one an
// agent guessing a sibling team's board name).
function boardIdSchema(verb) {
    const desc = BOARD_IDS.length
        ? `Board to ${verb}. You are a member of: ${BOARD_IDS.join(", ")} — any other board is refused.`
        : `Board to ${verb}.`;
    return BOARD_IDS.length
        ? { type: "string", enum: BOARD_IDS, default: BOARD_IDS[0], description: desc }
        : { type: "string", description: desc };
}

const TOOLS = [
    {
        name: "board_read",
        description:
            `Read the shared context board. Returns a rendered, token-budgeted view of ` +
            `admitted gists (FACT / OBSERVED / FAIL / PATCH_SUMMARY / CLAIM). ` +
            `Priority: FACT/concrete-OBSERVED > FAIL > OBSERVED, most recent within priority. ` +
            (BOARD_IDS.length ? `You have access to boards: ${BOARD_IDS.join(", ")}.` : ""),
        inputSchema: {
            type: "object",
            properties: {
                board_id: boardIdSchema("read"),
                window_tokens: { type: "integer", description: "Token budget", default: 1000 },
            },
            required: ["board_id"],
        },
        handler: async ({ board_id, window_tokens }) => {
            const wt = window_tokens || 1000;
            const r = await httpRequest(
                "GET",
                `/board/${encodeURIComponent(board_id)}/read?viewer=${encodeURIComponent(AGENT)}&window_tokens=${wt}`
            );
            if (r.status >= 400) throw new Error(`board_read ${r.status}: ${r.text}`);
            return r.json.rendered || "(no notes)";
        },
    },
    {
        name: "board_write",
        description:
            `Write a typed gist to the shared context board. Types: FACT, OBSERVED, FAIL, PATCH_SUMMARY, CLAIM. ` +
            `FACT/OBSERVED/FAIL/CLAIM: max 100 chars. PATCH_SUMMARY: max 300 chars, must use format ` +
            `"files=A/B/C | idea=D | evidence=E | risk=F"; evidence cannot be tbd/pending/unverified/etc. ` +
            `Server runs a deterministic verifier; returns "admitted" or "rejected" with reason. ` +
            `Pass "detail" to store the FULL text behind the gist: peers see only your short gist, ` +
            `and can expand yours on demand with board_unfold using the label returned here. ` +
            `Use it for anything too long for the cap — command output, a full error, a file listing.`,
        inputSchema: {
            type: "object",
            properties: {
                board_id: boardIdSchema("write to"),
                type: {
                    type: "string",
                    enum: ["FACT", "OBSERVED", "FAIL", "PATCH_SUMMARY", "CLAIM"],
                },
                content: { type: "string", description: "The short gist (see caps above)" },
                detail: {
                    type: "string",
                    description:
                        "Optional full text behind the gist. Not shown to peers by default; " +
                        "retrievable via board_unfold. No length cap.",
                },
                task_id: { type: "string", description: "Optional: link to a queue task" },
                delegation_id: {
                    type: "string",
                    description:
                        "The unit of work this note belongs to — normally the queue task_id you claimed. " +
                        "Keep it stable for the duration of that task.",
                },
                task_instruction: {
                    type: "string",
                    description: "Optional: what you were asked to do; shown alongside PATCH_SUMMARYs.",
                },
            },
            required: ["board_id", "type", "content"],
        },
        handler: async ({ board_id, type, content, detail, task_id, delegation_id, task_instruction }) => {
            const r = await httpRequest("POST", `/board/${encodeURIComponent(board_id)}/note`, {
                thread_id: AGENT,
                type,
                content,
                detail: detail || null,
                task_id: task_id || null,
                delegation_id: delegation_id || null,
                task_instruction: task_instruction || null,
            });
            if (r.status >= 500) throw new Error(`board_write ${r.status}: ${r.text}`);
            return JSON.stringify(r.json || { status: "error", detail: r.text });
        },
    },
    {
        name: "board_unfold",
        description:
            `Expand board gists into their full stored detail. The board holds short gists; ` +
            `anything marked "Unfoldable" in a board render has full text behind it, addressed by a label like G12. ` +
            `Two hops: depth="summary" lists the sub-chunks of each label (G12.1, G12.2, ...) so you can see ` +
            `what is there cheaply; depth="raw" returns the actual text, and asking for a sub-chunk ` +
            `(e.g. G12.2) also returns its neighbors G12.1 and G12.3. ` +
            `At most ${5} labels per call. Expanded text is for THIS step only — it is not added to the board, ` +
            `so if it matters to your peers, publish it as your own gist.`,
        inputSchema: {
            type: "object",
            properties: {
                board_id: boardIdSchema("unfold from"),
                labels: {
                    type: "array",
                    items: { type: "string" },
                    description: "Labels to expand, e.g. [\"G12\",\"G7.2\"]. Max 5.",
                },
                depth: {
                    type: "string",
                    enum: ["summary", "raw"],
                    default: "summary",
                    description: "summary = list sub-chunks; raw = full text with neighbors",
                },
            },
            required: ["board_id", "labels"],
        },
        handler: async ({ board_id, labels, depth }) => {
            const ls = (Array.isArray(labels) ? labels : [labels]).filter(Boolean);
            if (!ls.length) throw new Error("board_unfold: labels required");
            const q = `labels=${encodeURIComponent(ls.join(","))}&depth=${encodeURIComponent(depth || "summary")}`;
            const r = await httpRequest(
                "GET",
                `/board/${encodeURIComponent(board_id)}/unfold?viewer=${encodeURIComponent(AGENT)}&${q}`
            );
            if (r.status >= 400) throw new Error(`board_unfold ${r.status}: ${r.text}`);
            const j = r.json || {};
            let out = j.rendered || "(nothing unfolded)";
            if (j.unknown && j.unknown.length) out += `\n\n[unknown labels ignored: ${j.unknown.join(", ")}]`;
            if (j.dropped_over_cap && j.dropped_over_cap.length)
                out += `\n[dropped, over the 5-label cap: ${j.dropped_over_cap.join(", ")}]`;
            return out;
        },
    },
    {
        name: "board_finalize",
        description:
            `Mark your latest PATCH_SUMMARY as an explicit handoff ("this is done, I stand behind it"). ` +
            `Peers see [status=final] on it and are told to trust finalized summaries over unfinalized ones. ` +
            `Call this when you finish the work a PATCH_SUMMARY describes. ` +
            `Pass the same delegation_id you used when writing it.`,
        inputSchema: {
            type: "object",
            properties: {
                board_id: boardIdSchema("finalize on"),
                delegation_id: { type: "string" },
            },
            required: ["board_id"],
        },
        handler: async ({ board_id, delegation_id }) => {
            const r = await httpRequest("POST", `/board/${encodeURIComponent(board_id)}/finalize`, {
                thread_id: AGENT,
                delegation_id: delegation_id || null,
            });
            if (r.status >= 500) throw new Error(`board_finalize ${r.status}: ${r.text}`);
            return JSON.stringify(r.json || { status: "error", detail: r.text });
        },
    },
    {
        name: "queue_claim",
        description:
            `Atomically claim the next ready (deps-satisfied) task from a queue. ` +
            `Returns the task {task_id, description, deps} or "null" if none ready. ` +
            (DEFAULT_QUEUE ? `Default queue: ${DEFAULT_QUEUE}.` : ""),
        inputSchema: {
            type: "object",
            properties: {
                queue_id: { type: "string", description: "Queue to poll", default: DEFAULT_QUEUE || "" },
            },
        },
        handler: async ({ queue_id }) => {
            const qid = queue_id || DEFAULT_QUEUE;
            if (!qid) throw new Error("queue_claim: queue_id required (no default set)");
            const r = await httpRequest("POST", `/queue/${encodeURIComponent(qid)}/claim`, {
                claimed_by: AGENT,
            });
            if (r.status >= 500) throw new Error(`queue_claim ${r.status}: ${r.text}`);
            return JSON.stringify(r.json);
        },
    },
    {
        name: "queue_complete",
        description:
            `Mark a claimed task as completed or failed. Only the agent that claimed it can complete it.`,
        inputSchema: {
            type: "object",
            properties: {
                queue_id: { type: "string", default: DEFAULT_QUEUE || "" },
                task_id: { type: "string" },
                state: { type: "string", enum: ["completed", "failed"], default: "completed" },
                result_gist_id: { type: "integer" },
            },
            required: ["task_id"],
        },
        handler: async ({ queue_id, task_id, state, result_gist_id }) => {
            const qid = queue_id || DEFAULT_QUEUE;
            if (!qid) throw new Error("queue_complete: queue_id required");
            const r = await httpRequest("POST", `/queue/${encodeURIComponent(qid)}/complete`, {
                task_id,
                claimed_by: AGENT,
                state: state || "completed",
                result_gist_id: result_gist_id || null,
            });
            if (r.status >= 500) throw new Error(`queue_complete ${r.status}: ${r.text}`);
            return JSON.stringify(r.json || { status: "error", detail: r.text });
        },
    },
    {
        name: "queue_enqueue",
        description:
            `Push a new subtask into the queue. Typically only the planner/director uses this. ` +
            `deps is a list of prior task_ids that must complete first.`,
        inputSchema: {
            type: "object",
            properties: {
                queue_id: { type: "string", default: DEFAULT_QUEUE || "" },
                task_id: { type: "string" },
                description: { type: "string" },
                deps: { type: "array", items: { type: "string" }, default: [] },
            },
            required: ["task_id", "description"],
        },
        handler: async ({ queue_id, task_id, description, deps }) => {
            const qid = queue_id || DEFAULT_QUEUE;
            if (!qid) throw new Error("queue_enqueue: queue_id required");
            const r = await httpRequest("POST", `/queue/${encodeURIComponent(qid)}/enqueue`, {
                task_id,
                description,
                deps: deps || [],
                enqueued_by: AGENT,
            });
            if (r.status >= 500) throw new Error(`queue_enqueue ${r.status}: ${r.text}`);
            return JSON.stringify(r.json || { status: "error", detail: r.text });
        },
    },
    {
        name: "queue_status",
        description: `Get counts + all tasks in a queue. Useful for planners to check overall progress.`,
        inputSchema: {
            type: "object",
            properties: {
                queue_id: { type: "string", default: DEFAULT_QUEUE || "" },
            },
        },
        handler: async ({ queue_id }) => {
            const qid = queue_id || DEFAULT_QUEUE;
            if (!qid) throw new Error("queue_status: queue_id required");
            const r = await httpRequest("GET", `/queue/${encodeURIComponent(qid)}/status`);
            if (r.status >= 500) throw new Error(`queue_status ${r.status}: ${r.text}`);
            return JSON.stringify(r.json);
        },
    },
];

const TOOLS_BY_NAME = Object.fromEntries(TOOLS.map((t) => [t.name, t]));

// --- JSON-RPC 2.0 stdio loop -----------------------------------------------
function send(msg) {
    process.stdout.write(JSON.stringify(msg) + "\n");
}

async function handle(msg) {
    const { id, method, params } = msg;
    if (method === "initialize") {
        send({
            jsonrpc: "2.0",
            id,
            result: {
                protocolVersion: "2024-11-05",
                capabilities: { tools: {} },
                serverInfo: { name: "mcp-board", version: "0.1.0" },
            },
        });
        return;
    }
    if (method === "notifications/initialized") return;  // no reply
    if (method === "tools/list") {
        send({
            jsonrpc: "2.0",
            id,
            result: {
                tools: TOOLS.map((t) => ({
                    name: t.name,
                    description: t.description,
                    inputSchema: t.inputSchema,
                })),
            },
        });
        return;
    }
    if (method === "tools/call") {
        const { name, arguments: args } = params || {};
        const tool = TOOLS_BY_NAME[name];
        if (!tool) {
            send({ jsonrpc: "2.0", id, error: { code: -32601, message: `unknown tool ${name}` } });
            return;
        }
        try {
            const out = await tool.handler(args || {});
            send({
                jsonrpc: "2.0",
                id,
                result: { content: [{ type: "text", text: String(out) }] },
            });
        } catch (e) {
            send({
                jsonrpc: "2.0",
                id,
                result: {
                    isError: true,
                    content: [{ type: "text", text: `error: ${e.message || e}` }],
                },
            });
        }
        return;
    }
    if (method === "shutdown") {
        send({ jsonrpc: "2.0", id, result: null });
        setImmediate(() => process.exit(0));
        return;
    }
    // Unknown method — return an error only if it had an id (was a request).
    if (id !== undefined && id !== null) {
        send({ jsonrpc: "2.0", id, error: { code: -32601, message: `method not found: ${method}` } });
    }
}

log(`starting; agent=${AGENT} board_url=${BOARD_URL} boards=${BOARD_IDS.join(",") || "(any)"}`);

const rl = readline.createInterface({ input: process.stdin });
rl.on("line", async (line) => {
    line = line.trim();
    if (!line) return;
    try {
        const msg = JSON.parse(line);
        await handle(msg);
    } catch (e) {
        log("parse error:", e.message);
    }
});
rl.on("close", () => process.exit(0));
