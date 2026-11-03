# Acceptance testing: agent teams on real software projects

This build turns Agensh from a ProgramBench experiment runner into a tool for
real repositories. A team of 1–16 agents (optimized for 4–16) works on a
repository toward a goal, merges through CI, and delivers its `main` as a
pull request for people to review. ProgramBench remains as the regression pack.
This guide is for people trying the build on their own projects; the
[design](task_pack_design.md) explains the reasoning.

Build under test: `main` of [microsoft/Agensh](https://github.com/microsoft/Agensh).

## What to expect

| Area | Behavior | Where to look |
|---|---|---|
| Project file | `.agensh/project.toml` names the goal, upstream, checks, team size, budget, network and product owner | [software-project pack](../tasks/software-project/README.md) |
| Import | The upstream base branch becomes the team's `main` with its full history | team repository in Gitea |
| CI gate | PRs merge only when `agensh / pr` (your fast checks) and `agensh/main-health` pass; pushes to `main` run your full suite | PR status checks in Gitea |
| Broken `main` | The breaking merge's author is alerted, only `fix-main` PRs merge, the team is alerted after 15 minutes, the hold lifts after 60 | `main-health.json`, the channel |
| Protected paths | CI workflows, `.agensh/` and your `protected_paths` change only with the product owner's approval (or never, without one) | PR merge box |
| Backlog | A worker's claim citing `#<n>` assigns issue n to it | Gitea issues |
| Upstream sync | Upstream changes are merged 30 minutes before the end and before delivery; conflicts become an issue | `sync.json`, `upstream/<branch>` |
| Network | `auto`: open for a public GitHub upstream, registries-only allowlist otherwise | `prepare.json`, `egress/egress.jsonl` |
| Delivery | `main` is pushed to `agensh/<run-id>` and a GitHub PR is opened (never merged), listing protected-path changes, the sync result and the network | the PR, `delivery.json` |
| Acceptance | `acceptance.main` runs on the delivered head | `acceptance.json` |
| Lifecycle | `pause`, `resume` (fresh sessions plus a project summary), `finalize`, `status`; token budget warns at 90% and pauses at 100% | `run_state.json` |
| Product owner | Optional person in Gitea and Mattermost; their DMs, mentions and comments reach workers mid-turn; hourly digest | the channel, `digests/` |
| Planning | Optional: worker 1 writes `ARCHITECTURE.md` and issues in a `[plan]` PR before the others wake | the `[plan]` PR |
| Peer review | Optional: PRs touching `review_paths` need one peer approval | `agensh/review` status |

## Before you start

1. **Host**: Linux with Docker Engine, Compose v2, cgroup v2, passwordless
   `sudo` for Docker, Python 3.11+, Git, curl, jq, `envsubst`. Install the
   memory slice and reboot guard once, as in the
   [reproduction guide](../REPRODUCE.md#prerequisites). Each worker may use up
   to 64 GiB of memory by default; export `WORKER_MEMORY=16g` (or
   `WORKER_CPUS=auto`) before `profile` on a smaller host. Team state lives
   under the checkout in `.claude-team-data/`.
2. **Model gateway**: put the gateway in `~/.agensh/upstream.env` (mode 600):
   ```
   LLM_UPSTREAM=https://your-gateway.example
   LLM_UPSTREAM_TOKEN=...
   ```
   The model and harness come from [`agent/config/harness.json`](../agent/config/harness.json)
   (see [model API routes](../REPRODUCE.md#model-api-routes)).
3. **Delivery**: for a GitHub upstream, `gh auth login` on the host with push
   access to the repository. Workers never see these credentials. To try
   without delivering, use a local clone as `repo` or set `AGENSH_DELIVERY=off`.
4. **Pick a project**: a repository you own (or a fork), with a test command
   that runs in a few minutes, and a goal one to three PRs' worth for a first
   run. A private repository exercises the allowlist network.

Get the build and check it on your host:

```bash
git clone https://github.com/microsoft/Agensh.git && cd Agensh
python3 -m unittest discover -s tests/unit
SMOKE_PACK=software-project bash tests/smoke/run_smoke.sh
```

The smoke test runs two scripted workers through the real services in about 12
minutes without a model (use `bash tests/smoke/run_isolated.sh /path/to/data-dir`
to keep it inside a Docker-in-Docker container on a shared host).

[`tests/live/run_live.sh`](../tests/live/run_live.sh) is a scripted run with your
model: two Copilot workers get 30 minutes for a small CLI feature (JSON output,
sorting, tests, README) and the script reports delivered commits, acceptance,
CI timeline and token use per worker. It spends real tokens (about 2M in our
first run, which finished in 6 minutes):

```bash
mkdir -p /path/to/data-dir/tmp && install -m 600 ~/.agensh/upstream.env /path/to/data-dir/tmp/upstream.env
bash tests/smoke/run_isolated.sh /path/to/data-dir bash tests/live/run_live.sh
```

## Scenario 1: improve an existing repository

Add `.agensh/project.toml` to your repository (it can stay uncommitted; the path
is what matters):

```toml
pack = "software-project"
name = "widget"
goal = """
Add a --json flag to the CLI that prints the same fields as the table output.
Document it in the README.
"""

[upstream]
repo = "github.com/you/widget"
base_branch = "main"

[acceptance]
pr = ["python3 -m pytest -q -x tests/unit"]
main = ["python3 -m pytest -q"]

[team]
workers = 4

[budget]
hours = 2
max_model_tokens = 30000000

[environment]
base_image = "default-python"   # or any Debian/Ubuntu image with python3
```

Then build the worker image, write the profile and start the run:

```bash
python3 -m agensh.project build   /path/to/widget/.agensh/project.toml --agent-harness codex
python3 -m agensh.project profile /path/to/widget/.agensh/project.toml --agent-harness codex
python3 -m agensh.project run     /path/to/widget/.agensh/project.toml
```

`run` stays in the foreground for the budget; use `tmux` or `nohup`. Ports are in
`.env.software-project-widget` (`EDGE_HTTP_PORT` for Gitea, `EDGE_MM_PORT` for
Mattermost). From your laptop, with the ports from that file:

```bash
ssh -L 23000:localhost:23000 -L 23001:localhost:23001 you@host
```

Open `http://localhost:23000` (Gitea; administrator `chairman`, password
`GITEA_ADMIN_PASSWORD` in the profile) and `http://localhost:23001` (Mattermost;
`mmadmin` / `MATTERMOST_ADMIN_PASSWORD`).

**Check:**
- Issue #1 holds the goal; workers open issues and claim them (`#n` assigned).
- Every merged PR shows passing `agensh / pr` and `agensh/main-health`.
- `main`'s history starts with your repository's history.
- At the end, a PR from `agensh/<run-id>` appears on GitHub with the goal,
  change summary, sensitive paths, upstream and network sections, and nothing
  under `.gitea/` that you did not have before.
- `out/projects/widget/acceptance.json` shows your full suite's result on the
  delivered head.

## Scenario 2: a new project from a goal

```toml
pack = "software-project"
name = "todo-api"
goal_file = "goal.md"           # next to the project file

[workspace]
seed = "empty"

[acceptance]
pr = ["python3 -m pytest -q"]

[team]
workers = 6

[coordination]
planning = true
```

Without an upstream the result is a git bundle,
`out/projects/todo-api/delivery.bundle`. **Check:** worker 1 merges a `[plan]` PR
with `ARCHITECTURE.md` and issues first, the others start after it, and the code
is Python unless the goal says otherwise.

## Scenario 3: with a product owner

Add to the project file:

```toml
[human]
mode = "optional"
username = "owner"
digest = "1h"
```

Rerun `profile`, then `run`. Sign in to Gitea and Mattermost as `owner` with the
password in `.claude-team-data/software-project-<name>/tokens/human-owner.password`
(`sudo cat`). **Check:**
- You are in the `team-task` channel; workers ask you there when the goal is
  unclear and keep working meanwhile.
- A DM to a worker, or a channel post mentioning `@team-worker2`, changes what
  that worker does within its current turn; a post without a mention does not
  interrupt anyone.
- An issue you open is picked up; a comment you leave on a PR reaches its author.
- A PR touching `.agensh/` or your `protected_paths` waits for your approval.
- A digest arrives in the channel every hour.
- Closing issue #1 ends the run and delivers it; a worker closing it is
  reopened (without a product owner, the team's own close ends the run).

## Scenario 4: pause, resume, budget

```bash
python3 -m agensh.project pause    /path/to/.agensh/project.toml
python3 -m agensh.project status   /path/to/.agensh/project.toml
HOURS=1 python3 -m agensh.project resume /path/to/.agensh/project.toml
python3 -m agensh.project finalize /path/to/.agensh/project.toml
```

**Check:** a pause gives workers two minutes to push, then stops every container
and keeps Gitea, Mattermost and the board; resume starts each worker in a fresh
session with a summary of open issues, PRs, recent merges and CI; finalize
delivers a running or paused team. With a small `max_model_tokens`, workers are
warned at 90% and the run pauses at 100%; raise the budget, rerun `profile`,
and `resume`.

## Scenario 5: a private repository

With a private GitHub upstream, `auto` chooses the allowlist. **Check:**
`prepare.json` says why; `pip install` works in a worker while other sites are
refused; `.claude-team-data/<profile>/egress/egress.jsonl` lists every allowed
and denied host. Add internal package indexes with
`[environment] allow_domains = ["pypi.internal.example"]`.

## Results and clean-up

| File in `out/projects/<name>/` | Content |
|---|---|
| `prepare.json` | Base commit, network choice and reason |
| `run_state.json` | Segments and their end reasons |
| `main-health.json` | Broken-`main` timeline |
| `sync.json` | Upstream syncs and conflicts |
| `delivery.json`, `acceptance.json` | Delivered branch or PR, team commits, protected-path changes; acceptance results |
| `digests/`, `service-logs*/` | Progress digests; router, proxy and service logs per segment |

`python3 scripts/team_status.py software-project-<name>` summarizes a live team,
including token use per worker. Remove a finished team's state with
`make clean PROFILE=software-project-<name>` and its outputs with
`sudo rm -rf out/projects/<name>`.

## Known limitations

- `default-python` is the only named base image; other languages need an
  image reference (Debian or Ubuntu with `python3`).
- The model in `harness.json` (and `[team.models]`) must be served by your
  gateway with the harness's wire API.
- Gitea 1.22 cannot check protected files on the push that creates `main`, so
  they are protected right after the import; nothing runs in between.
- Git LFS files are imported as pointer files: the host never fetches LFS
  objects, so workers, CI and acceptance see the pointers, and checks that need
  an LFS file's content fail.
- With `open` networking, fetched content can carry prompt injection and
  workers can read the whole repository. Review every delivered PR.
- The router marks the owner's Mattermost posts urgent only on its live
  connection; posts recovered after a reconnect are delivered, but queued.
- A real-model run is the part least covered so far: the automated tests use
  scripted workers. Your reports on how agents actually behave are the point of
  this round.

## Reporting

Open an issue on [microsoft/Agensh](https://github.com/microsoft/Agensh/issues)
with: the project file (without secrets), harness and model, worker count and
budget, what you expected and what happened, and the run's
`out/projects/<name>/` JSON files and `service-logs/` (check them for secrets
first). For agent behavior, the Mattermost channel export and links to the PRs
help most.
