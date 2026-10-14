/**
 * policy.js — what the sim agent DOES with a turn.
 *
 * No model. A deterministic work cycle that touches all three surfaces every
 * productive turn, because the three have different failure modes and different
 * shares of real tool traffic (roughly gitea 24%, board 15%, mattermost 6%).
 * A sim that skipped one would leave
 * that share untested, which defeats the purpose.
 *
 * The cycle mirrors the six steps of the prompt's work cycle:
 *   probe → CLAIM → build in isolation → check → push/PR/merge → PATCH_SUMMARY
 *
 * ARGUMENT BUILDING IS SCHEMA-DRIVEN. gitea-mcp and the mattermost server are
 * upstream binaries behind the CLAUDE.md veto line; their tool names and arg
 * names are not ours to pin, and hardcoding a guess would produce a sim that
 * fails in a way that looks like a harness bug. So the sim reads each tool's
 * advertised inputSchema and fills the properties it recognises. What it cannot
 * fill, it reports as a failed tool call rather than inventing.
 */
import { SimState } from "./state.js";

/**
 * Read a numeric env var, treating EMPTY as absent.
 *
 * compose renders unset knobs as `""` (the `${VAR:-}` form used for every
 * optional agent var), and `Number("")` is 0 — which would silently give every
 * agent a zero turn budget: a run where nothing happens, nothing errors, and
 * every artifact is empty. `??` alone does not catch it because "" is not
 * nullish.
 */
function envNum(name, fallback) {
  const raw = process.env[name];
  if (raw === undefined || raw === null || String(raw).trim() === "") return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

function envStr(name, fallback = "") {
  const raw = process.env[name];
  return raw === undefined || raw === null || String(raw).trim() === "" ? fallback : String(raw).trim();
}

const AGENT = envStr("AGENT_NAME", "sim-agent");
const ORG = envStr("GITEA_ORG", "pbench");
const REPO = envStr("SIM_REPO", envStr("REPOS", "main").split(",")[0].trim() || "main");
const BOARD_ID = envStr("BOARD_QUEUE_ID", envStr("BOARD_IDS", "pbench-top").split(",")[0].trim() || "pbench-top");
const MAX_TURNS = envNum("PBENCH_SIM_TURNS", 4);
const THINK_MS = envNum("PBENCH_SIM_THINK_MS", 250);
// How long to wait for a required status check before attempting the merge.
// 0 disables the wait (useful to reproduce the raw 405 behaviour).
const CI_WAIT_MS = envNum("PBENCH_SIM_CI_WAIT_MS", 60_000);
const CI_POLL_MS = envNum("PBENCH_SIM_CI_POLL_MS", 2_000);
const SEED = envStr("PBENCH_SIM_SEED", "");

// PER-SERVER REQUEST RATE, in requests per minute PER AGENT.
//
// THINK_MS paces an agent against itself; it says nothing about the load a
// FLEET puts on one service. For a scale test the quantity that matters is the
// aggregate one service sees -- 1000 agents at 1 rpm is ~17 req/s against
// gitea, which is write-heavy and is therefore what decides whether sqlite or
// mysql belongs behind it. Expressing the target directly makes the
// experiment's input a number you can state rather than one inferred from a
// sleep. 0 (the default) is unpaced, so existing sim runs are unchanged.
const RPM = {
  gitea: envNum("PBENCH_SIM_GITEA_RPM", 0),
  mattermost: envNum("PBENCH_SIM_MM_RPM", 0),
  board: envNum("PBENCH_SIM_BOARD_RPM", 0),
};
// One gate PER SERVER, not one shared gate: gitea at 1 rpm must not throttle
// mattermost at 0.2 rpm.
const _nextSlot = { gitea: 0, mattermost: 0, board: 0 };

/** Wait until this agent's next slot for `server`. No-op when unpaced. */
async function rateGate(server) {
  const rpm = RPM[server] || 0;
  if (rpm <= 0) return;
  const spacing = 60_000 / rpm;
  const now = Date.now();
  const at = Math.max(now, _nextSlot[server] || 0);
  _nextSlot[server] = at + spacing;
  if (at > now) await sleep(at - now);
}

/** Deterministic unless PBENCH_SIM_SEED is set; then reproducibly jittered. */
function makeJitter(seed) {
  if (!seed) return () => 0;
  let s = 0;
  const key = `${seed}:${AGENT}`;
  for (let i = 0; i < key.length; i++) s = (s * 31 + key.charCodeAt(i)) >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return (s % 1000); // 0..999 ms
  };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Pull every event_id out of a rendered UEM prompt. Handles both the single and
 * the [event-batch] form (mini-router/src/uem_render.ts), and tolerates the
 * board block the dispatcher splices in front (forced read).
 */
export function parseEventIds(text) {
  const ids = [];
  for (const m of String(text ?? "").matchAll(/^event_id=(.+)$/gm)) {
    const id = m[1].trim();
    if (id) ids.push(id);
  }
  return ids;
}

/** Fill a tool's advertised inputSchema from a value bag. */
function buildArgs(server, toolName, bag) {
  const tool = server.tools.find((t) => t.name === toolName);
  const props = tool?.inputSchema?.properties ?? {};
  const required = tool?.inputSchema?.required ?? [];
  const args = {};
  for (const key of Object.keys(props)) {
    if (key in bag && bag[key] !== undefined && bag[key] !== null) args[key] = bag[key];
  }
  const missing = required.filter((k) => !(k in args));
  return { args, missing, known: Boolean(tool) };
}

export class SimPolicy {
  constructor({ mcp, log = () => {} }) {
    this.mcp = mcp;
    this.log = log;
    this.state = new SimState({ agent: AGENT });
    this.jitter = makeJitter(SEED);
    // Mattermost ids are discovered once per process and cached: rediscovering
    // them every turn would trade a realistic behaviour for pure API noise.
    this.teamId = null;
    this.channelId = null;
  }

  /**
   * One ACP turn. Returns {stopReason} and reports every attempted tool call
   * through `emit` so the router's TurnObserver builds a real TurnSummary.
   */
  async handlePrompt(text, emit) {
    const ids = parseEventIds(text);

    // UEM transport is at-least-once; dedup is the AGENT's job.
    // A batch counts as fresh if it carries at least one unseen event.
    const fresh = ids.filter((id) => !this.state.isDuplicate(id));
    if (ids.length > 0 && fresh.length === 0) {
      this.state.save();
      emit.message(`already processed ${ids.length} event(s): ${ids.join(", ")} — no action`);
      return { stopReason: "end_turn" };
    }

    if (this.state.turnsUsed >= MAX_TURNS) {
      this.state.save();
      emit.message(`turn budget spent (${this.state.turnsUsed}/${MAX_TURNS}); idle`);
      return { stopReason: "end_turn" };
    }

    const n = this.state.turnsUsed + 1;
    this.state.countTurn();
    emit.message(`sim turn ${n}/${MAX_TURNS} for ${AGENT}; ${fresh.length} new event(s)`);

    const notes = [];
    // Order matters: read the board first (what peers did), then do the work,
    // then tell everyone. Same shape as the prompt's six steps.
    notes.push(await this.#boardRead(emit));
    if (!this.state.claimed) notes.push(await this.#boardClaim(emit, n));
    notes.push(await this.#giteaCycle(emit, n));
    notes.push(await this.#boardPatchSummary(emit, n));
    notes.push(await this.#mattermost(emit, n));
    if (n % 2 === 0) notes.push(await this.#boardGrep(emit));

    this.state.save();
    emit.message(notes.filter(Boolean).join("; "));
    return { stopReason: "end_turn" };
  }

  /** Run one MCP call as a reported tool call. Never throws. Returns the result or null. */
  async #step(emit, title, serverName, candidates, bag) {
    const id = emit.toolCall(title, "other");
    // Gate BEFORE the think delay so the configured rpm is the rate the service
    // actually sees, not that rate plus THINK_MS of drift.
    await rateGate(serverName);
    await sleep(THINK_MS + this.jitter());
    const server = this.mcp.server(serverName);
    if (!server?.available) {
      emit.toolResult(id, "failed", `${serverName} unavailable`);
      return null;
    }
    const toolName = server.findTool(candidates);
    if (!toolName) {
      emit.toolResult(id, "failed", `no tool matching ${candidates.join("|")} on ${serverName}`);
      return null;
    }
    const { args, missing } = buildArgs(server, toolName, bag);
    if (missing.length) {
      // Honest failure: the upstream schema wants something the sim has no value
      // for. Better a reported failure than an invented argument.
      emit.toolResult(id, "failed", `${toolName}: cannot fill required ${missing.join(",")}`);
      return null;
    }
    const res = await this.mcp.call(serverName, [toolName], args);
    emit.toolResult(id, res.ok ? "completed" : "failed", `${toolName}: ${(res.text || "").slice(0, 400)}`);
    if (!res.ok) {
      // To stderr as well as into the ACP stream. The router truncates its RX
      // log at ~200 chars, so a failure whose cause is in the tail of the
      // message is invisible in `docker logs mini-router-*` — which is where
      // anyone debugging a sim run looks first. Include the args: nearly every
      // failure here is a wrong or missing argument against an upstream schema.
      this.log(`TOOL FAIL ${serverName}.${toolName} args=${JSON.stringify(args)} -> ${res.text}`);
    }
    return res.ok ? res : null;
  }

  /** Best-effort JSON out of an MCP text result. */
  #json(res) {
    if (!res?.text) return null;
    try { return JSON.parse(res.text); } catch { /* fall through */ }
    const m = res.text.match(/\{[\s\S]*\}/);
    if (m) { try { return JSON.parse(m[0]); } catch { /* */ } }
    return null;
  }

  async #boardRead(emit) {
    const r = await this.#step(emit, "board_read", "board", ["board_read"], { board_id: BOARD_ID });
    return r ? "board read" : "board read failed";
  }

  /**
   * board_write, with ADMISSION CHECKED.
   *
   * mcp-board only throws on 5xx (index.js:180): the board's deterministic
   * verifier rejects a malformed gist with HTTP 200 and
   * {"status":"rejected","reason":...}. So a note that never reached the board
   * looks exactly like a successful write to any caller that only checks
   * transport — which is how a sim could report a healthy board surface while
   * publishing nothing. Treat anything but "admitted" as a failed tool call and
   * surface the reason.
   */
  async #boardWrite(emit, title, fields) {
    const id = emit.toolCall(title, "other");
    await rateGate("board");
    await sleep(THINK_MS + this.jitter());
    const server = this.mcp.server("board");
    if (!server?.available) { emit.toolResult(id, "failed", "board unavailable"); return false; }
    const res = await this.mcp.call("board", ["board_write"], { board_id: BOARD_ID, ...fields });
    const verdict = this.#json(res);
    const admitted = res.ok && String(verdict?.status ?? "").toLowerCase() === "admitted";
    emit.toolResult(id, admitted ? "completed" : "failed", `board_write ${fields.type}: ${(res.text || "").slice(0, 300)}`);
    if (!admitted) {
      this.log(`BOARD REJECTED ${fields.type} content=${JSON.stringify(fields.content)} -> ${res.text}`);
    }
    return admitted;
  }

  async #boardClaim(emit, n) {
    // CLAIM caps at 100 chars (mcp-board verifier).
    const ok = await this.#boardWrite(emit, "board_write CLAIM", {
      type: "CLAIM",
      content: `claiming sim area ${AGENT} #${n}`.slice(0, 100),
      delegation_id: `sim-${AGENT}`,
    });
    if (ok) this.state.markClaimed();
    return ok ? "claimed" : "claim rejected";
  }

  async #boardPatchSummary(emit, n) {
    // The verifier requires "files=A | idea=B | evidence=C | risk=D" and rejects
    // tbd/pending/unverified as evidence, so the evidence must name something
    // that actually happened.
    const content =
      `files=src/sim/${AGENT}-${n}.txt | idea=sim work cycle turn ${n} | ` +
      `evidence=${this.state.prCount} PRs opened, ${this.state.mergeCount} merged by ${AGENT} | ` +
      `risk=none, simulated commit`;
    const ok = await this.#boardWrite(emit, "board_write PATCH_SUMMARY", {
      type: "PATCH_SUMMARY",
      content: content.slice(0, 300),
      delegation_id: `sim-${AGENT}`,
    });
    return ok ? "patch summary posted" : "patch summary rejected";
  }

  async #boardGrep(emit) {
    const r = await this.#step(emit, "board_grep", "board", ["board_grep"], {
      board_id: BOARD_ID,
      words: "sim",
    });
    return r ? "board grepped" : "board grep failed";
  }

  /**
   * gitea: read the task issue, branch, commit, PR, merge, comment.
   *
   * gitea-mcp exposes a MODE-BASED api — `pull_request_write{method:"create"|"merge"}`,
   * `issue_write{method:"add_comment"}` — not one tool per verb, so the tool
   * name alone does not identify the operation. Arg names come from each tool's
   * advertised inputSchema (buildArgs drops anything not advertised), so this
   * survives an upstream rename of a field we do not use.
   *
   * Every step is independent. A 405 on merge (block_on_outdated_branch, which
   * refuses most merges at 16 workers) must be RECORDED, not
   * fatal, exactly as a real worker experiences it.
   */
  async #giteaCycle(emit, n) {
    const branch = `sim/${AGENT}-${n}`;
    const path = `src/sim/${AGENT}-${n}.txt`;
    const base = { owner: ORG, repo: REPO };

    await this.#step(emit, "gitea read issue #1", "gitea", ["issue_read"], {
      ...base, method: "get", issue_number: 1,
    });

    await this.#step(emit, "gitea create branch", "gitea", ["create_branch"], {
      ...base, branch, old_branch: "main",
    });

    await this.#step(emit, "gitea commit file", "gitea", ["create_or_update_file"], {
      ...base, path, branch_name: branch,
      content: `sim ${AGENT} turn ${n} at ${new Date().toISOString()}\n`,
      message: `sim: ${AGENT} turn ${n}`,
    });

    const pr = await this.#step(emit, "gitea open PR", "gitea", ["pull_request_write"], {
      ...base, method: "create", head: branch, base: "main",
      title: `sim: ${AGENT} turn ${n}`,
      body: `Refs #1\n\nSimulated change ${n} from ${AGENT}.`,
    });
    if (pr) this.state.countPr();

    const prNum = Number(this.#json(pr)?.number ?? NaN);
    if (Number.isFinite(prNum)) {
      // WAIT FOR CI BEFORE MERGING. With PBENCH_CI_GATE=1 the branch carries a
      // required status context, and gitea answers 405 to a merge whose
      // required check has not reported yet. The sim opens a PR and would
      // otherwise merge ~1s later, while the check is still "pending" — a real
      // worker takes minutes per turn, so CI has always reported by the time it
      // merges. Without this the sim measures its own speed, not the gate.
      //
      // The wait itself is the interesting number: it IS the CI queue depth,
      // which is what act_runner's per-stack capacity bounds. Logged for that
      // reason.
      const waited = await this.#awaitChecks(emit, prNum);

      // Whether this succeeds or returns 405 is the measurement: N peers racing
      // the same `main` is where merge contention actually shows up.
      const merged = await this.#step(emit, "gitea merge PR", "gitea", ["pull_request_write"], {
        ...base, method: "merge", pull_number: prNum, merge_style: "merge",
      });
      if (merged) this.state.countMerge();
      this.log(`PR #${prNum} ci_wait_ms=${waited} merged=${Boolean(merged)}`);
      await this.#step(emit, "gitea comment on issue", "gitea", ["issue_write"], {
        ...base, method: "add_comment", issue_number: 1,
        body: `${AGENT}: PR #${prNum} for turn ${n} (${merged ? "merged" : "merge refused"})`,
      });
      return `PR #${prNum} ${merged ? "merged" : "open (merge refused)"}`;
    }
    return pr ? "PR opened (number not parsed)" : "PR failed";
  }

  /**
   * Poll the PR's combined status until it leaves "pending", bounded.
   * Returns ms waited. A gate that never reports is itself a finding, so this
   * gives up rather than blocking the turn forever.
   */
  async #awaitChecks(emit, prNum) {
    if (CI_WAIT_MS <= 0) return 0;
    const id = emit.toolCall("gitea await CI", "other");
    const started = Date.now();
    let last = "unknown";
    while (Date.now() - started < CI_WAIT_MS) {
      // Each poll is a gitea request, so it takes a gitea slot like #step does.
      await rateGate("gitea");
      const res = await this.mcp.call("gitea", ["pull_request_read"], {
        method: "get_status", owner: ORG, repo: REPO, pull_number: prNum,
      });
      const j = this.#json(res);
      // gitea reports either a combined {status|state} or a list of contexts.
      last = String(j?.status ?? j?.state ?? (Array.isArray(j) ? j[0]?.status : "") ?? "unknown");
      if (last && last !== "pending" && last !== "unknown") break;
      await sleep(CI_POLL_MS);
    }
    const waited = Date.now() - started;
    emit.toolResult(id, "completed", `checks=${last} after ${waited}ms`);
    return waited;
  }

  /**
   * mattermost: discover ids, post to the task channel, DM a peer.
   *
   * The ids are DISCOVERED, not assumed. Every team-scoped tool needs a team_id
   * the agent must find, and the runner's own comments record what happens when
   * that discovery fails: agents invent 26-char ids, mattermost answers 403, and
   * workers read that as a lockout and go silent. A sim
   * that took the ids from env would skip the exact step that breaks.
   */
  async #mattermost(emit, n) {
    if (!this.teamId) {
      const teams = await this.#step(emit, "mattermost list teams", "mattermost", ["list_teams"], {});
      const arr = this.#json(teams);
      const list = Array.isArray(arr) ? arr : (arr?.teams ?? []);
      this.teamId = list.find((t) => t?.name === ORG)?.id ?? list[0]?.id ?? null;
    }
    if (!this.teamId) return "mm: no team id";

    if (!this.channelId) {
      const ch = await this.#step(emit, "mattermost find task channel", "mattermost", ["get_channel_by_name"], {
        team_id: this.teamId, channel_name: "pbench-task",
      });
      this.channelId = this.#json(ch)?.id ?? null;
    }
    if (!this.channelId) return "mm: no task channel";

    await this.#step(emit, "mattermost read channel", "mattermost", ["get_channel_messages"], {
      channel_id: this.channelId, per_page: 20,
    });

    const posted = await this.#step(emit, "mattermost post status", "mattermost", ["post_message"], {
      channel_id: this.channelId,
      message: `${AGENT}: sim turn ${n} done (${this.state.prCount} PRs, ${this.state.mergeCount} merged)`,
    });

    // DM a peer: the fast-queue notice path only carries traffic if someone
    // actually sends a DM; real agents open DM channels far more often than
    // they read one.
    const peer = this.#peerName();
    if (peer) {
      const me = this.#json(await this.#step(emit, "mattermost get_me", "mattermost", ["get_me"], {}));
      const them = this.#json(await this.#step(emit, "mattermost find peer", "mattermost", ["get_user_by_username"], {
        username: peer,
      }));
      if (me?.id && them?.id) {
        const dm = this.#json(await this.#step(emit, "mattermost open DM", "mattermost", ["create_direct_channel"], {
          user_id_1: me.id, user_id_2: them.id,
        }));
        if (dm?.id) {
          await this.#step(emit, "mattermost DM peer", "mattermost", ["post_message"], {
            channel_id: dm.id, message: `${AGENT} -> ${peer}: turn ${n}, area claimed`,
          });
        }
      }
    }
    return posted ? "mm posted" : "mm post failed";
  }

  /** The next worker in the ring, so DMs fan out instead of all hitting worker1. */
  #peerName() {
    const m = AGENT.match(/^(.*worker)(\d+)$/);
    if (!m) return null;
    const idx = Number(m[2]);
    const total = envNum("PBENCH_WORKERS_PER_TEAM", 4);
    return `${m[1]}${(idx % total) + 1}`;
  }
}
