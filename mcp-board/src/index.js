#!/usr/bin/env node
// mcp-board — copilot-CLI MCP stdio server that proxies to board-service HTTP.
//
// Reads env:
//   BOARD_SERVICE_URL  (required) — e.g. http://board-service:8660
//   AGENT_NAME         (required) — the identity used as thread_id / viewer
//   BOARD_IDS          (optional) — CSV of boards this agent can access
//                                    (only used as a hint in tool descriptions;
//                                    real auth is enforced by board-service)
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
const BOARD_IDS = (process.env.BOARD_IDS || "").split(",").map((s) => s.trim()).filter(Boolean);
// Mirrors MAX_BOARD_ENTRIES in board-service/shared_lessons.py. Used ONLY to
// state the bound in the tool description — the service is what enforces it,
// so a drift here misinforms the agent but cannot change behaviour.
const MAX_BOARD_ENTRIES = Number(process.env.BOARD_MAX_ENTRIES || 2000);

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
// runtime 403 (agents otherwise guess a sibling team's board name and get
// refused).
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
            `Read the shared context board. Returns the WHOLE board — every admitted gist ` +
            `(FACT / OBSERVED / FAIL / PATCH_SUMMARY / CLAIM), newest ${MAX_BOARD_ENTRIES} if the ` +
            `board is larger than that. ` +
            `For anything older than the board still holds, use board_grep. ` +
            (BOARD_IDS.length ? `You have access to boards: ${BOARD_IDS.join(", ")}.` : ""),
        inputSchema: {
            type: "object",
            properties: {
                board_id: boardIdSchema("read"),
            },
            required: ["board_id"],
        },
        handler: async ({ board_id }) => {
            // window_tokens=0 is the service's "unlimited" sentinel: it renders
            // the whole board instead of a priority-selected slice.
            //
            // Never a finite default such as `window_tokens || 1000`. A
            // 1000-token budget engages the _MAX_RENDERED_CLAIMS=6 /
            // _MAX_RENDERED_PATCH_SUMMARIES=4 caps and the char budget, so a
            // read of a ~12.7k-gist board returns a few dozen entries. An
            // absent CLAIM then means "dropped by the window" just as often as
            // "nobody claimed it", which is exactly the ambiguity the full
            // board exists to remove. And `0 || 1000 === 1000`, so an agent
            // could not opt out by asking for 0 either.
            const r = await httpRequest(
                "GET",
                `/board/${encodeURIComponent(board_id)}/read?viewer=${encodeURIComponent(AGENT)}&window_tokens=0`
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
                task_id: { type: "string", description: "Optional: free-form id linking related notes." },
                delegation_id: {
                    type: "string",
                    description:
                        "The unit of work this note belongs to — a short label for the sub-task you are " +
                        "on, e.g. \"python-parser\". Reuse the SAME id for every note about that " +
                        "sub-task: a refined PATCH_SUMMARY then REPLACES your earlier one instead " +
                        "of peers reading a stale candidate, and a FAIL strikes your own patch " +
                        "summary. A fresh id per note silently disables both.",
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
        name: "board_grep",
        description:
            `Search the board's ENTIRE run history for gists whose text contains your keywords, ` +
            `including everything older than the recent window board_read returns. ` +
            `words is a boolean expression: '|' is OR, '&' is AND, and '()' groups, so ` +
            `"(parser|lexer)&crash" means either parser or lexer AND crash; matching is ` +
            `case-insensitive and a malformed expression is rejected rather than guessed at. ` +
            `The parser parses the sequence with '|', '&' and '()' rather than space, so ` +
            `"null pointer&xref mode" searches for those two phrases rather than four ` +
            `separate words. ` +
            `Returns the newest matches and always reports the true total, so "showing 500 of 3182" ` +
            `means narrow your terms rather than assuming you have seen everything.`,
        inputSchema: {
            type: "object",
            properties: {
                board_id: boardIdSchema("search"),
                words: {
                    type: "string",
                    description:
                        "Optional boolean expression. '|' OR, '&' AND, '()' grouping; " +
                        "'&' binds tighter than '|'. " +
                        "e.g. \"segfault|hts_open\", \"parser&segfault\", " +
                        "\"(parser|lexer)&crash\", \"null pointer&xref mode\". " +
                        "Omit to filter by type alone.",
                },
                limit: {
                    type: "integer",
                    description: "Max matches to return, newest first. Default 500.",
                },
                types: {
                    type: "string",
                    description:
                        "Optional filter on note type, '|' separated (a note has exactly one " +
                        "type, so these OR together). One or more of FACT, OBSERVED, FAIL, " +
                        "PATCH_SUMMARY, CLAIM, TRIED. Omit to search all types. " +
                        "e.g. \"FAIL|PATCH_SUMMARY\" to see only what was ruled out or fixed.",
                },
            },
            required: ["board_id"],
        },
        handler: async ({ board_id, words, limit, types }) => {
            // Accept an array too: models routinely send ["a","b"] for a list
            // field, and failing that is a pointless round trip. The items OR
            // together; ',' is an ordinary character in the words grammar, so
            // joining on it would search the literal "a,b" and find nothing.
            const w = Array.isArray(words) ? words.join("|") : String(words || "");
            const ty = Array.isArray(types) ? types.join("|") : String(types || "");
            // Either alone is a valid query; only both-empty is refused, and
            // the service is the one that decides that.
            if (!w.trim() && !ty.trim())
                throw new Error("board_grep: provide words and/or types");
            let q = `viewer=${encodeURIComponent(AGENT)}`;
            if (w.trim()) q += `&words=${encodeURIComponent(w)}`;
            if (limit) q += `&limit=${encodeURIComponent(limit)}`;
            if (ty.trim()) q += `&types=${encodeURIComponent(ty)}`;
            const r = await httpRequest("GET", `/board/${encodeURIComponent(board_id)}/grep?${q}`);
            if (r.status >= 400) throw new Error(`board_grep ${r.status}: ${r.text}`);
            const j = r.json || {};
            const entries = j.entries || [];
            if (!entries.length) {
                // Say "nothing in the whole history" explicitly. The useful
                // conclusion here is "no peer has touched this", and that is
                // only sound because the search covered the full log.
                return `no match for [${(j.words || "")}] in the full board history (0 of 0).`;
            }
            // Server-rendered with format_for_prompt -- the same grouping and
            // line format as board_read and the turn-start block, so a gist
            // never looks different depending on which tool surfaced it.
            let out = j.rendered || entries
                .map((e) => `[${e.label} ${e.thread_id}/${e.type}] ${e.content}`)
                .join("\n");
            if (j.truncated) {
                out +=
                    `\n\nshowing ${j.returned} of ${j.total} matches (oldest-first within each ` +
                    `group; the newest ${j.returned} were kept) — narrow the terms or raise limit.`;
            } else {
                out += `\n\n${j.total} match${j.total === 1 ? "" : "es"} (complete).`;
            }
            if (j.dropped_terms && j.dropped_terms.length)
                out += `\n[too many terms; ignored: ${j.dropped_terms.join(", ")}]`;
            return out;
        },
    },
    {
        name: "board_unfold",
        description:
            `The board holds short gists; anything marked "Unfoldable" in a board render has full text behind it. ` +
            `Expand board gists into their full stored detail.`,
        inputSchema: {
            type: "object",
            properties: {
                board_id: boardIdSchema("unfold from"),
                labels: {
                    type: "array",
                    items: { type: "string" },
                    description: "Labels to expand, e.g. [\"G12\",\"G34\"]. Max 100.",
                },
            },
            required: ["board_id", "labels"],
        },
        handler: async ({ board_id, labels }) => {
            const ls = (Array.isArray(labels) ? labels : [labels]).filter(Boolean);
            if (!ls.length) throw new Error("board_unfold: labels required");
            // Always depth=raw. Agents only ever ask for raw and never address
            // a sub-chunk. The summary hop (G->S) exists to avoid spending raw
            // budget on a large unit, but stored details are tiny -- median
            // ~190 chars, max ~1,250 (~314 tokens) on a 32-worker board -- so
            // there is nothing to economise, and n_subchunks' floor of 3 would
            // describe a 190-char detail as three ~63-char pieces.
            // The endpoint still accepts depth for diagnostics.
            const q = `labels=${encodeURIComponent(ls.join(","))}&depth=raw`;
            const r = await httpRequest(
                "GET",
                `/board/${encodeURIComponent(board_id)}/unfold?viewer=${encodeURIComponent(AGENT)}&${q}`
            );
            if (r.status >= 400) throw new Error(`board_unfold ${r.status}: ${r.text}`);
            const j = r.json || {};
            let out = j.rendered || "(nothing unfolded)";
            if (j.unknown && j.unknown.length) out += `\n\n[unknown labels ignored: ${j.unknown.join(", ")}]`;
            if (j.dropped_over_cap && j.dropped_over_cap.length)
                out += `\n[dropped, over the label cap: ${j.dropped_over_cap.join(", ")}]`;
            return out;
        },
    },
];

const TOOLS_BY_NAME = Object.fromEntries(TOOLS.map((t) => [t.name, t]));

// --- JSON-RPC 2.0 stdio loop -----------------------------------------------
function send(msg) {
    process.stdout.write(JSON.stringify(msg) + "\n");
}

// --- notices: NOT here -------------------------------------------------------
// Notices are injected by mcp-notice-shim, which proxies every MCP server.
// Appending them to this server's results alone would reach only the board's
// share of tool calls (~15%, against ~45% for gitea+board+mattermost), leaving
// many tool calls between drains instead of almost none.
//
// Do NOT reintroduce a drain here: the shim wraps this server too, so a second
// appender would deliver every notice twice.

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
