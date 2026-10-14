/**
 * state.js — the sim agent's durable memory.
 *
 * WHY A FILE AND NOT MEMORY
 * acp-bridge.py spawns a FRESH child per socket connection, so every router
 * reconnect gives the sim a new process. Holding the processed-event_id set in
 * memory would mean a reconnect silently resets it — and UEM delivery is
 * at-least-once, so redelivery across a reconnect is the exact case an agent
 * must survive. It is also the case a memory-only sim would appear to pass.
 *
 * Same reasoning for the turn budget: it is the run's success condition, so it
 * must not reset when a socket blips.
 *
 * Writes are atomic (tmp + rename) because N agents share a bind-mounted volume
 * and a torn read on restart would look like lost dedup state.
 */
import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const EMPTY = { turnsUsed: 0, seenEventIds: [], claimed: false, prCount: 0, mergeCount: 0 };

export class SimState {
  constructor({ dir, agent }) {
    // Empty is absent: compose renders unset optional vars as "", and an empty
    // dir would resolve every agent's state file to the process cwd.
    const fromEnv = String(process.env.SIM_STATE_DIR ?? "").trim();
    this.dir = dir || fromEnv || defaultDir();
    this.agent = agent;
    this.path = join(this.dir, `${sanitize(agent)}.json`);
    this.data = this.#load();
    // Set is the working form; the file keeps an array.
    this.seen = new Set(this.data.seenEventIds);
  }

  #load() {
    try {
      return { ...EMPTY, ...JSON.parse(readFileSync(this.path, "utf8")) };
    } catch {
      return { ...EMPTY };
    }
  }

  save() {
    try {
      mkdirSync(this.dir, { recursive: true });
      const tmp = `${this.path}.tmp`;
      writeFileSync(tmp, JSON.stringify({ ...this.data, seenEventIds: [...this.seen] }));
      renameSync(tmp, this.path);
    } catch (e) {
      process.stderr.write(`[sim-agent] state save failed (continuing): ${e?.message ?? e}\n`);
    }
  }

  /** True if this event_id was already processed. Records it either way. */
  isDuplicate(eventId) {
    if (!eventId) return false;
    if (this.seen.has(eventId)) return true;
    this.seen.add(eventId);
    return false;
  }

  get turnsUsed() { return this.data.turnsUsed; }
  get claimed() { return this.data.claimed; }
  get prCount() { return this.data.prCount; }
  get mergeCount() { return this.data.mergeCount ?? 0; }

  countTurn() { this.data.turnsUsed += 1; }
  markClaimed() { this.data.claimed = true; }
  countPr() { this.data.prCount += 1; }
  countMerge() { this.data.mergeCount = (this.data.mergeCount ?? 0) + 1; }
}

function defaultDir() {
  // /opt/data is the bind-mounted per-agent volume in compose; fall back to tmp
  // so the unit test (no container) works unchanged.
  try {
    mkdirSync("/opt/data/sim", { recursive: true });
    return "/opt/data/sim";
  } catch {
    return join(tmpdir(), "sim-agent-state");
  }
}

function sanitize(name) {
  return String(name || "agent").replace(/[^A-Za-z0-9._-]/g, "_");
}
