#!/usr/bin/env node
/**
 * Expose board read/write, history search and detail expansion as stdio MCP tools.
 * Bind requests to this worker's identity; the HTTP service enforces membership.
 */
"use strict";

const readline = require("node:readline");
const http = require("node:http");
const https = require("node:https");
const { URL } = require("node:url");

const BOARD_URL = process.env.BOARD_SERVICE_URL || "http://board-service:8660";
const AGENT = process.env.AGENT_NAME || "unknown-agent";
const BOARD_IDS = (process.env.BOARD_IDS || "").split(",").map((s) => s.trim()).filter(Boolean);
const MAX_BOARD_ENTRIES = 2000;

function log(...args) {
    process.stderr.write("[mcp-board] " + args.map(String).join(" ") + "\n");
}

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
            const r = await httpRequest(
                "GET",
                `/board/${encodeURIComponent(board_id)}/read?viewer=${encodeURIComponent(AGENT)}`
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
                delegation_id: {
                    type: "string",
                    description:
                        "The unit of work this note belongs to — a short label for the sub-task you are " +
                        "on, e.g. \"python-parser\". Reuse the SAME id for every note about that " +
                        "sub-task: a refined PATCH_SUMMARY then REPLACES your earlier one instead " +
                        "of peers reading a stale candidate, and a FAIL strikes your own patch " +
                        "summary. A fresh id per note silently disables both.",
                },
            },
            required: ["board_id", "type", "content"],
        },
        handler: async ({ board_id, type, content, detail, delegation_id }) => {
            const r = await httpRequest("POST", `/board/${encodeURIComponent(board_id)}/note`, {
                thread_id: AGENT,
                type,
                content,
                detail: detail || null,
                delegation_id: delegation_id || null,
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
                        "PATCH_SUMMARY, CLAIM. Omit to search all types. " +
                        "e.g. \"FAIL|PATCH_SUMMARY\" to see only what was ruled out or fixed.",
                },
            },
            required: ["board_id"],
        },
        handler: async ({ board_id, words, limit, types }) => {
            const w = Array.isArray(words) ? words.join("|") : String(words || "");
            const ty = Array.isArray(types) ? types.join("|") : String(types || "");
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
                return `no match for [${(j.words || "")}] in the full board history (0 of 0).`;
            }
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
            const q = `labels=${encodeURIComponent(ls.join(","))}`;
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

function send(msg) {
    // stdout is reserved for newline-delimited JSON-RPC; diagnostics use stderr.
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
    if (method === "notifications/initialized") return;
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
