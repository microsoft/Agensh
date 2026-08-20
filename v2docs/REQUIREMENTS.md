# omcgitea Requirements Document v2

> Version: v2 | Date: 2026-04-26
> Status: M1 implemented and verified (bidirectional PR/review/merge round working)

> **Agent choice**: "Hermes agent" / "Hermes" in this document means the generic **ACP agent**.
> The default is `AGENT_KIND=claude` (`@agentclientprotocol/claude-agent-acp`); `AGENT_KIND=hermes`
> is a dormant compatibility option. CLAUDE.md records the decision and the cache measurements
> behind it; they are not repeated here.

---

## 1. One-Sentence Goal

Have **Hermes agents** do modern development based on self-hosted **Gitea**, in a **multi-agent parallel + multi-microservice repository** manner, going through Gitea native PR and CI/CD (Gitea Actions) end-to-end, and supporting local CD deployment.

Ultimate form: **one team = one repo = N Hermes agents**, with the team internally self-organizing division of labor via Hermes, multi-repo = multi-team parallel.

---

## 2. Scope and Boundaries

### 2.1 What We Do ("glue layer + infrastructure")

- Deployment: self-hosted Gitea + Gitea Actions runner (one-command docker-compose start)
- Multi-repo management: one service per repo, N repos sharing one Gitea instance
- Agent integration: give Hermes agents Gitea identity and tokens, call APIs via the **Gitea official MCP server** (stdio)
- Event push: **Gitea → mini-router sidecar → ACP** — one sidecar per agent runs cursor pull + SSE trigger, and sends each UEM to that agent's long-lived ACP session (replaces the old webhook path)
- Agent orchestration: one agent per container
- Configuration: Gitea repos / users / tokens / branch protection / `.gitea/workflows/*.yml` templates
- Workflow conventions: Issue lifecycle, PR, review, CI must-be-green, local CD
- Documentation: deployment manual, interface contract, acceptance criteria

### 2.2 What We Don't Do

- Do not modify Hermes upstream code (black-box integration)
- Do not modify Gitea upstream code (config only, no patching)
- Do not introduce other CI systems (uniformly Gitea Actions)
- Do not provide microservice infrastructure (registry / discovery / config center / service mesh)
- Do not specify service boundaries / protocols / frameworks
- Do not do remote CD (only local docker compose / local k8s)

---

## 3. Key Concepts

| Term | Meaning |
|---|---|
| **Hermes agent** | Agent framework with self-organization, self-evolution, memory capabilities |
| **Team** | Collection of all Hermes agents inside the same repo, internally self-organizing division of labor |
| **Gitea instance** | Self-hosted Git service, serving as code hosting + collaboration hub |
| **Gitea MCP server** | Gitea official MCP service (`docker.gitea.com/gitea-mcp-server`) |
| **mini-router** | Self-built TypeScript sidecar, one per agent: pulls events from the Gitea notification API + SSE trigger and delivers them over ACP (replaces the old Hermes webhook gateway) |
| **Gitea Actions** | Gitea's built-in CI/CD engine, executed by act_runner |
| **Microservice repo** | One service per Gitea repo, independent CI/CD and deployment unit |
| **Glue layer** | The output of this repo: all configs, scripts, docs to connect Hermes to Gitea + one-command deployment |
| **Chairman** | The human user, the only human participant, observes and intervenes via Gitea Web UI |

---

## 4. agent ↔ repo Binding Model

### 4.1 Static Many-to-One

- One agent corresponds to only one repo (unchanged within lifecycle)
- One repo can bind multiple agents
- Statically specified via configuration at startup, not changed during runtime
- Cross-repo references via `owner/repo#N` syntax

### 4.2 Identity and Permissions

- Each Hermes agent = one Gitea user + one independent token
- Permissions determined by Gitea server per token
- **Starting from R5**, all repos are owned by **org `omcgitea`** (no longer owner=chairman);
  `chairman` is the org owner (admin user).
- Roles expressed via **org team membership** (`directors / leads / reviewers / coders`),
  see [`v2docs/TEAMCONFIG.md`](./TEAMCONFIG.md) §3 for details.
- At minimum required:
  - `chairman` (admin) — chairman + org owner, the execution identity for bootstrap
  - `directors` team (admin permission) — owns the overall task, supervises
  - `leads` team (admin permission) — split work, merge
  - `reviewers` team (write permission, listed in branch protection
    `approvals_whitelist_teams`)
  - `coders` team (write permission)

### 4.3 Repo Creation Constraints (from M2-E.2)

- **Agents are not allowed to create repos**. All repos are created by bootstrap as `chairman` under the
  `omcgitea` org, with team permissions automatically applied.
- This is a hard constraint for notification delivery correctness (see §5.2 / §5.4): Gitea automatically adds the repo creator to the
  watcher set (`services/repository/create.go`), and watchers receive all broadcast events for that repo.
  Letting an agent be the creator breaks the "only receive relevant events" convention in §5.4.
- Agent token scope therefore **does not include** `write:repository`; it retains
  `read:repository,read:user,read:notification,read:issue,write:issue`.

---

## 5. Communication Model

### 5.1 Hermes → Gitea (write direction)

- Medium: **Gitea official MCP server** (stdio subprocess)
- Deployment: an MCP subprocess is started inside each agent container, with env injecting `GITEA_HOST` + that agent's `GITEA_ACCESS_TOKEN`
- Tools required for M1: `create_issue` / `get_issue_by_index` / `edit_issue` / `list_repo_issues` / `create_issue_comment` / `create_pull_request` / `get_pull_request_by_index` / `list_repo_pull_requests` / `create_pull_request_review` / `submit_pull_request_review` / `merge_pull_request`
- git operations go through standard git CLI, credentials injected via git credential helper with tokens

### 5.2 Gitea → Agent (read direction)

Requirement level (implementation is [`DESIGN_R7_SIDECAR.md`](./DESIGN_R7_SIDECAR.md): per-agent
mini-router sidecar + central MySQL + secret-service):

- **The router layer is the unique entry for events.** Each agent has its own sidecar holding a
  cursor pull (`?since=<cursor>`, `read:notification` scope) plus an SSE wake trigger.
- Events are persisted before delivery, keyed `gitea:notif:<id>`, and delivered as **one merged
  ACP `session/prompt` per batch** with state machine pending→sending→{sent,failed,cancelled}.
- **Boot recovery**: leftover `sending` rows roll back to `pending`, so a killed process cannot
  strand a half-delivered batch.
- **at-most-once**: transmission failures are not auto-resent (humans do it the same way); ACP
  exceptions mark `failed` and enter the dead letter queue.
- **Stuck self-healing**: the sidecar listens to the ACP `sessionUpdate` stream; **20 minutes
  with no update** is considered stuck → `session/cancel`, mark the batch `cancelled` + log,
  automatically continue with the next batch. Session and cache are not lost.
- One long-lived ACP session per agent (a prerequisite for cache reuse).
- **No semantic filtering**: who receives what is 100% delegated to the Gitea notification model
  (§5.4); the router layer only ferries + persists + batches.

### 5.4 Notification Delivery Convention (from M2-E.2, all delegated to Gitea)

**Goal**: under N=30 agents / single-repo collaboration, each agent only receives events truly relevant to it.

**Gitea delivery semantics** (source-verified `services/uinotification/notify.go` + `models/activities/notification_list.go`):
- **Directed events** (assign / request review / @mention) → `receiverID > 0`, **only pushed to that one person**, does not query the watcher set
- **Broadcast events** (comment / status change / push / merge) → pushed to `IssueWatchers ∪ RepoWatchers ∪ Participants − IssueUnWatchers − author`

**Bootstrap-side config** (to prevent agents from entering the watcher set):
1. `app.ini`: `[service] AUTO_WATCH_ON_CHANGES=false`, `AUTO_WATCH_NEW_REPOS=false`
2. Agents do not create repos (§4.3) — will not be auto-watched by `create.go:448`
3. Bootstrap calls `PUT /repos/{o}/{r}/subscription {subscribed:false}` once for each agent for each repo

**Remaining visible broadcast events**: issues/PRs the agent itself has commented on (enters the Participants set). This is common-sense semantics of a collaboration platform ("if you participated in a topic, you should know follow-up movements"), **not considered noise**, no longer handled.

### 5.5 Branch protection (resolves self-merge / enforces review)

Bootstrap configures the main branch of each repo one-time with:
- `enable_push: true` + `push_whitelist_usernames:["chairman"]` (only admin pushes
  workflow files, agents cannot push directly)
- `required_approvals: 1`
- `block_on_official_review_requests: true`
- `block_on_outdated_branch: true`
- `dismiss_stale_approvals: true`
- `approvals_whitelist_teams: ["reviewers"]` (**from R5** use team, no longer list user)
- `merge_whitelist_teams: ["leads","reviewers","coders"]`
- `enable_status_check: true`, `status_check_contexts: ["closes-issue-check"]`
  (paired with `.gitea/workflows/closes-check.yml`, forces PR body to contain `Closes #N`)

See [`v2docs/TEAMCONFIG.md`](./TEAMCONFIG.md) §3 for details.

Note: Gitea does not have a native "only non-PR-author can merge" switch, self-merge is gated by workflow convention + branch protection's review enforcement gate.

### 5.3 LLM Integration

- Goes through any Anthropic Messages API-compatible endpoint
- Configured in Hermes `custom_providers` + `api_mode: anthropic_messages`
- **Model names can only use hyphens** (Hermes unconditionally converts `.` to `-` in the `anthropic_messages` path) — e.g. `claude-opus-4-7`, **do not** write `claude-opus-4.7`

---

## 6. Workflow Trunk (M2 and beyond)

### 6.1 Issue Lifecycle

- `open` no label = to be claimed
- `open` + `in_progress` label = already claimed by some agent
- `closed` = corresponding PR merged

### 6.2 PR Trunk

1. Agent completes development → push → open PR via MCP `create_pull_request`, body contains `Closes #N`
2. PR automatically triggers Gitea Actions
3. Reviewer agent reviews, merges after reaching `required_approvals`
4. Merge automatically closes issue

### 6.3 Main Protection (independently configured per repo)

See §5.5. Bootstrap calls `POST /api/v1/repos/{o}/{r}/branch_protections` immediately after repo creation. From M1 `required_approvals=1`, upgraded to ≥ 2 at M3.

### 6.4 CI

- `.gitea/workflows/*.yml` is the only CI definition
- Modifying the workflow itself also goes through PR + review
- CI failures notify PR author

### 6.5 Local CD (optional)

- Each repo appends a deployment step after CI
- Trigger timing determined by that repo's workflow (merge to main / tag / manual)
- Does not involve remote registry / remote k8s / remote secret

---

## 7. Deployment Form

| Service | Purpose |
|---|---|
| `gitea` | Gitea itself (Web UI + API) |
| `gitea-admin-init` | One-time sidecar, uses gitea CLI to create admin user (Gitea 1.22 no longer auto-creates from env) |
| `gitea-runner` | Gitea Actions runner (M1 placeholder, M2 enabled) |
| `bootstrap` | One-time container, runs `bootstrap.sh` to create users/tokens/repos + delete old hermes-agent webhook |
| `mysql` + `secret-service` | Central event store + per-agent token distribution (R7) |
| `mini-router-<n>` (one per agent) | Long-running: pull Gitea notification → ACP → that agent's session |
| `hermes-agent-<n>` (one agent per container) | Each agent is an independent container, containing Hermes gateway + Gitea MCP subprocess |
| User business services (after CD deployment) | Microservices written out by agents |

All data is bind-mounted to the host project subdirectory. `docker compose down` does not lose data.

---

## 8. Milestones

### M1 (minimum milestone, ✅ **completed**)

**Bidirectional Hermes ↔ Gitea connectivity + single-repo multi-agent collaboration round**

- Hermes → Gitea: agent calls core APIs via Gitea MCP server
- Gitea → Hermes: webhook arrives in real-time at the corresponding agent and triggers LLM reasoning
- Acceptance: Issue → branch → PR → review → merge run through at least one round

### M2

- Multi-repo + multi-agent parallel
- Complete CI closed loop + main protection + local CD
- pytest automated e2e suite

### Subsequent

- M3: cross-repo collaboration
- M4: remote CD
- M5: microservice infrastructure templates

---

## 9. Acceptance Dimensions

| # | Stage | Criterion | Status |
|---|---|---|---|
| V1 | M1 | MCP calls core APIs successfully (list/create/edit/comment etc.) | ✅ |
| V2 | M1 | Events arrive in real-time at corresponding agent and processed by LLM (mini-router → ACP) | ✅ |
| V3 | M1 | Smoke: open issue → agent replies comment | ✅ |
| V4 | M1 | Round: Issue → PR → review → merge closed loop working | ✅ |
| V5 | M2 | Same-repo multi-agent parallel: ≥2 developers + ≥1 reviewer concurrent without deadlock | — |
| V6 | M2 | Multi-repo parallel | — |
| V7 | M2 | Main protection server-side blocking reliable | — |
| V8 | M2 | Local CD: deployment step triggered after merge | — |
| V9 | M2 | No loss on destroy: data preserved after `docker compose down` | — |
| V10 | All-period | Do not touch upstream: zero patch / zero fork of Hermes / Gitea | ✅ |
| V11 | All-period | Documentation self-consistency: v2docs/ synchronized with code | ✅ |
