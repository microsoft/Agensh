# omcgitea Testing Document

> Companion: `REQUIREMENTS.md`, `DESIGN.md`, `DESIGN_R7_SIDECAR.md`, `INTERFACE.md`
> Test stack: **TypeScript + vitest** (Node 20.10+) for the sidecar/contract layer,
> **bash + python3** for the ProgramBench layer.

This snapshot carries the two suites the ProgramBench 1-team sweep 6.11 arm depends on:
`tests/f8_sidecar/` (delivery-layer correctness) and `tests/pbench/` + `tests/pbench-board/`
(benchmark harness correctness). The pre-R7 suites (F2–F7, F9) and the `router/` unit tests are
gone along with the code they covered.

---

## 0. General Principles

### 0.1 Real Tests

The hard requirements — real containers, real HTTP, real tokens, real git, real MCP, and the
**one** mocking exemption (the external LLM API) — are stated in **CLAUDE.md** ("Hard Requirements
for Real Tests"). They are not restated here. Every suite below obeys them: the sidecar tests run
against a real MySQL / real socat ACP socket, the pbench tests parse real `docker compose config`
output, real generator stdout, real tar archives and real git repos.

### 0.2 Repeatability

- vitest `globalSetup` (`tests/setup.ts`) brings the cluster up once per run and tears it down at
  the end; single worker, serial (`fileParallelism:false` + `singleFork:true`).
- `make clean PROFILE=<p>` wipes only that profile's data dir.
- A test run must leave behind no container / network / volume outside this project's
  `omcgitea-<profile>` project name.

### 0.3 Layering

| Layer | Where | Real container | Speed |
|---|---|---|---|
| Pure logic (state machine, template render, config parse, UEM mapping) | `tests/f8_sidecar/*.test.ts` (unit half) | No | seconds |
| Sidecar integration (MySQL events, ACP socket, secret-service, SSE, Mattermost WS) | `tests/f8_sidecar/*.test.ts` (integration half) | Yes | tens of seconds |
| Harness contract (topology, isolation, export, gates, memory, reboot) | `tests/pbench/*.sh` + `*.test.ts` | Partly | seconds–minutes |
| Board | `tests/pbench-board/` | Yes (throwaway MySQL) | tens of seconds |

---

## 1. `tests/f8_sidecar/` — delivery layer (R7)

Covers the components in [`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md).

| File | Content |
|---|---|
| `mysql_events.test.ts` | central `events` / `cursors` / `acp_sessions` CRUD; `(dedup_key, agent)` idempotence; ingest + cursor advance in one transaction |
| `dispatcher.test.ts` | pending→sending→{sent,failed,cancelled}; at-most-once; per-agent serial; same-agent batch merge; watchdog → `cancelled` + auto-continue |
| `acp_socket_channel.test.ts` | ACP over unix socket: new_session / load_session / prompt; `sessionUpdate` stream surfaced to caller; no-update timeout → `cancel(sessionId)` |
| `acp_socket_stress.test.ts` / `stress.test.ts` | socket channel under concurrent load; no interleaved-frame corruption |
| `bridge.test.ts` | the socat-forked `acp_adapter.entry` bridge inside the agent container |
| `fetcher.test.ts` | REST pull: URL construction / PAT header / cursor advance |
| `listener.test.ts` | pollOnce composition; errors do not pollute the cursor; wake-driven, no polling fallback |
| `sse.test.ts` | SSE driver: connected / reconnects / lastFrameAt metrics; watchdog reconnect |
| `form_auth.test.ts` | `GiteaFormAuth` two-step handshake / cache / concurrent coalescing / failure breaker |
| `secret_service.test.ts` | `GET /tokens/<agent>` protocol + auth + sidecar-side cache |
| `uem.test.ts` | Gitea notification → UEM field mapping ([`UEM.md`](./UEM.md)) |
| `mattermost_listener.test.ts` / `mattermost_ws.test.ts` / `mattermost_notification.test.ts` | the Mattermost inbound path alongside Gitea |
| `board_forcing.test.ts` / `board_unreachable.test.ts` | shared context board injected into dispatch; degradation when board-service is down |
| `step_loop.test.ts` / `step_policies.test.ts` | the step/remind loop and its policies |
| `workspace_probe.test.ts` | agent workspace probing |
| `dev_stack_smoke.test.ts` | dev stack comes up and the pod pair is healthy |

Run: `cd tests && pnpm install && pnpm test:sidecar`

## 2. `tests/pbench/` — ProgramBench harness contract

| File | Asserts |
|---|---|
| `test_gen_topology.sh` | `tools/gen-compose-prod.py` renders any team size from env (default 37); anti-cheat `/opt/pbench/executable` mount survives downsizing; bootstrap `AGENTS`/`ROLES` match the roster; Makefile wires the per-profile dynamic base |
| `test_compose_netlock.sh` | the org-pbench network-cutoff overlay holds up under real `docker compose config` |
| `test_net_isolation.sh` | real containers + real docker networks: the agent cannot reach the public internet (no `git clone` of the upstream project) but can still reach what it needs |
| `test_bin_isolation.sh` | env-gated privilege drop in `acp-bridge.py`: the agent can **run** the reference binary but not **read** its bytes (`root:root` + 0111 mount) |
| `test_role_fragments.sh` | every 1-team role defines all six prompt fragments `entrypoint.sh` reads unconditionally |
| `test_submission_export.sh` | real git repo + real tar: the exported `submission.tar.gz` is what ProgramBench's `copy_in_tar` expects |
| `test_export_resilience.sh` | a **failed** export must never be mistaken for a score (sweep 6.11 lost 2 of 4 completed tasks to this) |
| `test_test_gate.sh` / `test_gate_feedback.sh` | the CI test gate is wired end to end; the merge gate tells a worker which cases it broke and grades both sides on the same current suite |
| `test_memory_ceiling.sh` | benchmark work cannot take the machine down (sweep 6.10 died on 11 machine-wide OOM kills) |
| `test_reboot_guard.sh` | a reboot never leaves stacks running headless (sweep 6.11 was cut by a maintenance reboot ~9h in) |
| `test_mm_ids.sh` | agents are told their Mattermost team and task-channel ids |
| `test_remind_loop.sh` | against a **live** profile: the real `pbench-task` channel actually received ≥1 director progress-check post |
| `test_compaction_reinject.sh` | the router can detect a context compaction and put back what it dropped (mechanism retained; `reinjectAfterCompaction` defaults **false**) |
| `test_traj_metrics.sh` | `scripts/pbench_traj_metrics.sh` agrees with ground truth the test computes itself (no rotting golden values) |
| `test_llm_backend.sh` | functional smoke against the real configured backend: endpoint alive, key usable, the model the agent actually requests is available |
| `test_env.sh` | `.env.org-pbench` shape: egress routed through the in-cluster proxy, upstream pinned, required secrets present |
| `agent_image.test.ts` | the agent image contains what the run needs |
| `network_subnets.test.ts` | per-profile subnets do not collide (parallel profiles on one host) |
| `dispatcher_serial.test.ts` | dispatch stays serial per agent under the 1-team topology |
| `runner_deadline.test.ts` | the runner honours its wall-clock deadline |

Run: `bash tests/pbench/<name>.sh`, or `cd tests && pnpm test:pbench` for the vitest files.

**Needs a live stack / filled-in env**: `test_env.sh`, `test_llm_backend.sh`, `test_remind_loop.sh`,
`test_net_isolation.sh`, `test_bin_isolation.sh`. The rest are static/offline and run from a clean
checkout.

## 3. `tests/pbench-board/` — shared context board

- `test_board_service.sh` — end-to-end against a real throwaway MySQL + board-service (both images
  built by this repo): a battery of real curl requests over the verifier + windowing logic.
- `test_full_board.py` — a dispatch must carry the **whole** board, not a window (measured on sweep
  6.3: 91 overlap incidents across 20 tasks, 169,566 wasted tokens).

---

## 4. Run Conventions

### 4.1 Entry

```
cd tests && pnpm install
pnpm test:unit         # pure-logic subset
pnpm test:sidecar      # tests/f8_sidecar/
pnpm test:pbench       # tests/pbench/*.test.ts
pnpm typecheck

bash tests/pbench/<name>.sh          # harness contract tests
bash tests/pbench-board/test_board_service.sh
python3 tests/pbench-board/test_full_board.py
```

Stack lifecycle is `make up / down / clean PROFILE=<p>` (see `Makefile`); there are no
`make test-*` targets — the suites are invoked directly.

### 4.2 Environment Switches

| Env | Purpose |
|---|---|
| `OMC_TEST_PROFILE` | Which profile the cluster fixtures target |
| `OMC_TEST_NO_UP=1` | Skip `make up` (assumes the cluster is already started) |
| `OMC_TEST_KEEP_UP=1` | Skip teardown `make down` |
| `OMC_TEST_DEBUG=1` | Print `isClusterUp` on each probe |
| `OMC_TEST_ARTIFACTS_KEEP=N` | `tests/_artifacts/` keeps N copies (default 10) |
| `PBENCH_TEAMS` / `PBENCH_WORKERS_PER_TEAM` / `PBENCH_AUDITOR` | Roster knobs read by `test_gen_topology.sh` (and by the generator itself) |
| `PROFILE` | Live-stack tests (`test_remind_loop.sh`, `test_env.sh`) pick their `.env.<profile>` from this |

### 4.3 Fixtures

- `tests/lib/cluster.ts` — up/down/probe around `make`
- `tests/lib/context.ts:makeContext()` — `gitea` anonymous / `giteaAdmin` (admin.token) /
  `giteaAgents: Map<name, GiteaClient>`, all through nginx-edge
- `tests/lib/tokens.ts` — reads the 0700-root token dir via `sudo cat` / `sudo stat`
- `tests/lib/env.ts` — `.env.<profile>` parsing
- `tests/lib/artifacts.ts:dumpArtifacts` — on failure dumps `compose ps` + per-service logs
  (last 500 lines) + token **file names** (never contents), keeping the last N runs

---

## 5. Acceptance Correspondence

| ID | Requirement (REQUIREMENTS §9) | Covered by |
|---|---|---|
| V2 | Events arrive at the right agent in real time | `f8_sidecar/{listener,sse,dispatcher,acp_socket_channel}.test.ts` |
| V9 | No loss on destroy | `f8_sidecar/mysql_events.test.ts` (persistence + dedup on replay) |
| V10 | Do not touch upstream | no patch/fork in tree; agent image only `FROM` + `COPY` |
| V11 | Doc self-consistency | manual review of `v2docs/` |

Requirements V1 / V3 / V4 / V5–V8 were verified by the M1/M2 e2e suites, which are not part of this
snapshot; the benchmark harness exercises the same PR → review → merge loop in production instead.
