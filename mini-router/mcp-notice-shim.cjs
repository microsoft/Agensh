#!/usr/bin/env node
/**
 * mcp-notice-shim — a transparent stdio proxy that appends priority notices
 * (peer board entries and DMs) to MCP tool results.
 *
 * WHY THIS EXISTS
 * A worker otherwise learns of peer findings or messages only at the next
 * turn boundary. Agents post direct
 * messages far more often than they read a DM channel: the messages arrive and
 * nobody looks.
 *
 * Mid-turn delivery cannot come from the router: every router->agent path is
 * `connection.prompt()`, request/response, resolving only at turn end, and the
 * ACP client->agent surface has nothing that adds context to a live turn --
 * `prompt` starts one, `cancel` ends one. A TOOL RESULT is the one thing an
 * agent reads mid-loop.
 *
 * WHY A SHIM RATHER THAN THE BOARD SERVER
 * board is only ~15% of tool calls; gitea (~24%) + board + mattermost (~6%) is
 * ~45%, which is the difference between several tool calls between drains and
 * almost none. Gitea and Mattermost MCP servers are upstream
 * binaries behind the CLAUDE.md veto line, so this PROXIES them -- spawning the
 * server as a child and forwarding JSON-RPC verbatim -- which is the sidecar
 * workaround CLAUDE.md prescribes. No upstream file is touched.
 *
 * TWO INVARIANTS:
 *
 *   1. INVISIBLE WHEN IDLE. With nothing pending, every byte out of this
 *      process is a byte the upstream server produced. We forward the ORIGINAL
 *      line, never a re-serialization -- JSON.parse+stringify would silently
 *      reorder keys and break anything diffing tool output. The shim sits in
 *      front of all three servers, so a bug here breaks all three at once.
 *
 *   2. ZERO MODEL-INITIATED WORK. This only ever touches a `tools/call`
 *      RESPONSE. It advertises no tools (`tools/list` passes through untouched),
 *      never sends an unsolicited message, and never starts a turn. Delivery
 *      free-rides on a call the model made for its own reasons, so a notice
 *      costs nothing but the tokens it occupies.
 *
 * Fails open by construction: any error fetching or appending notices returns
 * the upstream result unmodified. A broken notice queue must never break gitea.
 *
 * Usage: node mcp-notice-shim.cjs -- <upstream-cmd> [args...]
 * Env:   BOARD_SERVICE_URL, AGENT_NAME
 */
"use strict";
const { spawn } = require("child_process");
const http = require("http");
const https = require("https");
const { URL } = require("url");

const BOARD_URL = (process.env.BOARD_SERVICE_URL || "").replace(/\/+$/, "");
const AGENT = process.env.AGENT_NAME || "";

const sep = process.argv.indexOf("--");
if (sep < 0 || sep === process.argv.length - 1) {
    process.stderr.write("mcp-notice-shim: usage: node mcp-notice-shim.cjs -- <upstream-cmd> [args...]\n");
    process.exit(2);
}
const argv = process.argv.slice(sep + 1);

const log = (...a) => process.stderr.write(`[shim] ${a.join(" ")}\n`);

const child = spawn(argv[0], argv.slice(1), { stdio: ["pipe", "pipe", "inherit"] });
child.on("error", (e) => {
    log("upstream spawn failed:", e.message);
    process.exit(1);
});
child.on("exit", (code, sig) => process.exit(code == null ? (sig ? 1 : 0) : code));

/** id -> method, so a response can be matched to the request that caused it. */
const methodById = new Map();

function httpGetJson(url, timeoutMs = 1500) {
    return new Promise((resolve) => {
        let u;
        try { u = new URL(url); } catch { return resolve(null); }
        const lib = u.protocol === "https:" ? https : http;
        const req = lib.get(u, (res) => {
            let body = "";
            res.on("data", (d) => (body += d));
            res.on("end", () => {
                if (res.statusCode >= 400) return resolve(null);
                try { resolve(JSON.parse(body)); } catch { resolve(null); }
            });
        });
        req.on("error", () => resolve(null));
        req.setTimeout(timeoutMs, () => { req.destroy(); resolve(null); });
    });
}

/**
 * Pending priority notices and their lease token. Returns an empty record when
 * disabled; an unreachable board-service must degrade to "no notices", never
 * to a broken tool call.
 */
async function fetchPending() {
    if (!BOARD_URL || !AGENT) return { notices: [], leaseToken: null };
    const j = await httpGetJson(`${BOARD_URL}/pending/${encodeURIComponent(AGENT)}`);
    const list = (j && j.notices) || [];
    return {
        notices: Array.isArray(list) ? list.filter((n) => n && n.text) : [],
        leaseToken: j && typeof j.lease_token === "string" ? j.lease_token : null,
    };
}

/**
 * Record what we rendered so the router can retire those rows in its next tick
 * instead of re-delivering them at the turn boundary. Never rejects: a lost ack
 * costs one duplicate notice. Resolves once the ack has landed or given up; the
 * caller awaits it only after the tool result is already written.
 */
function reportShown(notices, leaseToken) {
    return new Promise((resolve) => {
        if (!BOARD_URL || !AGENT || !notices.length) return resolve();
        const ids = notices.map((n) => n.id).filter((v) => v != null);
        if (!ids.length) return resolve();
        let u;
        try { u = new URL(`${BOARD_URL}/shown/${encodeURIComponent(AGENT)}`); } catch { return resolve(); }
        const lib = u.protocol === "https:" ? https : http;
        const payload = JSON.stringify({ ids, lease_token: leaseToken });
        const req = lib.request(u, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) },
        }, (res) => { res.on("end", resolve); res.on("close", resolve); res.on("error", resolve); res.resume(); });
        req.on("error", resolve);
        req.setTimeout(1500, () => { req.destroy(); resolve(); });
        req.write(payload);
        req.end();
    });
}

/**
 * Append notices to a tool result's trailing text block.
 *
 * Returns null when it cannot do so safely, which makes the caller forward the
 * original line untouched. Anything unexpected in the response shape is a
 * reason to do nothing, not a reason to guess.
 */
function withNotices(msg, notices) {
    const content = msg && msg.result && msg.result.content;
    if (!Array.isArray(content)) return null;
    const suffix = "\n\n" + notices.map((n) => n.text).join("\n");
    const idx = content.map((c) => c && c.type).lastIndexOf("text");
    if (idx >= 0) {
        content[idx] = { ...content[idx], text: String(content[idx].text ?? "") + suffix };
    } else {
        content.push({ type: "text", text: suffix.trimStart() });
    }
    return JSON.stringify(msg);
}

// --- client -> upstream -------------------------------------------------------
// Verbatim. We only record id->method in passing; nothing is rewritten, so a
// request the model made is exactly the request the upstream server sees.
let inBuf = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
    inBuf += chunk;
    let i;
    while ((i = inBuf.indexOf("\n")) >= 0) {
        const line = inBuf.slice(0, i);
        inBuf = inBuf.slice(i + 1);
        if (line.trim()) {
            try {
                const m = JSON.parse(line);
                if (m && m.id != null && m.method) methodById.set(m.id, m.method);
            } catch { /* not our business — forward it anyway */ }
        }
        child.stdin.write(line + "\n");
    }
});
process.stdin.on("end", () => child.stdin.end());

// --- upstream -> client -------------------------------------------------------
// Ordering: lines stay strictly in the order the server produced them, via
// `chain`.
let outBuf = "";
let chain = Promise.resolve();
child.stdout.setEncoding("utf8");
child.stdout.on("data", (chunk) => {
    outBuf += chunk;
    let i;
    while ((i = outBuf.indexOf("\n")) >= 0) {
        const line = outBuf.slice(0, i);
        outBuf = outBuf.slice(i + 1);
        chain = chain.then(() => handleUpstreamLine(line));
    }
});

async function handleUpstreamLine(line) {
    if (!line.trim()) return void process.stdout.write(line + "\n");

    let msg = null;
    try { msg = JSON.parse(line); } catch { /* fall through: forward verbatim */ }

    const isToolCall = msg && msg.id != null && methodById.get(msg.id) === "tools/call";
    if (msg && msg.id != null) methodById.delete(msg.id);

    // Invariant 2: only a tools/call response is ever touched.
    if (!isToolCall) return void process.stdout.write(line + "\n");

    // Checked before the fetch, not after: /pending leases what it returns to
    // this shim, so notices fetched for a result that cannot carry them (a
    // JSON-RPC error has no result.content) would be held back from the
    // agent's other shims until the lease ran out.
    if (!Array.isArray(msg.result && msg.result.content)) return void process.stdout.write(line + "\n");

    let pending = { notices: [], leaseToken: null };
    try { pending = await fetchPending(); } catch (e) { log("drain failed:", e.message); }
    const notices = pending.notices;

    // Invariant 1: nothing pending => the upstream's own bytes, unmodified.
    if (!notices.length) return void process.stdout.write(line + "\n");

    let out = null;
    try { out = withNotices(msg, notices); } catch (e) { log("append failed:", e.message); }
    if (out == null) return void process.stdout.write(line + "\n");

    process.stdout.write(out + "\n");
    // Held in `chain` until the ack lands, preserving upstream response order
    // and normally releasing this agent's durable mutex before the next result
    // checks /pending. Other shim processes are excluded by that mutex.
    await reportShown(notices, pending.leaseToken);
}
