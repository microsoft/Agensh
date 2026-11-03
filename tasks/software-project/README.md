# Software-project task pack

A team works on a real repository toward a goal and delivers its `main` branch
back upstream as a pull request for people to review. The repository is either
imported from an upstream branch, with its history, or started empty for a new
project. The core runtime is described in [`agensh/`](../../agensh/README.md).

## Project file

Each project is described by a TOML file, usually `.agensh/project.toml` in the
target repository (or anywhere for a new project):

```toml
pack = "software-project"
name = "widget"                         # profile: software-project-widget
goal = "Add a --json flag to the widget CLI."   # or goal_file = "docs/goal.md"

[workspace]
seed = "git"                            # "git": import upstream; "empty": new repository

[upstream]
repo = "github.com/acme/widget"         # GitHub, any git URL, or a local path
base_branch = "main"
delivery_branch = "agensh/{run_id}"     # must contain {run_id}

[acceptance]
pr = ["python3 -m unittest -q"]         # quick checks before each merge
main = ["python3 -m unittest"]          # full suite on main; defaults to pr
protected_paths = ["tests/acceptance/**"]   # added to the pack's protected paths
timeout_minutes = 15                    # per CI job

[team]
workers = 4                             # 1-128

[team.models]                           # optional: some workers on another model
3 = "gpt-5.6-mini"                      # worker number = model id served by the gateway

[budget]
hours = 2                               # per run segment
max_model_tokens = 20000000             # team input + output tokens; 0: no limit

[human]
mode = "optional"                       # "none" (default): fully autonomous
username = "owner"                      # Gitea and Mattermost login for the person
digest = "1h"                           # progress digest to the owner; 0 turns it off

[coordination]
planning = true                         # worker 1 plans before the others wake
planning_timeout = "45m"
review_paths = ["src/core/**"]          # PRs touching these need one peer approval

[environment]
base_image = "default-python"           # or an image ref: Debian/Ubuntu with python3
network = "auto"                        # open, allowlist, offline or auto (the default)
allow_domains = ["pypi.internal.example"]   # added to the allowlist's registries
```

`default-python` is `python:3.12-bookworm`. A custom image must be Debian or
Ubuntu based and provide `python3`, because the worker image layers its runtime
with `apt-get` and runs Python tools.

## Running a project

Run from the repository root, with model credentials in `~/.agensh/upstream.env`
as for ProgramBench and the host prerequisites from the
[reproduction guide](../../REPRODUCE.md#prerequisites):

```bash
python3 -m agensh.project build   path/to/.agensh/project.toml --agent-harness codex
python3 -m agensh.project profile path/to/.agensh/project.toml --agent-harness codex
python3 -m agensh.project run     path/to/.agensh/project.toml
```

`build` makes `omcgitea-agent-<base-image>-<harness>:agensh` (`AGENT_IMAGE_TAG`
changes the tag; `AGENT_BASE_IMAGE` the Gitea MCP artifact). `profile` writes
`.env.software-project-<name>` with ports and subnets chosen from 23000 and
`10.217.x` so they stay clear of ProgramBench's table; regenerating keeps the
allocation and passwords. `run` starts [`scripts/team_run.sh`](../../scripts/team_run.sh)
with `TASK=<name>`, the profile and `HOURS` from `[budget]` (an exported `HOURS`
wins). `RUN_ID` names the delivery branch; it defaults to the start time.

## Pause, resume and finalize

```bash
python3 -m agensh.project pause    path/to/.agensh/project.toml   # keep everything; stop the team
python3 -m agensh.project resume   path/to/.agensh/project.toml   # fresh sessions, HOURS more
python3 -m agensh.project finalize path/to/.agensh/project.toml   # sync, deliver, evaluate
python3 -m agensh.project status   path/to/.agensh/project.toml
```

A run segment ends when `[budget] hours` elapse (finalize, after a 15-minute
wrap-up notice), when issue #1 is closed (finalize), or when the token budget is
spent (pause: raise `max_model_tokens`, rerun `profile`, then `resume`).
Without a product owner, the team closing issue #1 also finalizes the run; with
one, only the owner's close does.
`pause` and `finalize` reach a running driver within seconds; `finalize` also
delivers a paused run. Outputs go to `out/projects/<name>/` (`OUT_DIR` changes
it). See the [run lifecycle](../../agensh/README.md#run-lifecycle) for details.

## Lifecycle hooks

| Hook | Does |
|---|---|
| [`hooks/prepare.py`](hooks/prepare.py) | Clones the upstream base branch with its history (or starts a repository with a README), renders [`templates/`](templates/) into the run's `prompts/` with the goal, checks, language and network rules, and records `prepare.json` |
| [`hooks/export.py`](hooks/export.py) | Clones the team's final `main`; pushes it to the delivery branch and, for GitHub, opens a pull request with the goal, commit count and change summary; never merges. Without an upstream it writes `delivery.bundle`; `AGENSH_DELIVERY=off` keeps delivery local. Records `delivery.json` |
| [`hooks/evaluate.py`](hooks/evaluate.py) | Runs `acceptance.main` on the delivered `main` in the worker image and records `acceptance.json`; failing checks are results, not run failures. The checkout belongs to the host user, so the container trusts it (`safe.directory`) and checks can run `git` |

The imported history becomes the team's `main` directly: bootstrap creates the
repository without an initial commit and without the CODEOWNERS commit, so the
delivery branch shares its history with upstream and the pull request shows
only the team's work. GitHub delivery uses the host's `gh` login; workers never
hold upstream credentials.

Git LFS files stay pointer files throughout a run. The prepare, sync and export
hooks clone with the LFS filter turned off, so the host's git-lfs never fetches
objects (which may be missing upstream) or pushes them, and the team's Gitea
holds none. Workers, CI and acceptance see the pointers, so a check that needs
an LFS file's content cannot pass.

Workers get their instructions from the core template with this pack's
fragments, the `team-task` channel and the `team` board. Their events carry
inline context (who commented what, how a thread started; see the
[router](../../mini-router/README.md#runtime-and-event-delivery)), and chat
messages stay under 100 words, with details in issues and PRs.

## Network

| Mode | Workers and CI jobs reach |
|---|---|
| `open` | The internet |
| `allowlist` | Only PyPI, npm, crates.io, the Go proxy, Debian and Ubuntu mirrors, and `allow_domains`, through `egress-filter`; refusals and grants are logged to `$DATA_ROOT/<profile>/egress/egress.jsonl` |
| `offline` | Nothing but the team's services and the model |
| `auto` (default) | `open` for a public GitHub upstream or a new project without one; `allowlist` for a private upstream or one whose visibility cannot be told, such as a local path |

The prepare hook records the chosen mode and why in `prepare.json`, and the
delivery PR lists it with any added domains. The model credential stays in the
egress proxy in every mode. Workers can read the whole repository and fetched
content can carry prompt injection, which is why private code defaults to the
allowlist; review every delivered pull request.

## Backlog and upstream

Gitea issues are the work items: a worker's `CLAIM` cites an issue as `#<n>`,
and the driver assigns the issue to the worker while the claim lives (see
[backlog synchronization](../../agensh/README.md#backlog-synchronization)).

[`hooks/sync.py`](hooks/sync.py) brings the upstream base branch into the team's
`main` 30 minutes before the end of the budget and again before export. The
upstream head is always on the team branch `upstream/<base_branch>`. A clean
merge is pushed to `main` by the administrator; a conflict is never forced:
an issue lists the conflicting files and asks the team to resolve it in a normal
PR. A conflict still open at the final sync is reported in the delivery PR.
`sync.json` records every sync.

## Merge gate

PRs merge only after their checks pass. The prepare hook commits
`.gitea/workflows/agensh.yml`, generated from `[acceptance]`: PRs run `pr` as
the required `agensh / pr` check in the worker image, and every push to `main`
runs `main`. When `main` fails, the author of the breaking merge is alerted and
only `fix-main` PRs can merge until it passes; after 60 minutes the restriction
lifts and the run log records a notice. `.gitea/workflows/**`, `.agensh/**` and
the project's `protected_paths` are Gitea protected files, so no worker PR can
change the checks that gate its work. Export removes the workflow again, so the
delivery pull request carries only the team's changes. See the
[CI merge gate](../../agensh/README.md#ci-merge-gate) for the details.

## Product owner

With `[human] mode = "optional"`, the person signs in to Gitea and Mattermost
as `username` with the password in
`.claude-team-data/<profile>/tokens/human-<username>.password` (through the SSH
port-forward to `EDGE_HTTP_PORT` and `EDGE_MM_PORT`). Workers ask them in the
task channel when the goal is ambiguous and carry on meanwhile; the person's
DMs, mentions of a worker, and issue and PR comments reach that worker
mid-turn. Issues they open become work items. PRs that touch protected paths
merge only after they approve; everything else merges on CI, and the person
reviews the whole change on the delivery PR, where protected-path changes are
listed separately. They get a progress digest in the channel every `digest`.
Closing issue #1 ends the run and delivers it.

