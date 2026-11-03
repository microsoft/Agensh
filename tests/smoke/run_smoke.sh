#!/usr/bin/env bash
# Run a short team on the scripted stub harness through the real runner, then
# check claims, PRs, merges, event delivery, usage, export and shutdown archives.
# SMOKE_PACK selects programbench (default) or software-project.
# Needs Docker, passwordless sudo and network access for the first image builds.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PACK="${SMOKE_PACK:-programbench}"
WORKERS="${SMOKE_WORKERS:-2}"
KEEP="${SMOKE_KEEP:-0}"
INTERRUPT="${SMOKE_INTERRUPT:-0}"
# software-project: name a product owner (1) or keep protected paths admin-only (0).
HUMAN="${SMOKE_HUMAN:-1}"
# software-project: import a sanitized snapshot without history (1) or the full history (0).
SNAPSHOT="${SMOKE_SNAPSHOT:-0}"
PORT_BASE="${SMOKE_PORT_BASE:-26000}"
SUBNET_OCTET="${SMOKE_SUBNET_OCTET:-231}"
IMAGE_ORG=agensh-smoke
PI_VERSION=1.4.0
OUT="$ROOT/out/smoke"
DOCKER=(sudo -n docker)
case "$PACK" in
    programbench)
        TASK=jgm__pandoc.5caad90
        MINUTES="${SMOKE_MINUTES:-5}"
        PROFILE=programbench-pandoc-smoke
        CLEANROOM="$IMAGE_ORG/jgm_1776_pandoc.5caad90:task_cleanroom_v6"
        AGENT_IMAGE=omcgitea-agent-pandoc-pi:smoke
        BOARD=pbench-top
        ;;
    software-project)
        TASK=smoke-widget
        # The CI gate checks run a broken main and its fix through Actions.
        MINUTES="${SMOKE_MINUTES:-10}"
        PROFILE=software-project-smoke-widget
        PROJECT_FILE="$OUT/project/.agensh/project.toml"
        UPSTREAM="$OUT/upstream.git"
        BASE_IMAGE=python:3.12-slim-bookworm
        AGENT_IMAGE=omcgitea-agent-python-3-12-slim-bookworm-pi:smoke
        BOARD=team
        ;;
    *) echo "SMOKE_PACK must be programbench or software-project" >&2; exit 2 ;;
esac
ENV_FILE="$ROOT/.env.$PROFILE"

log() { echo "[smoke $(date -u +%H:%M:%S)] $*" >&2; }
# A command that stops the script under `set -e` names itself in the log.
set -E
trap 'echo "[smoke $(date -u +%H:%M:%S)] FAIL: exit $? at line $LINENO: $BASH_COMMAND" >&2' ERR
die() { log "FAIL: $*"; exit 1; }
profile_value() { awk -F= -v k="$1" '$1==k {print substr($0, length(k) + 2); exit}' "$ENV_FILE"; }

[[ "$WORKERS" =~ ^[1-9][0-9]*$ ]] || die "SMOKE_WORKERS must be a positive integer"
sudo -n true 2>/dev/null || die "passwordless sudo is required"

remove_profile() {
    # Only this smoke profile's containers, data and outputs are removed. Containers
    # left by an earlier run would restart with the daemon, so remove them by label too.
    local stale
    stale="$("${DOCKER[@]}" ps -aq --filter "label=com.docker.compose.project=omcgitea-$PROFILE")"
    [ -z "$stale" ] || "${DOCKER[@]}" rm -f $stale >/dev/null
    if [ -f "$ENV_FILE" ]; then
        make -s clean PROFILE="$PROFILE" >/dev/null 2>&1 || true
        local data
        data="$(profile_value DATA_ROOT)/$PROFILE"
        # make clean stops before deleting data when Compose cannot render; say so.
        [ ! -e "$data" ] || die "make clean left $data behind"
    fi
    sudo -n rm -rf "$OUT/run" "$OUT/project" "$OUT/upstream.git"
}

preserve_failure() {
    # Keep runner outputs (export and service logs) for diagnosis before cleanup.
    sudo -n rm -rf "$OUT/last-failure"
    if [ -d "$OUT/run" ]; then
        sudo -n cp -a "$OUT/run" "$OUT/last-failure"
        sudo -n rm -f "$OUT/last-failure/$TASK/bin/executable"
        sudo -n chown -R "$(id -u):$(id -g)" "$OUT/last-failure"
        log "runner outputs kept in $OUT/last-failure"
    fi
}

sessions() {
    # The ACP session id the router stored for each worker.
    "${DOCKER[@]}" exec "$(container mysql)" mysql -N -B -uroot -p"$(profile_value MYSQL_ROOT_PASSWORD)" -D omcgitea \
        -e "SELECT agent, v FROM agent_kv WHERE k LIKE 'acp_session_id:%' ORDER BY agent" 2>/dev/null
}

project_command() {
    # Background callers use `exec`, so $! is the driver itself and SIGTERM reaches it.
    ${PROJECT_EXEC:-} env OUT_DIR="$OUT/run" RUN_ID=smoke COMPOSE_EXTRA_FILES="$OUT/compose_stub.yml" AGENSH_WAKE_STAGGER_S=5 \
        AGENSH_BRINGUP_SETTLE_S=5 AGENSH_PAUSE_GRACE_S=10 AGENSH_TOKEN_CHECK_S=10 AGENSH_ISSUE_CHECK_S=10 \
        DOCKER="sudo -n docker" \
        python3 -m agensh.project "$@" "$PROJECT_FILE"
}

check_lifecycle() {
    # Pause keeps every piece of state; resume continues with fresh sessions and the
    # resume message; the resumed segment then finalizes and delivers.
    local runner="$1" before after resumed rc=0 state
    # The budget is calibrated for the default two workers.
    [ "$WORKERS" != 2 ] || grep -q 'token budget at 9[0-9]%' "$OUT/run.log" \
        || die "no token budget warning above 90% in $OUT/run.log"
    before="$(sessions)"
    [ -n "$before" ] || die "no stored ACP sessions before the pause"
    log "pausing the team"
    project_command pause >/dev/null || die "pause request failed"
    wait "$runner" || rc=$?
    [ "$rc" = 0 ] || die "the paused runner exited $rc; see $OUT/run.log"
    state="$(project_command status | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])')"
    [ "$state" = paused ] || die "run state is $state after the pause"
    [ -z "$("${DOCKER[@]}" ps -q --filter "label=com.docker.compose.project=omcgitea-$PROFILE")" ] \
        || die "containers still run after the pause"
    sudo -n test -d "$(profile_value DATA_ROOT)/$PROFILE/gitea" || die "the pause did not keep the team's state"
    log "paused: containers stopped, state kept"

    : > "$OUT/resume.log"
    (HOURS="$(python3 -c 'print(3 / 60)')" PROJECT_EXEC=exec project_command resume >> "$OUT/resume.log" 2>&1) &
    resumed=$!
    for _ in $(seq 1 60); do
        grep -q 'wake complete' "$OUT/resume.log" && break
        kill -0 "$resumed" 2>/dev/null || die "resume exited early; see $OUT/resume.log"
        sleep 5
    done
    grep -q 'cleared stored ACP sessions' "$OUT/resume.log" || die "resume did not clear the stored sessions"
    for _ in $(seq 1 12); do
        after="$(sessions)"
        [ -n "$after" ] && [ "$(echo "$after" | wc -l)" = "$WORKERS" ] && [ "$after" != "$before" ] && break
        sleep 5
    done
    [ "$after" != "$before" ] && [ "$(echo "$after" | wc -l)" = "$WORKERS" ] || die "workers did not start fresh sessions"
    log "resumed: every worker has a fresh session"
    wait "$resumed" || rc=$?
    [ "$rc" = 0 ] || die "the resumed runner exited $rc; see $OUT/resume.log"
    state="$(project_command status | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])')"
    [ "$state" = finalized ] || die "run state is $state after the resumed segment"
    log "the resumed segment finalized"
}

smoke_env() {
    # The egress proxy forwards to tests/smoke/fake_upstream.py, which reports fixed usage.
    env LLM_UPSTREAM=http://fake-upstream:8080 LLM_UPSTREAM_TOKEN=smoke-unused \
        AGENT_IMAGE_TAG=smoke AGENT_BASE_IMAGE="$IMAGE_ORG/agent-base:local" \
        MINI_ROUTER_IMAGE="$IMAGE_ORG/mini-router:local" BOARD_IMAGE="$IMAGE_ORG/board:local" \
        BOOTSTRAP_IMAGE="$IMAGE_ORG/bootstrap:local" SECRET_SERVICE_IMAGE="$IMAGE_ORG/secret-service:local" \
        DOCKER="sudo -n docker" "$@"
}

make_upstream() {
    # A tiny Python project with a test suite, as a local upstream. A fixture added and
    # removed again makes its history larger than the edge proxy's 100 MiB request limit,
    # as a large repository's is, so the seed push must pass the proxy's Git route.
    local work="$OUT/upstream-work"
    rm -rf "$work" "$UPSTREAM"
    git init -q --initial-branch=main "$work"
    printf '%s\n' 'def greet(name):' '    return f"hello {name}"' > "$work/widget.py"
    git -C "$work" add . && git -C "$work" -c user.name=Smoke -c user.email=smoke@localhost commit -qm "Add widget"
    printf '%s\n' 'import unittest' 'from widget import greet' '' 'class GreetTest(unittest.TestCase):' \
        '    def test_greet(self):' '        self.assertEqual(greet("x"), "hello x")' > "$work/test_widget.py"
    # Stands in for held-out data that a snapshot import's sanitize script removes.
    echo "held-out answers" > "$work/holdout.txt"
    git -C "$work" add . && git -C "$work" -c user.name=Smoke -c user.email=smoke@localhost commit -qm "Test widget"
    head -c 110M /dev/urandom > "$work/fixture.dat"
    git -C "$work" add . && git -C "$work" -c user.name=Smoke -c user.email=smoke@localhost commit -qm "Add a large fixture"
    git -C "$work" rm -q fixture.dat
    git -C "$work" -c user.name=Smoke -c user.email=smoke@localhost commit -qm "Remove the large fixture"
    git clone -q --bare "$work" "$UPSTREAM"
    rm -rf "$work"
    mkdir -p "$(dirname "$PROJECT_FILE")"
    # Outside the team's repository: the sanitize script and data only the final evaluation sees.
    local private="$OUT/private"
    rm -rf "$private" && mkdir -p "$private"
    printf '#!/bin/sh\nrm -f "$1/holdout.txt"\n' > "$private/sanitize.sh" && chmod 755 "$private/sanitize.sh"
    echo "final answers" > "$private/answers.txt"
    cat > "$private/check_model.py" <<'PY'
import json, os, urllib.request
request = urllib.request.Request(os.environ['AGENSH_MODEL_BASE'] + '/v1/responses', method='POST',
                                 data=json.dumps({'model': 'fake'}).encode(), headers={'Content-Type': 'application/json'})
assert urllib.request.urlopen(request, timeout=30).status == 200
print('model route reachable from the final evaluation')
PY
    cat > "$PROJECT_FILE" <<EOF
pack = "software-project"
name = "$TASK"
goal = "Smoke test: each worker adds one file through a merged pull request."
$([ "$SNAPSHOT" = 1 ] && printf '[workspace]\nhistory = "snapshot"\nsanitize = "%s"\n' "$private/sanitize.sh")
[upstream]
repo = "$UPSTREAM"
[acceptance]
pr = ["python3 -m unittest -q"]
# Evaluation runs git on a checkout that the container's user does not own.
main = ["python3 -m unittest -q", "git log -1 --format=%H"]
final = ["python3 -m unittest -q", "git log -1 --format=%H", "test -s /private/answers.txt", "python3 /private/check_model.py"]
private_dir = "$private"
[team]
workers = $WORKERS
$([ "$WORKERS" -ge 2 ] && printf '[team.models]\n# Worker 2'"'"'s requests go to its own model, as for a cheaper reviewer role.\n2 = "smoke-reviewer-model"\n')
[budget]
# Two workers' stubs make four requests of 150 tokens and a worker one more through the model
# route: 91% of this, enough for the warning. Other team sizes get room instead (no warning
# check). The final evaluation's request is outside the budget.
max_model_tokens = $([ "$WORKERS" = 2 ] && echo 820 || echo $((1000 * WORKERS)))
# Without a product owner the run keeps its full length: a worker's close of #1 is reopened.
fixed_length = $([ "$HUMAN" = 1 ] && echo false || echo true)
[human]
mode = "$([ "$HUMAN" = 1 ] && echo optional || echo none)"
username = "owner"
digest = "1m"
[coordination]
planning = true
planning_timeout = "5m"
$([ "$WORKERS" -ge 2 ] && echo 'review_paths = ["review/**"]')
[environment]
base_image = "$BASE_IMAGE"
EOF
}

build_images() {
    log "building images (cached after the first run)"
    "${DOCKER[@]}" build -q -f agent/Dockerfile.base -t "$IMAGE_ORG/agent-base:local" agent/ >/dev/null
    "${DOCKER[@]}" build -q -t "$IMAGE_ORG/mini-router:local" mini-router/ >/dev/null
    "${DOCKER[@]}" build -q -t "$IMAGE_ORG/board:local" board-service/ >/dev/null
    if [ "$PACK" = programbench ]; then
        "${DOCKER[@]}" build -q -f tests/smoke/cleanroom.Dockerfile -t "$CLEANROOM" tests/smoke/ >/dev/null
        "${DOCKER[@]}" build -q -f agent/Dockerfile \
            --build-arg TASK_IMAGE="$CLEANROOM" --build-arg AGENT_HARNESS=pi \
            --build-arg PI_CLI_VERSION="$PI_VERSION" \
            --build-arg AGENT_BASE_IMAGE="$IMAGE_ORG/agent-base:local" -t "$AGENT_IMAGE" . >/dev/null
    else
        [ "$(smoke_env python3 -m agensh.project build "$PROJECT_FILE" --agent-harness pi \
            --harness-version "$PI_VERSION" 2>"$OUT/build.log" | tail -1)" = "$AGENT_IMAGE" ] \
            || die "project image build failed; see $OUT/build.log"
    fi
}

write_profile() {
    if [ "$PACK" = programbench ]; then
        smoke_env ENV_DIR="$ROOT" TASKS="$TASK" WORKERS="$WORKERS" PROFILE_SUFFIX=smoke \
            PORT_BASE="$PORT_BASE" SUBNET_OCTET="$SUBNET_OCTET" \
            bash tasks/programbench/scripts/gen_env.sh --agent-harness pi --harness-version "$PI_VERSION" >/dev/null
    else
        smoke_env python3 -m agensh.project profile "$PROJECT_FILE" --agent-harness pi \
            --harness-version "$PI_VERSION" >/dev/null
    fi
    [ "$(profile_value AGENT_IMAGE)" = "$AGENT_IMAGE" ] || die "unexpected AGENT_IMAGE in $ENV_FILE"
    {
        echo "# Generated by tests/smoke/run_smoke.sh: run the stub harness in place of Pi."
        echo "services:"
        echo "  fake-upstream:"
        echo "    image: python:3.13-slim"
        echo "    networks: [egress]"
        echo "    volumes:"
        echo "      - $ROOT/tests/smoke/fake_upstream.py:/opt/fake_upstream.py:ro"
        echo "    command: [python3, /opt/fake_upstream.py]"
        for i in $(seq 1 "$WORKERS"); do
            echo "  agent-worker$i:"
            echo "    volumes:"
            echo "      - $ROOT/tests/smoke/stub_acp.py:/opt/omcgitea/pi/acp.py:ro"
        done
    } > "$OUT/compose_stub.yml"
}

gitea_api() {
    curl -fsS -u "$(profile_value GITEA_ADMIN_USER):$(profile_value GITEA_ADMIN_PASSWORD)" \
        "http://localhost:$(profile_value EDGE_HTTP_PORT)/api/v1$1"
}

gitea_clone_url() {
    echo "http://$(profile_value GITEA_ADMIN_USER):$(profile_value GITEA_ADMIN_PASSWORD)@localhost:$(profile_value EDGE_HTTP_PORT)/$(profile_value ORG_NAME)/main.git"
}

container() {
    "${DOCKER[@]}" ps --filter "label=com.docker.compose.project=omcgitea-$PROFILE" \
        --filter "label=com.docker.compose.service=$1" --format '{{.Names}}' | head -1
}

contributions_on_main() {
    local org count=0 i
    org="$(profile_value ORG_NAME)"
    for i in $(seq 1 "$WORKERS"); do
        # Gitea answers 200 for an empty repository, so check that the file itself came back.
        gitea_api "/repos/$org/main/contents/smoke/$org-worker$i.txt?ref=main" 2>/dev/null \
            | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(not (isinstance(d, dict) and d.get("type") == "file" and d.get("path") == sys.argv[1]))' \
                "smoke/$org-worker$i.txt" 2>/dev/null && count=$((count + 1))
    done
    echo "$count"
}

check_live_state() {
    # Board entries and event rows are only readable while the stack is up.
    local org board mysql
    org="$(profile_value ORG_NAME)"
    board="$(container board-service)"
    mysql="$(container mysql)"
    [ -n "$board" ] && [ -n "$mysql" ] || die "board or mysql container not found"

    local merged
    merged="$(gitea_api "/repos/$org/main/pulls?state=closed&limit=50" \
        | python3 -c 'import json,sys; print(sum(1 for p in json.load(sys.stdin) if p.get("merged")))')"
    [ "$merged" -ge "$WORKERS" ] || die "expected $WORKERS merged PRs, found $merged"
    log "merged PRs: $merged"

    "${DOCKER[@]}" exec "$board" python3 -c '
import json, sys, urllib.request
workers, org, board = int(sys.argv[1]), sys.argv[2], sys.argv[3]
url = f"http://127.0.0.1:8660/board/{board}/read_all?viewer=harness"
entries = json.load(urllib.request.urlopen(url, timeout=10))["entries"]
for i in range(1, workers + 1):
    agent = f"{org}-worker{i}"
    kinds = {e["type"] for e in entries if e["thread_id"] == agent}
    missing = {"CLAIM", "PATCH_SUMMARY"} - kinds
    if missing:
        sys.exit(f"{agent} has no board {sorted(missing)}")
print(f"board entries: {len(entries)}")
' "$WORKERS" "$org" "$BOARD" >&2 || die "board check failed"

    check_usage
    check_agents_md
    if [ "$PACK" = software-project ]; then
        check_imported_history
        check_backlog
        # The assignment above notifies each worker about issue #1.
        # A worker's own actions are not events for it, so a team of one has none.
        [ "$WORKERS" -lt 2 ] || check_event_context
        check_allowlist
        # A team of one has no planning phase: its only worker starts at once.
        [ "$WORKERS" -lt 2 ] || check_planning
        [ "$WORKERS" -lt 2 ] || check_models
        check_model_route
        if [ "$HUMAN" = 1 ]; then
            check_human
        else
            check_issue_reopened
            log "fixed-length run: a worker's close of #1 was reopened"
        fi
        python3 tests/smoke/check_gate.py "$ENV_FILE" "$OUT/run/$TASK" || die "CI gate check failed"
        [ "$SNAPSHOT" = 1 ] || push_upstream_change
    fi

    local rows
    rows="$("${DOCKER[@]}" exec "$mysql" mysql -N -B -uroot -p"$(profile_value MYSQL_ROOT_PASSWORD)" \
        -D omcgitea -e "SELECT agent, SUM(state='sent') FROM events GROUP BY agent" 2>/dev/null)"
    log "events delivered per agent: $(echo "$rows" | tr '\t\n' '= ')"
    for i in $(seq 1 "$WORKERS"); do
        echo "$rows" | awk -v a="$org-worker$i" '$1==a && $2>0 {found=1} END {exit !found}' \
            || die "$org-worker$i has no delivered events"
    done
}

check_agents_md() {
    # The worker's entrypoint must render exactly what the shared renderer predicts.
    local expected="$OUT/expected-AGENTS.md" worker
    if [ "$PACK" = programbench ]; then
        python3 tools/render_snapshot.py --out "$OUT/snapshot" --workers "$WORKERS" --harness pi >/dev/null \
            || die "render snapshot failed"
        cp "$OUT/snapshot/worker/w$(printf '%02d' "$WORKERS")/AGENTS.md" "$expected"
    else
        env -i PATH="$PATH" AGENT_NAME="$(profile_value ORG_NAME)-worker1" GITEA_ORG="$(profile_value ORG_NAME)" \
            AGENSH_WORKERS="$WORKERS" TASK_CHANNEL=team-task \
            bash agent/render_agents.sh prompts/agents.txt "$OUT/run/$TASK/prompts" > "$expected"
    fi
    worker="$(container agent-worker1)"
    "${DOCKER[@]}" exec "$worker" cat /work/AGENTS.md > "$OUT/agents-worker1.md" \
        || die "cannot read AGENTS.md from $worker"
    diff -u "$expected" "$OUT/agents-worker1.md" >&2 || die "worker AGENTS.md differs from the expected rendering"
    log "worker AGENTS.md matches the expected rendering ($(wc -c < "$expected") bytes)"
}

check_imported_history() {
    # main must descend from the upstream base, so the delivery PR shares its history.
    local base check="$OUT/gitea-main"
    base="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["base_sha"])' "$OUT/run/$TASK/prepare.json")"
    rm -rf "$check"
    git clone -q "$(gitea_clone_url)" "$check" || die "cannot clone the team repository"
    if [ "$SNAPSHOT" = 1 ]; then
        # The team sees the sanitized tree only: a snapshot commit and the workflow, no history.
        [ "$(git -C "$check" rev-list --max-parents=0 HEAD | wc -l)" = 1 ] \
            && git -C "$check" log -1 --format=%s "$(git -C "$check" rev-list --max-parents=0 HEAD)" | grep -q '^Snapshot of ' \
            || die "team main does not start from the snapshot commit"
        [ ! -e "$check/holdout.txt" ] || die "the sanitize script's file reached the team"
        ! git -C "$check" cat-file -e "$base^{commit}" 2>/dev/null || die "upstream commits reached the team"
        log "team main is a sanitized snapshot of upstream ${base:0:12}, without its history"
        rm -rf "$check"
        return
    fi
    git -C "$check" merge-base --is-ancestor "$base" HEAD || die "team main does not descend from upstream $base"
    [ "$(git -C "$check" rev-list --count "$base")" = 4 ] || die "upstream history was not imported in full"
    # Only the product owner's CODEOWNERS from the prepare hook, never bootstrap's.
    if [ "$HUMAN" = 1 ]; then
        grep -q 'Generated by Agensh' "$check/.gitea/CODEOWNERS" || die "the product owner's CODEOWNERS is missing"
    else
        [ ! -e "$check/.gitea/CODEOWNERS" ] || die "bootstrap added CODEOWNERS to the imported history"
    fi
    [ -f "$check/.gitea/workflows/agensh.yml" ] || die "the team workflow is not on main"
    log "team main descends from upstream ${base:0:12} with its full history"
    rm -rf "$check"
}

check_event_context() {
    # event_context = "inline": Gitea events name who wrote what, not just the title.
    local inline
    inline="$("${DOCKER[@]}" exec "$(container mysql)" mysql -N -B -uroot -p"$(profile_value MYSQL_ROOT_PASSWORD)" -D omcgitea \
        -e "SELECT COUNT(*) FROM events WHERE source = 'gitea' AND JSON_UNQUOTE(JSON_EXTRACT(payload, '\$.summary')) LIKE '% by @%'" 2>/dev/null)"
    [ "${inline:-0}" -gt 0 ] || die "no Gitea event carries inline context (author and text)"
    log "inline event context: $inline Gitea event(s) name their author and text"
}

check_backlog() {
    # Each stub's claim cites #1, so the driver assigns issue #1 to every worker.
    local org want got i
    org="$(profile_value ORG_NAME)"
    want="$(for i in $(seq 1 "$WORKERS"); do echo "$org-worker$i"; done | sort | tr '\n' ' ')"
    for _ in $(seq 1 12); do
        got="$(gitea_api "/repos/$org/main/issues/1" | python3 -c 'import json,sys; print(" ".join(sorted(a["login"] for a in json.load(sys.stdin).get("assignees") or [])) + " ")')"
        [ "$got" = "$want" ] && break
        sleep 10
    done
    [ "$got" = "$want" ] || die "issue #1 assignees are '$got', expected '$want' from the claims"
    log "claims citing #1 assigned it to: $got"
}

check_allowlist() {
    # A local upstream has unknown visibility, so `auto` chose the allowlist.
    local worker log_file
    worker="$(container agent-worker1)"
    [ "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["network"])' "$OUT/run/$TASK/prepare.json")" = allowlist ] \
        || die "auto did not choose the allowlist for a local upstream"
    [ "$("${DOCKER[@]}" exec "$worker" curl -sS -o /dev/null -w '%{http_code}' --max-time 60 https://pypi.org/simple/pip/)" = 200 ] \
        || die "a worker cannot reach PyPI through egress-filter"
    ! "${DOCKER[@]}" exec "$worker" curl -sS -o /dev/null --max-time 20 https://example.com/ 2>/dev/null \
        || die "a worker reached example.com on the allowlist network"
    ! "${DOCKER[@]}" exec "$worker" curl --noproxy '*' -sS -o /dev/null --max-time 10 https://pypi.org/ 2>/dev/null \
        || die "a worker reached the internet without the proxy"
    log_file="$(profile_value DATA_ROOT)/$PROFILE/egress/egress.jsonl"
    sudo -n grep -q '"host": "example.com", "port": 443, "decision": "denied"' "$log_file" \
        || die "egress-filter did not log the denied request"
    log "allowlist: PyPI through egress-filter, example.com refused and logged, no direct egress"
}

check_models() {
    # [team.models]: worker 2's model requests went to its own model.
    local usage
    usage="$(profile_value DATA_ROOT)/$PROFILE/usage/usage.jsonl"
    sudo -n python3 - "$usage" "$(profile_value ORG_NAME)" <<'CHECK' >&2 || die "per-worker models were not applied"
import json, sys
records = [json.loads(line) for line in open(sys.argv[1])]
models = {}
for record in records:
    models.setdefault(record['agent'], set()).add(record['model'])
org = sys.argv[2]
if models.get(f'{org}-worker2') != {'smoke-reviewer-model'} or 'smoke-reviewer-model' in models.get(f'{org}-worker1', set()):
    sys.exit(f'unexpected models per worker: {models}')
print(f'models per worker: { {k: sorted(v) for k, v in sorted(models.items())} }')
CHECK
}

check_model_route() {
    # Workers reach the model through the proxy's unmodified /raw route, with no key.
    local worker
    worker="$(container agent-worker1)"
    "${DOCKER[@]}" exec "$worker" python3 -c 'import json, os, urllib.request
r = urllib.request.Request(os.environ["AGENSH_MODEL_BASE"] + "/v1/responses", method="POST",
    data=json.dumps({"model": "fake"}).encode(), headers={"Content-Type": "application/json"})
assert urllib.request.urlopen(r, timeout=30).status == 200' || die "a worker cannot use AGENSH_MODEL_BASE"
    sudo -n grep -q '"agent":"project"' "$(profile_value DATA_ROOT)/$PROFILE/usage/usage.jsonl" \
        || die "the model route's request was not metered as project"
    log "model route: a worker called the model through AGENSH_MODEL_BASE, metered as project"
}

check_planning() {
    # Worker 1 planned first; its `[plan]` PR woke the others.
    grep -q 'plan merged (PR #' "$OUT/run.log" || die "the others did not wake on the merged [plan] PR"
    log "planning: worker 1's [plan] PR woke the team"
}

check_human() {
    # The owner's accounts exist; a channel mention is urgent for that worker only;
    # progress digests are posted to the owner.
    local org password
    org="$(profile_value ORG_NAME)"
    password="$(sudo -n cat "$(profile_value DATA_ROOT)/$PROFILE/tokens/human-owner.password")"
    gitea_api "/users/owner" >/dev/null || die "the product owner has no Gitea account"
    python3 - "$(profile_value EDGE_MM_PORT)" "$password" "$org" <<'POST' >&2 || die "the owner cannot post in the task channel"
import json, sys, urllib.request
port, password, org = sys.argv[1:4]
base = f'http://localhost:{port}/api/v4'
def call(method, path, body=None, token=None):
    request = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json', **({'Authorization': f'Bearer {token}'} if token else {})})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.headers.get('Token'), json.loads(response.read() or b'null')
token, _ = call('POST', '/users/login', {'login_id': 'owner', 'password': password})
_, team = call('GET', f'/teams/name/{org}', token=token)
_, channel = call('GET', f'/teams/{team["id"]}/channels/name/team-task', token=token)
call('POST', '/posts', {'channel_id': channel['id'], 'message': f'@{org}-worker1 please keep the CLI output stable'}, token=token)
print('owner posted a mention in team-task')
POST
    local mysql urgent=0
    mysql="$(container mysql)"
    for _ in $(seq 1 12); do
        urgent="$("${DOCKER[@]}" exec "$mysql" mysql -N -B -uroot -p"$(profile_value MYSQL_ROOT_PASSWORD)" -D omcgitea \
            -e "SELECT agent, COUNT(*) FROM events WHERE JSON_EXTRACT(payload, '\$.urgent') = true GROUP BY agent" 2>/dev/null)"
        [ -n "$urgent" ] && break
        sleep 5
    done
    [ "$(echo "$urgent" | awk '{print $1}')" = "$org-worker1" ] || die "the owner's mention was not urgent for worker1 only: '$urgent'"
    for _ in $(seq 1 18); do
        ls "$OUT/run/$TASK/digests/"digest-*.md >/dev/null 2>&1 && break
        sleep 5
    done
    ls "$OUT/run/$TASK/digests/"digest-*.md >/dev/null 2>&1 || die "no progress digest was posted"
    # Only the owner ends the run by closing issue #1; a worker's close is reopened.
    check_issue_reopened
    log "product owner: accounts exist, a mention was urgent for $org-worker1 only, digests posted, a worker's close of #1 was reopened"
}

check_issue_reopened() {
    # A worker's close of issue #1 does not end the run: with a product owner, or in a
    # fixed-length run without one ([budget] fixed_length).
    local org token state=closed
    org="$(profile_value ORG_NAME)"
    token="$(sudo -n cat "$(profile_value DATA_ROOT)/$PROFILE/tokens/agent-$org-worker1.token")"
    curl -fsS -X PATCH -H "Authorization: token $token" -H 'Content-Type: application/json' -d '{"state":"closed"}' \
        "http://localhost:$(profile_value EDGE_HTTP_PORT)/api/v1/repos/$org/main/issues/1" >/dev/null \
        || die "worker1 could not close issue #1"
    for _ in $(seq 1 12); do
        state="$(gitea_api "/repos/$org/main/issues/1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])')"
        [ "$state" = open ] && break
        sleep 5
    done
    [ "$state" = open ] || die "issue #1 closed by a worker was not reopened"
}

push_upstream_change() {
    # Upstream moves during the run; the final sync must bring it into the delivery.
    local work="$OUT/upstream-change"
    rm -rf "$work"
    git clone -q "$UPSTREAM" "$work"
    echo "added upstream during the run" > "$work/upstream_note.txt"
    git -C "$work" add upstream_note.txt
    git -C "$work" -c user.name=Smoke -c user.email=smoke@localhost commit -qm "Upstream note"
    git -C "$work" push -q origin HEAD:main
    rm -rf "$work"
    log "pushed a new upstream commit for the final sync"
}

check_usage() {
    # Each stub worker makes two Responses requests; the fake upstream reports
    # 120 input and 30 output tokens per request.
    local status="$OUT/status.json"
    python3 scripts/team_status.py "$PROFILE" > "$OUT/status.txt" 2>&1 || die "team_status failed"
    python3 scripts/team_status.py --json "$PROFILE" > "$status" || die "team_status --json failed"
    sed 's/^/  /' "$OUT/status.txt" >&2
    python3 - "$status" "$WORKERS" <<'CHECK' >&2 || die "usage check failed"
import json, sys
status, workers = json.load(open(sys.argv[1])), int(sys.argv[2])
if status['errors']:
    sys.exit(f"status errors: {status['errors']}")
rows = {row['agent']: row for row in status['workers']}
if len(rows) != workers:
    sys.exit(f'expected {workers} workers, got {len(rows)}')
for agent, row in rows.items():
    usage = row['usage']
    if usage['requests'] < 2 or usage['errors']:
        sys.exit(f'{agent}: unexpected usage {usage}')
    if usage['input_tokens'] != 120 * usage['requests'] or usage['output_tokens'] != 30 * usage['requests']:
        sys.exit(f'{agent}: token totals do not match the fake upstream: {usage}')
    if row['worker'] != 'running' or row['router'] != 'running' or not row['pulls'].get('merged'):
        sys.exit(f'{agent}: unexpected state {row}')
print(f"usage metered for {workers} workers; team requests={status['team_usage']['requests']}")
CHECK
}

check_archives() {
    local archives
    archives="$(sudo -n find "$(profile_value DATA_ROOT)/$PROFILE/agents" -path '*/shutdown/*/state.tar.gz' | wc -l)"
    [ "$archives" -ge "$WORKERS" ] || die "expected $WORKERS shutdown archives, found $archives"
    echo "$archives"
}

check_outputs() {
    local task_out="$OUT/run/$TASK" org listing archives
    org="$(profile_value ORG_NAME)"
    archives="$(check_archives)"
    if [ "$PACK" = programbench ]; then
        [ ! -e "$task_out/EXPORT_FAILED" ] || die "submission export failed"
        # Re-packed archives list entries as ./path; compare without that prefix.
        listing="$(tar -tzf "$task_out/submission.tar.gz" | sed 's|^\./||')" || die "submission.tar.gz unreadable"
        for i in $(seq 1 "$WORKERS"); do
            grep -qx "smoke/$org-worker$i.txt" <<<"$listing" || die "submission lacks smoke/$org-worker$i.txt"
        done
        grep -qx "README.md" <<<"$listing" || die "submission lacks the seeded README.md"
        log "submission has every contribution; $archives shutdown archives verified"
        return
    fi
    python3 - "$task_out" "$UPSTREAM" "$WORKERS" "$org" "$INTERRUPT" "$SNAPSHOT" <<'CHECK' >&2 || die "delivery check failed"
import json, subprocess, sys
from pathlib import Path
task_out, upstream, workers, org, interrupted = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5] == '1'
snapshot = sys.argv[6] == '1'
delivery = json.loads((task_out / 'delivery.json').read_text())
if delivery.get('mode') != 'branch':
    sys.exit(f'unexpected delivery {delivery}')
branch, base = delivery['branch'], delivery['base_sha']
git = lambda *a: subprocess.run(['git', '-C', upstream, *a], capture_output=True, text=True)
if git('merge-base', '--is-ancestor', base, branch).returncode != 0:
    sys.exit(f'{branch} does not descend from the upstream base {base}')
files = set(git('ls-tree', '-r', '--name-only', branch).stdout.split())
missing = {f'smoke/{org}-worker{i}.txt' for i in range(1, workers + 1)} - files
if '.gitea/workflows/agensh.yml' in files or '.gitea/CODEOWNERS' in files:
    sys.exit(f'{branch} still contains the team workflow or CODEOWNERS')
prepare = json.loads((task_out / 'prepare.json').read_text())
if prepare.get('human') and '.agensh/acceptance.txt' not in delivery.get('sensitive_changes', []):
    sys.exit(f'the owner-approved protected change is not listed: {delivery.get("sensitive_changes")}')
if missing or not {'widget.py', 'test_widget.py'} <= files:
    sys.exit(f'{branch} lacks {sorted(missing)} or the upstream files: {sorted(files)}')
if delivery['commits'] < workers:
    sys.exit(f'expected at least {workers} new commits, got {delivery["commits"]}')
if snapshot:
    # Replayed onto upstream as one commit; the sanitized file is upstream's own, untouched.
    if git('rev-parse', f'{branch}~1').stdout.strip() != base or 'holdout.txt' not in files:
        sys.exit(f'{branch} is not one replayed commit on {base[:12]} with the upstream files')
if not interrupted and not snapshot:
    # The upstream commit pushed during the run arrived through a sync (on resume or final).
    if 'upstream_note.txt' not in files or delivery.get('sync') not in ('merged', 'up-to-date'):
        sys.exit(f'the final upstream sync is missing: sync={delivery.get("sync")}')
if not interrupted:
    acceptance = json.loads((task_out / 'acceptance.json').read_text())
    # The final commands run git on the checkout, read the private directory and call
    # the model route.
    if len(acceptance['results']) != 4 or not acceptance['all_passed'] or acceptance['head'] != delivery['head']:
        sys.exit(f'acceptance did not pass on the delivered head: {acceptance}')
    git_log = next(r for r in acceptance['results'] if r['command'].startswith('git log'))
    if delivery['head'] not in git_log['output_tail']:
        sys.exit(f'git did not read the delivered checkout during acceptance: {git_log}')
print(f'delivered {branch}: {delivery["commits"]} commit(s) on upstream {base[:12]}'
      + ('' if interrupted else '; acceptance passed on the delivered head'))
CHECK
    log "delivery verified; $archives shutdown archives verified"
}

main() {
    mkdir -p "$OUT"
    remove_profile
    [ "$PACK" = software-project ] && make_upstream
    build_images
    write_profile
    trap 'rc=$?; [ "$rc" = 0 ] || preserve_failure; [ "$KEEP" = 1 ] || remove_profile; exit $rc' EXIT

    local hours
    hours="$(python3 -c "print($MINUTES / 60)")"
    log "running $WORKERS stub workers of $PACK for $MINUTES minutes (log: $OUT/run.log)"
    if [ "$PACK" = programbench ]; then
        env TASK="$TASK" PROFILE="$PROFILE" HOURS="$hours" OUT_DIR="$OUT/run" SKIP_EVAL=1 \
            PROGRAMBENCH_DOCKER_ORG="$IMAGE_ORG" COMPOSE_EXTRA_FILES="$OUT/compose_stub.yml" \
            AGENSH_WAKE_STAGGER_S=5 AGENSH_BRINGUP_SETTLE_S=5 \
            bash scripts/team_run.sh > "$OUT/run.log" 2>&1 &
    else
        (HOURS="$hours" PROJECT_EXEC=exec project_command run > "$OUT/run.log" 2>&1) &
    fi
    local runner=$!

    local deadline=$((SECONDS + MINUTES * 60)) done_count=0
    while [ "$SECONDS" -lt "$deadline" ] && kill -0 "$runner" 2>/dev/null; do
        done_count="$(contributions_on_main 2>/dev/null || echo 0)"
        [ "$done_count" -ge "$WORKERS" ] && break
        sleep 10
    done
    kill -0 "$runner" 2>/dev/null || die "runner exited early; see $OUT/run.log"
    [ "$done_count" -ge "$WORKERS" ] || die "only $done_count/$WORKERS contributions reached main"
    log "all $WORKERS contributions are on main"
    check_live_state

    local rc=0
    if [ "$PACK" = software-project ] && [ "$INTERRUPT" != 1 ]; then
        check_lifecycle "$runner"
    elif [ "$INTERRUPT" = 1 ]; then
        # The failure path must still export, archive and verify before stopping.
        log "interrupting the runner (SIGTERM) to exercise its teardown"
        kill -TERM "$runner"
        wait "$runner" || rc=$?
        [ "$rc" != 0 ] || die "interrupted runner exited 0; expected a failure status"
        grep -q 'teardown (rc=' "$OUT/run.log" || die "runner did not run its teardown; see $OUT/run.log"
        log "runner exited $rc after teardown"
    else
        log "waiting for the runner to finish its budget, export and shutdown"
        wait "$runner" || rc=$?
        [ "$rc" = 0 ] || die "runner exited $rc; see $OUT/run.log"
    fi
    check_outputs
    log "PASS"
}

main "$@"
