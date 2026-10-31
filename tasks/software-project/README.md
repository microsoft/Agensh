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

[team]
workers = 4                             # 1-128

[budget]
hours = 2

[environment]
base_image = "default-python"           # or an image ref: Debian/Ubuntu with python3
network = "open"                        # or "offline"; default from pack.toml (open)
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

## Lifecycle

| Hook | Does |
|---|---|
| [`hooks/prepare.py`](hooks/prepare.py) | Clones the upstream base branch with its history (or starts a repository with a README), renders [`templates/`](templates/) into the run's `prompts/` with the goal, checks, language and network rules, and records `prepare.json` |
| [`hooks/export.py`](hooks/export.py) | Clones the team's final `main`; pushes it to the delivery branch and, for GitHub, opens a pull request with the goal, commit count and change summary; never merges. Without an upstream it writes `delivery.bundle`; `AGENSH_DELIVERY=off` keeps delivery local. Records `delivery.json` |
| [`hooks/evaluate.py`](hooks/evaluate.py) | Runs `acceptance.main` on the delivered `main` in the worker image and records `acceptance.json`; failing checks are results, not run failures |

The imported history becomes the team's `main` directly: bootstrap creates the
repository without an initial commit and without the CODEOWNERS commit, so the
delivery branch shares its history with upstream and the pull request shows
only the team's work. GitHub delivery uses the host's `gh` login; workers never
hold upstream credentials.

Workers get their instructions from the core template with this pack's
fragments, the `team-task` channel and the `team` board. The network is open by
default; the model credential still stays in the egress proxy. With open
networking, fetched content can carry prompt injection and workers can read the
whole repository, so use `network = "offline"` for private code until the
allowlist mode is available, and review every delivered pull request.

## Not yet included

CI as a required merge check, protected acceptance files, the broken-`main`
alarm, the issue backlog synchronization, the `allowlist` and `auto` network
modes, upstream sync before delivery, a human product owner and resume follow in
the next steps of the [task pack design](../../docs/task_pack_design.md).
