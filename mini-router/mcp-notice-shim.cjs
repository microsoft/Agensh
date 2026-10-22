#!/usr/bin/env node
/**
 * Wrap an infrastructure MCP server and append DMs and fresh board gists to
 * tools/call results. Leases coordinate concurrent wrappers for one worker.
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

async function fetchPending() {
    if (!BOARD_URL || !AGENT) return { notices: [], leaseToken: null };
    const j = await httpGetJson(`${BOARD_URL}/pending/${encodeURIComponent(AGENT)}`);
    const list = (j && j.notices) || [];
    return {
        notices: Array.isArray(list) ? list.filter((n) => n && n.text) : [],
        leaseToken: j && typeof j.lease_token === "string" ? j.lease_token : null,
    };
}

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
            } catch {   }
        }
        child.stdin.write(line + "\n");
    }
});
process.stdin.on("end", () => child.stdin.end());

let outBuf = "";
// Preserve upstream response order while each notice fetch and acknowledgement runs.
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
    try { msg = JSON.parse(line); } catch {   }

    const isToolCall = msg && msg.id != null && methodById.get(msg.id) === "tools/call";
    if (msg && msg.id != null) methodById.delete(msg.id);

    if (!isToolCall) return void process.stdout.write(line + "\n");

    // Pass protocol responses and errors without MCP content through unchanged.
    if (!Array.isArray(msg.result && msg.result.content)) return void process.stdout.write(line + "\n");

    let pending = { notices: [], leaseToken: null };
    try { pending = await fetchPending(); } catch (e) { log("drain failed:", e.message); }
    const notices = pending.notices;

    if (!notices.length) return void process.stdout.write(line + "\n");

    let out = null;
    try { out = withNotices(msg, notices); } catch (e) { log("append failed:", e.message); }
    if (out == null) return void process.stdout.write(line + "\n");

    process.stdout.write(out + "\n");
    // Acknowledge only after emitting the augmented result; failures can redeliver.
    await reportShown(notices, pending.leaseToken);
}
