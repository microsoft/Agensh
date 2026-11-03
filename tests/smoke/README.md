# Stub-harness smoke test

Runs a short team through the real runner (`scripts/team_run.sh`) and team
services, with a scripted ACP harness in place of a model. It checks the
cooperation path end to end without spending tokens, so refactors of the
runner, Compose generation and services can be verified locally.

```bash
bash tests/smoke/run_smoke.sh
```

| File | Purpose |
|---|---|
| `run_smoke.sh` | Builds images, writes a smoke profile, runs the team and checks the results |
| `run_isolated.sh` | Runs `run_smoke.sh` inside a capped Docker-in-Docker daemon with storage under a given directory |
| `stub_acp.py` | Scripted ACP harness mounted over the Pi adapter in each worker |
| `cleanroom.Dockerfile` | Minimal stand-in for a ProgramBench cleanroom with an ELF reference and a README |
| `fake_upstream.py` | Model upstream returning fixed usage, also used by `tests/unit/test_usage_meter.py` |

Each stub worker, on its first prompt, makes two model requests (streamed and
not) through the egress proxy with the key from Pi's generated config, writes a
`CLAIM`, pushes `smoke/<worker>.txt` on its own branch, opens and merges a PR
through the Gitea API, confirms the file on `main` and publishes a
`PATCH_SUMMARY`. Later prompts
end the turn immediately. The worker image is a normal Pi worker; Compose mounts
`stub_acp.py` over `/opt/omcgitea/pi/acp.py` through `COMPOSE_EXTRA_FILES`, so
the entrypoint, ACP bridge, router, board, Gitea, Mattermost, bootstrap, token
service, model proxy and archives are the production ones. The proxy forwards
to `fake_upstream.py`, added as a Compose service on the egress network.

The test passes when:

- every worker's file reaches `main` and every worker's PR is merged,
- every worker has `CLAIM` and `PATCH_SUMMARY` entries on the board,
- the router delivered events to every worker,
- `scripts/team_status.py` reports every worker's containers running, a merged
  PR, and token usage that matches the fake upstream exactly (120 input and 30
  output tokens per request), with no metering errors,
- the runner exits 0 after its budget, the submission contains every
  contribution plus the seeded README, and each worker sealed a shutdown
  archive that the runner verified.

With `SMOKE_PACK=software-project` the team imports a local upstream whose
history is larger than the edge proxy's 100 MiB request limit, and the
delivered head's acceptance includes a `git` command, run on a checkout that
the evaluation container's user does not own.

| Setting | Default | Meaning |
|---|---|---|
| `SMOKE_WORKERS` | 2 | Team size |
| `SMOKE_MINUTES` | 5 | Run budget passed to the runner |
| `SMOKE_KEEP` | 0 | `1` keeps the profile data and containers for inspection |
| `SMOKE_INTERRUPT` | 0 | `1` sends SIGTERM to the runner after the live checks and checks that its teardown still exported and archived |
| `SMOKE_HUMAN` | 1 | software-project: `1` names a product owner (owner approval, urgent routing, digests); `0` keeps protected paths admin-only and makes the run fixed-length |
| `SMOKE_SNAPSHOT` | 0 | software-project: `1` imports a sanitized snapshot without history and checks the replayed delivery |
| `SMOKE_PORT_BASE`, `SMOKE_SUBNET_OCTET` | 26000, 231 | Host ports and Docker subnets of the smoke profile |

Requirements: Docker with Compose v2, passwordless `sudo`, and network access
for the first image builds and pulls. Images use private `agensh-smoke/*` and
`:smoke` tags, so shared experiment tags are never moved. The profile is
`programbench-pandoc-smoke`; the test removes only that profile's data
and `out/smoke/run`. The task ID is a fixed entry from the profile generator's
table, but the cleanroom image comes from `PROGRAMBENCH_DOCKER_ORG=agensh-smoke`
and has nothing to do with ProgramBench's Pandoc task. Evaluation is skipped.

On a shared host, or where the host Docker lacks BuildKit's buildx component,
run the test inside a private daemon instead:

```bash
bash tests/smoke/run_isolated.sh /path/on/a/data/disk/agensh-smoke
```

The host then runs a single privileged `docker:dind` container, capped by
`SMOKE_DIND_CPUS` (default 8) and `SMOKE_DIND_MEMORY` (default 16g; a two-worker run uses about 1.5 GiB). All images,
containers and profile data stay in the inner daemon, whose storage is kept in
`DATA_DIR/docker` as a cache for later runs. Keep the checkout on the same disk
too, because the profile data root lives inside it. Host image tags, networks
and the reboot guard are not affected, and inner images do not use the host's
root disk. The container's `/tmp` is also kept under `DATA_DIR`, and its log is
capped at 10 MB. If the host's default bridge network is unusable (for example,
`docker0` is missing), set `SMOKE_DIND_SUBNET` to an unused subnet such as
`10.231.250.0/24`; the script then creates a private bridge network for the
container and removes it afterwards.

Not covered: native harness behavior (model requests, tools, compaction) and
the idle watchdog, which needs ten minutes of inactivity. Feature work adds a
short real-harness run for those.
