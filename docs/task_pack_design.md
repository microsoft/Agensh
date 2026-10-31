# Task packs: separating ProgramBench from the team harness

Status: draft for discussion. Branch: `task-pack-decoupling`.

## Goals

- Keep the peer cooperation loop (Gitea workspace, Mattermost messaging,
  shared context board, per-worker router, harness adapters) as a task-neutral
  core.
- Move everything ProgramBench-specific into a **task pack** that plugs into
  that core through a small, explicit contract.
- Make the core usable as a **development tool for real software projects**:
  improving an existing repository or building a new one from a specification,
  with an optional human product owner.
- Keep ProgramBench runs reproducible. The `programbench` pack is the
  regression baseline for every refactoring step.
- Land the work upstream in `microsoft/Agensh` as a series of reviewable pull
  requests.

## Non-goals (for now)

- Multi-node or Kubernetes orchestration. The release remains single-node Compose.
- Hosts other than GitHub for delivery. The finalize hook is pluggable, so GitLab
  and others can follow.
- Tuning for 1,024-worker teams. Large teams must keep working, but defaults
  target **4–16 workers**.
- Rewriting the board, router, secret service or harness adapters.
- More than one human product owner per project.

## Current coupling inventory

The core services are already almost task-neutral. ProgramBench coupling sits in
the outer layers:

| Area | Where | Coupling |
|---|---|---|
| Collaboration prompt | `prompts/agents.txt` | Work cycle steps 1–6 run `/opt/pbench/executable`; grader note about `argv[0]`; channel `pbench-task`; `PBENCH_WORKERS` |
| Task prompts | `prompts/pbench_brief.txt`, `task_brief.txt`, `idle.txt`, `idle_delivery.txt`, `deadline_*.txt` | ProgramBench objective, offline rules, `compile.sh` contract |
| Worker image | `agent/Dockerfile` | `FROM ${TASK_IMAGE}`: workers are built on the cleanroom image, one image per task |
| Compose | `tools/gen_compose_prod.py`, `docker/docker_compose.pbench.yml` | Reference binary mount, brief mount, internal-only network, `pbench.slice`, board id `pbench-top` |
| Model proxy policy | `docker/docker_compose.pbench.yml` | `request_user_input` disabled (fully autonomous) |
| Run lifecycle | `scripts/pbench_run.sh` | Generic drive logic (kickoff, staggered wake, idle watchdog, reminders, quiesce, archive) mixed with cleanroom seeding, submission export and `programbench eval` |
| Sequencing and scoring | `scripts/pbench_chain.sh`, `scripts/lib_launch.sh`, `scripts/launch_single_node.sh` | Cleanroom image checks, evaluator invocation, score reporting |
| Profiles | `scripts/pbench_gen_env.sh`, `Makefile` | Hard-coded `TASK_TABLE` drives ports/subnets; profile names must match `pbench-single-node-*` |
| Tools | `tools/pbench_submission.py`, `tools/pbench_score_report.py`, `scripts/pbench_docker_sudo.sh`, `scripts/lib_pbench_images.sh`, `scripts/pbench_build_pertask_images.sh` | Entirely ProgramBench |
| Baseline | `scripts/launch_single_agent.py`, `scripts/acp_driver.py`, `prompts/single-agent/` | Entirely ProgramBench |
| Naming | everywhere | `PBENCH_*` variables, `ORG_NAME=pbench`, `~/.pbench-upstream.env`, `/opt/pbench` |
| Router | `mini-router/src/uem_render.ts` | `PBENCH_RUN_START_MS` only (generic meaning: run start time) |

## Concepts

- **Core**: the cooperation infrastructure plus a task-neutral run lifecycle.
- **Task pack** (`tasks/<pack>/`): a reusable kind of work. A pack provides
  prompts, defaults and hooks. Two packs are planned:
  - `programbench`: today's experiments, kept reproducible.
  - `software-project`: real projects, starting from an existing repository or
    from an empty one with a specification.
- **Project**: one concrete instance of a pack, such as "improve repo X" or
  "ProgramBench task `jgm__pandoc.5caad90`".
- **Run**: one execution of a project. Real projects can pause and resume;
  benchmark runs are one-shot.

## Configuration

Configuration files use TOML. Python 3.11, already required by the release,
reads it with the standard library `tomllib`, so the host needs no new
dependency.

A pack supplies defaults and hooks in `tasks/<pack>/pack.toml`. A project file
overrides only the fields marked *project* below; the core rejects any other
field in a project file. Real projects keep their project file in the target
repository at `.agensh/project.toml`. Benchmark runs generate project files from
the pack (for example, one per ProgramBench task).

| Field | Set by | Meaning |
|---|---|---|
| `workspace.prepare` | pack | Hook that produces the initial repository tree |
| `workspace.seed` | project | `git` (import an upstream repository) or `empty` |
| `upstream.repo`, `upstream.base_branch`, `upstream.delivery_branch` | project | GitHub repository and branches for import, sync and delivery |
| `goal` | project | Path to a goal or specification document, or an inline string |
| `environment.base_image` | pack, project | `default-<language>`, `devcontainer` or an image reference |
| `environment.mounts` | pack | Extra read-only mounts |
| `environment.network` | pack, project | `open`, `allowlist`, `offline` or `auto` (see [network](#network-and-security)) |
| `environment.allow_domains` | project | Extra domains for `allowlist` mode |
| `environment.disabled_tools` | pack | Native tools the model proxy removes |
| `acceptance.pr`, `acceptance.main` | pack, project | Fast checks for PRs; the full suite on `main` |
| `acceptance.protected_paths` | pack, project | Files that need human approval before merge |
| `human.mode`, `human.username` | pack, project | `none` or `optional`; the human's account name |
| `coordination.backlog` | pack | `issues` or `board` (board = current CLAIM-only behavior) |
| `coordination.planning` | pack, project | One worker plans before the others wake |
| `coordination.review` | pack, project | Optional peer-review rule |
| `brief.*` | pack | Prompt fragments (see [prompt layering](#prompt-layering)) |
| `team.workers`, `budget.*` | project | Team size, wall-clock and token budgets |
| `lifecycle.resumable`, `lifecycle.stop_when` | pack | One-shot or resumable; stop conditions |
| `finalize.export`, `finalize.evaluate` | pack | Delivery and evaluation hooks |

Example `tasks/software-project/pack.toml`:

```toml
name = "software-project"
description = "Improve an existing repository, or build a new one from a specification"

[workspace]
prepare = "hooks/prepare"            # import upstream or create an empty tree

[environment]
base_image = "default-python"
network = "auto"                     # open for public upstreams, allowlist for private

[acceptance]
protected_paths = [".gitea/workflows/**", ".agensh/**"]

[human]
mode = "optional"

[coordination]
backlog = "issues"
planning = false

[brief]
objective = "prompts/objective.md"
work_cycle = "prompts/work_cycle.md"
idle = "prompts/idle.md"
delivery = "prompts/delivery.md"

[lifecycle]
resumable = true
stop_when = ["budget", "human_close", "human_stop"]

[finalize]
export = "hooks/export"              # push the delivery branch and open a PR
```

Example `.agensh/project.toml` in a target repository:

```toml
pack = "software-project"
goal = "docs/agensh_goal.md"

[workspace]
seed = "git"

[upstream]
repo = "github.com/org/project"
base_branch = "main"
delivery_branch = "agensh/{run_id}"

[acceptance]
pr = ["make lint", "make test-fast"]
main = ["make test"]

[human]
username = "alice"

[team]
workers = 8

[budget]
hours = 8
max_model_tokens = 0                 # 0 = unlimited
```

## Run lifecycle

The current runner requires empty state and destroys the stack at the end. That
suits experiments but not projects. The core lifecycle becomes:

| Command | Behavior |
|---|---|
| `up` | Bootstrap accounts, run `prepare`, push the seed, open issue #1, wake workers on a stagger |
| `pause` | Stop routers/CI, then stop workers so they seal archives (current `quiesce_agents`) |
| `resume` | Sync upstream, start workers with **fresh** native sessions, deliver a project-state summary |
| `finalize` | Pause, sync upstream, then run `export` and `evaluate` |
| `down` / `clean` | As in the current Makefile |

**Resume uses fresh sessions.** Restoring the previous ACP session depends on
each harness's native session files, and after a long pause the old context has
usually been compacted. Fresh sessions are more predictable. Workers continue
from durable state: the repository, the board history and a generated
"state of the project" summary (open issues and claims, recent merges, CI
status, the latest progress digest). Restoring the existing session remains the
behavior for automatic restarts after a crash, as the router does today.

**Stop conditions** combine: wall-clock budget, token budget (from usage
metering), the human closing issue #1, or an explicit stop. Packs choose which
apply. `programbench` keeps its current behavior: one shot, empty state
required, wall-clock budget only.

**Token budget: warn, then stop.** At 90% of `budget.max_model_tokens` every
worker gets a lifecycle message to commit and wrap up current work. At 100% the
proxy rejects new model requests and the driver pauses the run, so work stays
resumable once the human raises the budget.

**Lifecycle messages replace deadline reminders in the core.** Real projects
pause and resume, so "45 minutes left" has no meaning there. The core sends
messages on lifecycle events: budget nearly spent, before pause and before
finalize. Time-based reminders (`deadline_45m`, `deadline_5m`) stay in the
`programbench` pack.

For 4–16 workers, the default wake stagger drops from 30 s to a few seconds per
worker. The existing ramp settings stay available.

## Upstream sync and delivery

The team works in its own Gitea repository; workers never hold GitHub
credentials. Host-side hooks move code between GitHub and Gitea using the host's
`gh` login:

```
GitHub base branch ──prepare / sync──▶ Gitea main ──agents: PR, CI, merge──▶ Gitea main
                                                                                  │
                         finalize: push GitHub branch agensh/<run-id>, open PR ◀──┘
```

- **Sync** runs on `resume` and before `finalize`. The host fetches the upstream
  base branch and merges it into Gitea `main` as the admin user, who is the only
  account allowed to push to `main` directly. A conflicting merge is not forced:
  the host opens a Gitea issue with the conflict and the agents resolve it in a
  normal PR.
- Commits that the human pushes to Gitea `main` between runs are treated like
  any other commit and stay in history.
- **Delivery** keeps the team's commit history on the delivery branch for
  auditability. Maintainers can squash when merging the GitHub PR.
- The delivery PR description lists every change to a sensitive path (see
  [human product owner](#human-product-owner)) in its own section.

## Human product owner

When `human.mode = "optional"`:

- Bootstrap creates a human account in Gitea and Mattermost and adds it to the
  organization, the team and the task channel.
- The router marks the human's direct messages, @mentions of a worker, and
  issue/PR comments as urgent, so they reach that worker mid-turn through the
  existing notice path. Channel messages without a mention stay queued, so the
  human does not interrupt every worker at once.
- The prompt tells agents to ask the product owner in the task channel when
  requirements are ambiguous, and to **continue with other work instead of
  waiting**. `request_user_input` stays disabled because it would block the
  turn; human input is always asynchronous.
- Issues the human opens become work items, as peer-opened issues already do.

**Review happens after merge, with one exception.** Requiring human approval
before merge would stop agents whenever the human is away. Agents therefore
merge normally, and the human reviews the complete change on the delivery PR,
where changes to sensitive paths are listed separately. The exception is
`acceptance.protected_paths` (CI workflows and acceptance scripts): if agents
could change them freely, they could weaken the checks that gate their own
work. The prepare hook writes these paths to `.gitea/CODEOWNERS` with the
human as owner, so PRs touching them request the human's review; the driver
makes the human the only official approver and enables
`block_on_official_review_requests` (Gitea 1.22 has no separate code-owner
requirement). Agents rarely need to touch these files; when they do, they open
the PR, explain why, and keep working on something else.

`human.mode = "none"` reproduces the current fully autonomous setting. Protected
paths then use Gitea's `protected_file_patterns`, so only the admin can change
them.

## Network and security

| Mode | Behavior |
|---|---|
| `open` | Workers join a bridge network with general egress |
| `allowlist` | A fixed list of public package registries (PyPI, npm, crates.io, Go proxy, Debian mirrors) plus domains the project adds in `environment.allow_domains`, through a filtering proxy; all other egress blocked |
| `offline` | Today's internal network plus model egress only (`programbench`) |
| `auto` | `open` for a public upstream repository, `allowlist` for a private one (from the GitHub API at `prepare`) |

`software-project` defaults to `auto`. Projects add domains such as internal
package indexes with `environment.allow_domains`; the delivery PR description
lists any added domains so reviewers see what the team could reach.

- Model credentials stay in the egress proxy in every mode. Each worker sends
  its own proxy key, `local-proxy-<agent>`, which the proxy uses to label
  requests for usage metering. It is a label, not a credential: the proxy is
  only reachable on the private network and does not authenticate workers. A
  worker could claim another label, which matters only for per-agent budgets;
  issuing secret per-worker keys from bootstrap would close that gap if
  per-agent budgets are ever enforced.
- Workers never hold GitHub credentials. Only host-side hooks push branches or
  open PRs.
- **The repository itself is sensitive.** Workers can read the whole codebase,
  and prompt injection from fetched content can try to send it elsewhere. That
  is why private repositories default to `allowlist`. With `open`, the
  remaining safeguards are that workers hold no long-lived credentials and that
  everything delivered goes through human review on GitHub.

## Worker environment

- **Default base images** come in per-language variants, built from
  `agent/Dockerfile` with a task-neutral `TASK_IMAGE`: `default-python`,
  `default-node`, `default-go`, `default-rust` and `default-c`. A single image
  with every toolchain would be several gigabytes and slow to build.
- **`devcontainer`** is supported when the target repository's
  `.devcontainer/devcontainer.json` names an `image` or a `build.dockerfile`
  based on Debian or Ubuntu. The harness layers use `apt-get`, so other
  distributions, devcontainer features and Compose-based devcontainers fall
  back to the default base with a warning.
- `programbench` keeps building from its cleanroom image.
- **Resource shares**: workers have a 64 GiB memory ceiling but no CPU limit, so
  16 workers compiling at once on an 8-core host contend heavily. Compose
  generation assigns CPU and memory shares from the host size and worker count.

## Harness selection

Packs do not choose a harness. `agent/config/harness.json`, the environment and
`--agent-harness` keep selecting Copilot, Pi, Codex or Claude Code, exactly as
today.

## Implementation language of target projects

Agents follow the language and tooling already used in the target repository.
For new projects (`workspace.seed = "empty"`) the pack defaults to Python unless
the goal says otherwise. Both rules live in the pack prompts, not in the core.

## Prompt layering

`prompts/agents.txt` becomes a core template that keeps identity, the shared
services, the event model and the generic loop (observe → claim → build →
verify → merge → publish). Task-specific content moves to pack fragments:

```
prompts/agents.txt (core)
  ${TASK_OBJECTIVE}     ← <pack>/prompts/objective.txt
  ${TASK_FOCUS}         ← <pack>/prompts/focus.txt ("Always focus on …;")
  ${TASK_WORK_CYCLE}    ← <pack>/prompts/work_cycle.txt
  ${TASK_DELIVERY}      ← <pack>/prompts/delivery.txt (e.g. the compile.sh contract)
```

`agent/render_agents.sh` renders `AGENTS.md` from these at worker start, and
`scripts/lib_prompts.sh` renders runner messages; the render snapshot calls the
same code.

Generic work cycle: read the backlog and the board → `CLAIM` referencing an
issue → implement on the latest `main` → run `acceptance.pr` → open a PR →
merge after CI passes → `PATCH_SUMMARY`. The prompts also ask agents to keep
`ARCHITECTURE.md` and a decision log in the repository, which outlive any run.

The ProgramBench fragments start from today's text. Small wording changes that
the layering needs are allowed.

**Reproducibility check:** `scripts/render_check.sh` renders the worker
`AGENTS.md` and MCP configuration, every runner message, the standalone
baseline prompts, and the profile and Compose files for each harness and 1–16
workers, then diffs them against the base revision. Unchanged outputs need no
further check. Any intended difference is listed in the PR description. Once
the refactor series is complete, a ProgramBench team run on dev1 confirms that
results stay comparable with the published experiments.

## Quality gates

**CI merge gate.** Gitea Actions and act-runner are running, but no workflow is
installed, and `ensure_branch_protection` in `docker/bootstrap/bootstrap.sh`
sets `required_approvals: 0` and `enable_status_check: false`. The core
generates `.gitea/workflows/agensh.yml` from the acceptance commands and makes
the PR job a required status check on `main`.

- PRs run only `acceptance.pr`, the fast subset. act-runner defaults to two
  concurrent jobs, and 16 workers opening PRs would otherwise queue behind full
  test suites. Runner capacity also scales with the host.
- Pushes to `main` run the full `acceptance.main`.
- `DEFAULT_ACTIONS_URL: github` needs network access to fetch actions, so
  offline projects get a workflow that uses only `run:` steps.
- The workflow and acceptance scripts are protected paths (see
  [human product owner](#human-product-owner)).

**Broken-main alarm.** There is no merge queue and `block_on_outdated_branch` is
off, so two PRs that each pass can still break `main` together. When the full
suite fails on `main`:

1. The author of the merge that broke it gets an urgent event, and an automatic
   `FAIL` gist goes on the board so peers do not build on the broken state.
2. If `main` is still failing after 15 minutes, every worker gets the urgent
   event.

Alerting only the author first avoids the whole team rushing to fix the same
failure.

While `main` is failing, only PRs labeled `fix-main` can merge. The driver
enforces this with an `agensh/main-health` commit status, which is a required
check on `main`: it posts success on every PR while `main` is green, and only
on `fix-main` PRs while it is red. Gitea branch protection cannot filter merges
by label, so the status check carries the rule. If `main` is still red after
60 minutes, the restriction lifts automatically and the human is notified, so a
flaky test cannot stall the team.

**Optional peer review by path.** The prompts contain no review step: agents
write and merge their own PRs. `coordination.review.paths` lists core
directories; a PR touching them needs one peer approval. Paths are used rather
than changed-line counts, which agents can avoid by splitting PRs. Gitea
approvals apply to a whole branch rather than paths, so the driver enforces the
rule with an `agensh/review` commit status. Review costs throughput, so it is
off by default.

## Coordination

**Backlog: issues say what, claims say who.** Work decomposition is implicit
today: board `CLAIM` entries (one-hour expiry) and ad hoc issues. With
`backlog = "issues"`, Gitea issues are the work items, and labels and
milestones carry priority, so the human manages priorities in the issue list. A
`CLAIM` references an issue as `#<number>`. Synchronization is one-way: a claim
sets the issue's assignee, and claim expiry or the closing PR clears it. The
board stays the source of truth for who is working on what right now. Two-way
synchronization is avoided on purpose.

**Optional planning phase.** All workers start at once. That suits rebuilding a
reference program, but building from a specification benefits from an
architecture document and an issue breakdown first. With `planning = true`, one
worker plans, and the others wake when the plan PR is merged.

**Progress digest.** An hourly or daily summary to the human, built from the
board, PRs and CI results, so the human does not need to read every channel
message.

## Observability and cost

**Usage metering** *(PR 4)*. Every worker used to send the same proxy key
(`local-proxy-no-auth`), so the proxy could not tell agents apart. Workers now
send `local-proxy-<agent>`, and `scripts/usage_meter.py` parses the usage fields
of each buffered response (Responses, Chat Completions and Messages, JSON or
SSE). The proxy keeps per-agent totals, serves them at `GET /usage` and appends
one record per request to `$DATA_ROOT/<profile>/usage/usage.jsonl`. This is the
prerequisite for the token budget and for reporting what a feature cost.

**Run status** *(PR 4)*. `scripts/team_status.py <profile>` summarizes each
worker's containers, native activity (from the same session journals as the
idle watchdog), event queue states, token usage, board entries and merged PRs.
CI results join it with the CI merge gate. A web dashboard can follow later.

**Per-role models (optional).** The proxy forwards to one configured model
(`UPSTREAM_ANTHROPIC_MODEL`). Selecting the model per worker or per role (for
example, a cheaper model for review) reduces cost and is also a research
question.

## Framework testing

The repository has no tests and no CI of its own.

- **Unit tests** for the board (deduplication, claim expiry, patch replacement,
  `gquery` parsing, `unfold`) and the router (event states, retries, cursors,
  group-message backlogs).
- **Repository CI** on GitHub Actions: unit tests, the router typecheck, shell
  syntax checks and `render_check.sh` against the PR base.
- **Stub-harness smoke test** (`tests/smoke/`). A scripted ACP harness writes a
  claim, pushes a file, opens and merges a PR and publishes a patch summary.
  The router talks to every harness through ACP over the worker socket, so the
  stub exercises the whole team stack (router, board, Gitea, Mattermost,
  bootstrap, export, shutdown archives) without a model and without emulating
  the Responses and Messages streaming protocols. Rather than adding a fifth
  harness kind, which would touch the harness configuration, image checks,
  Dockerfile and launch scripts, the test uses a normal Pi worker image and
  mounts the stub over the Pi adapter through `COMPOSE_EXTRA_FILES`. It runs
  the real `scripts/pbench_run.sh` against a minimal stand-in cleanroom, so it
  becomes the regression check when the runner is split. A two-worker run takes
  about eight minutes, most of it the runner's minimum budget and shutdown.
  `run_isolated.sh` runs it inside a capped Docker-in-Docker daemon with storage
  on a chosen disk, for shared hosts.
- **Real-harness smoke run** for feature PRs: two workers on copilot-api for
  about ten minutes, covering the native harness integration that the stub
  skips.

## Naming

Renaming happens once, without compatibility aliases; the release notes list
every change. Names that belong to ProgramBench stay inside the
`programbench` pack.

| Current | New |
|---|---|
| `PBENCH_*` (generic meaning) | `AGENSH_*` |
| `PBENCH_RUN_START_MS` | `AGENSH_RUN_START_MS` |
| `pbench.slice`, `pbench-reboot-guard.service` | `agensh.slice`, `agensh-reboot-guard.service` |
| `pbench-single-node-<task>` profiles | `<pack>-<project>` (for example `programbench-pandoc`) |
| `~/.pbench-upstream.env` | `~/.agensh/upstream.env` |
| `ORG_NAME=pbench`, board id `pbench-top`, channel `pbench-task` | pack-defined; ProgramBench keeps these values, so its prompts are unchanged |
| `/opt/pbench/executable`, cleanroom tags, evaluator variables | unchanged, owned by the `programbench` pack |
| `omcgitea` images, Compose projects, `/opt/omcgitea` paths, database | unchanged for now; renaming needs image rebuilds and a reboot-guard change |

Implemented in PR 8; REPRODUCE.md "Migrating from earlier releases" lists every
renamed file and setting.

## Orchestration language

The core driver moves to Python in the PR that splits `pbench_run.sh`. That PR
rewrites the lifecycle anyway, and the features that follow (pause/resume,
upstream sync, alarms, digests, `status`) would be hard to maintain in Bash. The
CLI is `agensh up|pause|resume|finalize|status|down`. Pack hooks are
executables, so the `programbench` hooks can stay in Bash at first.

## Target layout

```
agensh/                 # Python package: CLI, configuration, lifecycle, drive loops
agent/  board-service/  mini-router/  secret-service/  docker/   # core, unchanged locations
prompts/agents.txt      # core template and lifecycle messages
tasks/
  programbench/
    pack.toml
    prompts/            # brief, work cycle, idle, delivery, deadlines, single-agent/
    hooks/              # prepare (cleanroom seed), export, evaluate
    scripts/            # chain, per-task image build, score report, docker shim
  software-project/
    pack.toml
    prompts/
    hooks/              # prepare (import or empty), sync, export (GitHub PR)
docs/task_pack_design.md
```

Core component directories stay where they are, to keep diffs and
documentation links stable.

## Upstream PR sequence

Low-cost foundations come first, then the refactor, then features. Each PR
runs the render-diff check and lists any intended difference in the
`programbench` pack's rendered outputs.

Foundations:

1. **Render-diff harness**: renders prompts, profiles and Compose for every
   harness and 1–16 workers. *(done)*
2. **Framework tests and repository CI**: board and router unit tests, plus
   GitHub Actions running them with the typecheck and render check. *(done)*
3. **Stub-harness smoke test**. *(done)*
4. **Per-worker proxy identity, usage metering and `status`**. *(done)*

Refactor:

5. **Prompt layering**: core template plus ProgramBench fragments under
   `tasks/programbench/prompts/`, with shared renderers
   (`agent/render_agents.sh`, `scripts/lib_prompts.sh`). *(done)* Lifecycle
   messages move to PR 10, where pause, resume and the token budget exist.
6. **Python core driver and pack loading**: `agensh/` (driver, `pack.toml`
   loader, timing rules) and the ProgramBench `prepare/export/evaluate` hooks;
   `scripts/pbench_run.sh` becomes a wrapper. *(done)* Project files arrive with
   the `software-project` pack, and the ProgramBench-only tools and launch
   scripts move into the pack with the naming migration, so user-facing paths
   change once.
7. **Compose parameterization**: worker mounts, prompt directory, board id and
   the `offline`/`open` network modes come from the pack; worker memory and CPU
   shares are opt-in settings; tasks outside `TASK_TABLE` get automatically
   chosen ports and subnets. *(done)* The `allowlist` and `auto` network modes
   and the per-language default base images move to PR 9, which is the first
   pack to use them.
8. **Naming migration** in one step, together with moving the
   ProgramBench-only tools and launch scripts into `tasks/programbench/`.
   *(done)* Agent-visible ProgramBench names stay in the pack and internal
   `omcgitea` names are unchanged; REPRODUCE.md lists every rename and the host
   migration steps.

Features:

9. **`software-project` pack**, in three parts:
   - **9a** *(done)*: project files and `agensh.project` (profile, build,
     run); import of the upstream branch with its history; per-project prompt
     rendering; delivery to a GitHub branch and pull request (or a bundle);
     acceptance as the evaluation; `default-python` base image; `open` network;
     the task channel becomes a pack setting.
   - **9b** *(done)*: CI as a required merge check, protected acceptance
     files, the broken-`main` alarm and `fix-main` gate. Until the human
     product owner arrives in PR 10, protected paths use Gitea protected files
     (administrator only), as `human.mode = "none"` describes.
   - **9c** *(done)*: issue backlog synchronization, `allowlist` and `auto`
     network modes, upstream sync before delivery. Upstream also syncs 30
     minutes before the end, so the team can still resolve a conflict; a
     conflict left at the final sync is reported in the delivery PR.
10. **Human product owner and resume**, in two parts:
    - **10a** *(done)*: `pause`, `resume`, `finalize` and `status` for
      resumable packs, fresh-session resume with the project-state summary,
      the token budget (warning at 90%, proxy refusal and pause at 100%),
      lifecycle messages, stopping when issue #1 closes, and a 5-second wake
      stagger for software projects.
    - **10b** *(done)*: the human product owner (accounts, urgent routing,
      approval of protected paths through CODEOWNERS, sensitive paths in the
      delivery PR), the progress digest and the optional planning phase.
      `[human]` and `[coordination] planning` are project settings; the pack
      only declares `[human] product_owner = true`.
11. **Optional capabilities** *(done)*: peer review by path
    (`[coordination] review_paths`, enforced by the `agensh/review` status)
    and per-worker models (`[team.models]`, applied by the egress proxy).

PRs 1–8 do not change task behavior. 9–11 add features.

## Standalone baseline

`scripts/launch_single_agent.py`, `scripts/acp_driver.py` and
`prompts/single-agent/` move into the `programbench` pack unchanged, so the
published single-agent condition stays the same. General single-agent use is a
team run with `team.workers = 1`; the core does not maintain a separate
single-agent lifecycle.

## Decisions

| Topic | Decision |
|---|---|
| Purpose | Development tool for real projects; ProgramBench stays as a regression pack |
| Order | Foundations, then refactor, then features |
| ProgramBench prompts | Small changes allowed; listed in the PR and confirmed by a dev1 run after the refactor |
| Human role | Optional product owner; post-merge review on the delivery PR; protected acceptance files need approval before merge |
| Network | `auto`: open for public upstreams, allowlist for private ones; fixed registry list plus project domains |
| Team size | Defaults tuned for 4–16 workers |
| Target project language | Follow the repository; Python for new projects |
| Harness | Not set by packs |
| Orchestration language | Python core driver from the runner-split PR |
| Naming | One rename, no compatibility aliases |
| Token budget | Lifecycle message at 90%, proxy stop and pause at 100% |
| Standalone baseline | Stays in the `programbench` pack |
| Peer review | Optional, triggered by paths |
| Broken `main` | Only `fix-main` PRs merge; restriction lifts after 60 minutes with a human notice |
| Validation | Render check, unit tests and stub-harness smoke on every PR; copilot-api smoke runs for features; ProgramBench regression on dev1 |
| Delivery credentials | The host's `gh` login |

## Open questions

None at present. New questions are added here as implementation proceeds.
