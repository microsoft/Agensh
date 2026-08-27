# TEAMCONFIG — Team Collaboration Model

> Status: **landed**. `docker/bootstrap/bootstrap.sh` implements the org / team route described
> below (`ensure_org`, `ensure_team_membership_strict`, team-based branch-protection whitelists,
> no `roles.env`). The earlier owner=chairman + `roles.env` + templated-AGENTS.md form it replaced
> is gone; this text describes what runs.
> Principle: **do not touch Hermes / claude-agent-acp / Gitea upstream code**, only configure via Gitea API + bootstrap
> scripts + agent SOUL.md/AGENTS.md layered landing.

> The default agent is `claude-agent-acp` (`AGENT_KIND=claude`); hermes is dormant. The
> AGENTS.md / SOUL.md injection mechanism keeps one template set per kind
> (`docker/hermes-agent/templates-claude*`, `templates-hermes`), selected by entrypoint.

---

## 1. Background

The phenomena observed in R3 multi-agent runs (review storm / lead-issue comment fanout / sub-issue
not auto-close / PR closed and reopened by author as umbrella) upon analysis are **all not code bugs**, but 10
agents completely equal in power, no role division of labor → whole-team-piling-on side effects when things happen.

R4 landed the role concept into the branch protection whitelist + static AGENTS.md template concatenation, and initially suppressed
the review storm; but exposed two new problems:

1. **team membership is dynamic, should not be hardcoded into md files**: HR adjustments (agent3
   changed from coder to reviewer) require restarting all containers to take effect, and copies of different md files may
   not synchronize.
2. **owner=chairman (user) has no structured "role grouping" mount point**: can only mark roles via
   branch protection whitelist + user description bypass, invisible on UI,
   API queries also not intuitive.

R5 formally goes the **Gitea organization + team** route, making "role" a first-class citizen.

---

## 2. Target Collaboration Model

Role types (the same agent can serve different roles in different repos through different team assignments):

```
director (0-1)      owns the overall task, supervises, arbitrates across teams
  │
  └── lead (1 per team)   split work, distribute sub-issue, arbitrate PR mode, merge
        │
        ├── reviewer (1-2)   review all PRs, APPROVE / REQUEST_CHANGES
        │
        └── coder (the rest) write code, open PR, request_review to reviewer
```

Role configuration in `.env.<profile>`, the input source for bootstrap to orchestrate team membership:

```
ROLES=director=director;lead=agent1;reviewer=agent2;coder=agent3,agent4,...
```

After bootstrap parses, **no longer writes roles.env file**, but directly calls Gitea API to add agent to
the corresponding team. **Unique authoritative source = Gitea team membership table**, agent role queries all go through API.

---

## 3. Gitea-side Topology

### 3.1 Org / Team Structure

```
omcgitea (org)
├── Members: chairman (owner), agent1..agentN
├── Repositories:
│   └── omcgitea/test-sandbox  (transferred from chairman/test-sandbox)
└── teams:
    ├── directors    permission admin   members = ROLES.director
    ├── leads        permission admin   members = ROLES.lead
    ├── reviewers    permission write   members = ROLES.reviewer
    └── coders       permission write   members = ROLES.coder
```

- **org name**: `omcgitea` (consistent with project name; profile isolation still handled by docker compose
  project name `omcgitea-<profile>`)
- **org owner**: `chairman` (admin user, bootstrap's execution identity)
- **repo owner path migration**: `chairman/<repo>` → `omcgitea/<repo>` (bootstrap
  either transfer or directly create under org; see §4 implementation steps)
- **team permissions** use the `permission` field: `admin / write / read`
  - `directors = admin`, `leads = admin`: allows lead to modify branch protection, to merge any PR
  - `reviewers = write`: can review/approve/push to feature branch
  - `coders = write`: can push to feature branch, open PR
- **Direct push to main is still blocked by branch protection push_whitelist** (see §3.3)

### 3.2 Role Query API (used by agent)

```
GET /api/v1/orgs/omcgitea/teams/directors/members  → [{username:"director",...}]
GET /api/v1/orgs/omcgitea/teams/leads/members      → [{username:"agent1",...}]
GET /api/v1/orgs/omcgitea/teams/reviewers/members  → [{username:"agent2"}]
GET /api/v1/orgs/omcgitea/teams/coders/members     → [{username:"agent3",...}]

GET /api/v1/users/{me}/orgs/omcgitea/teams         → List of teams the current agent
                                                       belongs to under omcgitea org
```

Agent's first self-check after startup: call the last call above, record the first team name as its own role into
SOUL.md. Subsequently teammate/role changes are also queried in real time via the first three APIs.

### 3.3 Branch protection (team whitelists)

Gitea's branch protection supports both `*_whitelist_usernames` and
`*_whitelist_teams` simultaneously. Only teams are used; the user list is left empty (except push_whitelist for
chairman used for bootstrap pushing workflow files).

```jsonc
{
  "branch_name": "main",
  "enable_push": true,
  "enable_push_whitelist": true,
  "push_whitelist_usernames": ["chairman"],   // bootstrap pushes .gitea/workflows
  "push_whitelist_teams": [],                  // agent is not allowed to direct push
  "required_approvals": 1,
  "enable_approvals_whitelist": true,
  "approvals_whitelist_username": [],
  "approvals_whitelist_teams": ["reviewers"],  // ★ only APPROVE from reviewer team counts
  "enable_merge_whitelist": true,
  "merge_whitelist_usernames": [],
  "merge_whitelist_teams": ["directors", "leads", "reviewers", "coders"],  // anyone can press merge
  "dismiss_stale_approvals": true,
  "block_on_rejected_reviews": true,
  "block_on_official_review_requests": true,
  "block_on_outdated_branch": true,
  "enable_status_check": true,
  "status_check_contexts": ["closes-issue-check"]
}
```

Because the whitelist is a *team reference* rather than an enumerated user list, branch
protection automatically catches up when team membership changes — no need to rewrite protection.

### 3.4 closes-issue-check Workflow

bootstrap pushes `.gitea/workflows/closes-check.yml` to each repo,
PR body must contain `Closes #<n>`. Before act-runner comes up the check is pending = block, which
is acceptable; the generated per-profile base starts an act-runner, so it goes green in a real run.

---

## 4. Bootstrap Implementation Steps

Execution order (idempotent):

1. **ensure_org** (POST `/api/v1/orgs`)
   - If not exists create `omcgitea` (visibility=public, repo_admin_change_team_access=true)
   - chairman automatically becomes org owner (POST `/api/v1/orgs/{org}/members/chairman` + promotion)
2. **ensure_teams**: create `directors / leads / reviewers / coders`
   - permission respectively `admin / admin / write / write`
   - `units` field contains `repo.code, repo.issues, repo.pulls` (as needed)
3. **ensure_team_membership**: parse ROLES, for each agent
   - PUT `/api/v1/teams/{team_id}/members/{agent}`
   - If that agent is already in another team (role change), first DELETE then PUT
4. **ensure_repo**: create repo under org (POST `/api/v1/orgs/omcgitea/repos`),
   or transfer existing `chairman/<repo>` to org (POST
   `/api/v1/repos/{old_owner}/{repo}/transfer`)
5. **ensure_closes_workflow**: push `.gitea/workflows/closes-check.yml` to `omcgitea/<repo>`
6. **ensure_branch_protection**: use §3.3 team whitelist
7. **purge legacy**: delete old `chairman/<repo>` collaborator settings (if transfer path was taken)

ROLES env is still the sole input to bootstrap; roles.env file is **no longer written** (agents query via API
instead of reading the file).

---

## 5. AGENTS.md / SOUL.md Layering

**Fundamental principle: md files only write the agent's own information (or project rules common to all agents),
absolutely do not write other agent information — that is dynamic, must be queried from Gitea at runtime.**

### 5.1 AGENTS.md (environment injection / common rules)

- Location: `/work/AGENTS.md`, **completely identical** for all agents
- Source: on host `docker/hermes-agent/AGENTS.md` (static file, no placeholders)
- Rendering timing: `cp` to `/work/` at container entrypoint startup (or ro mount)
- Content scope:
  - Project identity (you work in the omcgitea team)
  - Workflow general rules (PR must `Closes #N`, do not @ multiple people, do not review others' PRs
    unless you are reviewer, use issue body edit-in-place instead of comment spam ...)
  - "How to confirm your role and teammates" operational guidance: call
    `GET /orgs/omcgitea/teams/{leads,reviewers,coders}/members`
- **Absolutely do not write**:
  - Specific agent names (except in examples like "call API to query")
  - Specific private responsibilities of a certain role (→ into SOUL.md)

### 5.2 SOUL.md (agent self-managed / individual identity)

- Location: `$HERMES_HOME/SOUL.md` (persistent volume, container restart untouched)
- Source: bootstrap **does not write**, Hermes automatically seeds a default → agent on first startup
  follows AGENTS.md guidance and calls Gitea API to query its own role, writes the following into its SOUL.md:
  - I am \<name>
  - My current role is \<role> (lead/reviewer/coder)
  - Specific requirements of this role for me (agent can copy from AGENTS.md §"Role responsibilities memo"
    — that section is written in AGENTS.md visible to all agents, only "which one I am" is
    private information, into SOUL.md)
  - What I'm good at / what I've learned (agent continually sediments)
- Edited by agent itself, environment **never overwrites**
- Reread when Hermes session rebuilds prompt (compression, model switch, natural invalidate)

### 5.3 Where the Role → Person Mapping Is Stored

**Unique authority = Gitea org team membership**. No md file writes "who teammates are".

If an agent wants to know who the current reviewer is, call
`GET /orgs/omcgitea/teams/reviewers/members`, always gets latest value, zero file sync problem.

---

## 6. Open Design Note

**Role filtering in the router layer is deliberately not implemented.** Before dispatch a sidecar
*could* call `/orgs/omcgitea/teams/{team}/members` to decide whether a given PR notification belongs
to this agent. It does not: delivery is 100% delegated to the Gitea notification model
([`REQUIREMENTS.md`](./REQUIREMENTS.md) §5.4), and adding a second filter would put delivery
semantics in two places. Kept here as a recorded fallback, not a plan.
