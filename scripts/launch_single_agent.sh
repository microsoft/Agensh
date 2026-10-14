#!/usr/bin/env bash
# Single-agent ProgramBench baseline: one Copilot CLI agent (BYOK, native ACP)
# on one task, with the team runs' anti-cheat and no forge or chat.
#
#   1. Seed a per-task workspace from the task's cleanroom image and pull the
#      0111 root:root reference binary out of it.
#   2. Build a per-task agent image FROM the cleanroom that adds node and
#      @github/copilot@1.0.70 (docker/single-agent/Dockerfile), on the
#      host, before the network is locked.
#   3. Bring up an internal-only network and the strip-metadata egress-proxy
#      (docker/docker-compose.pbench-single-agent.yml).
#   4. Drive one ACP session for HOURS through scripts/acp_driver.py; the ACP
#      child is /opt/copilot-cli/node_modules/.bin/copilot --acp --stdio
#      --no-auto-login --no-auto-update --no-remote --disable-builtin-mcps
#      --no-ask-user.
#   5. Export submission.tar.gz, capture metrics, tear down, run programbench eval.
#
# The upstream URL, key and model come from .env.pbench-single-agent
# (PBENCH_LLM_UPSTREAM, ANTHROPIC_API_KEY, ANTHROPIC_MODEL).
#   TASK=<instance_id> HOURS=<h> scripts/launch_single_agent.sh
#   (or make pbench-single-agent TASK=<instance_id> HOURS=<h>)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TASK="${TASK:?TASK=<instance_id> required (e.g. abishekvashok__cmatrix.5c082c6)}"
HOURS="${HOURS:-6}"
# Absolute: compose bind-mounts paths under it and eval runs from PB_REPO, so a
# relative OUT_DIR (taken from the repo root) would resolve elsewhere.
OUT_DIR="$(realpath -m "${OUT_DIR:-$ROOT/out/pbench-single-agent}")"
PROJ="${PBENCH_SINGLE_PROJECT:-omcgitea-pbench-single-agent}"
COMPOSE_FILE="${PBENCH_SINGLE_COMPOSE:-$ROOT/docker/docker-compose.pbench-single-agent.yml}"
DOCKER_ORG="${PROGRAMBENCH_DOCKER_ORG:-programbench}"
PB_REPO="${PROGRAMBENCH_REPO:-$HOME/programbench}"
# acp_driver.py installs claude-agent-acp's settings.json.tmpl (effort, deny-list)
# into ~/.claude/settings.json for every agent kind; copilot ignores it, so the
# effort also goes on Copilot's child command as --effort.
SETTINGS_TMPL="${PBENCH_ACP_SETTINGS_TMPL:-$ROOT/docker/agent/config/settings.json.tmpl}"
EFFORT="${PBENCH_ACP_EFFORT:-high}"
SINGLE_AGENT_IMAGE_REPO="${SINGLE_AGENT_IMAGE_REPO:-omcgitea-single-agent}"

# Anti-cheat parity: same non-root uid + same 0111 root:root reference-binary
# mount. docker/single-agent/Dockerfile sets up /home/ccagent for uid 10000.
ACP_CHILD_UID="${ACP_CHILD_UID:-10000}"
ACP_CHILD_GID="${ACP_CHILD_GID:-10000}"

DOCKER="${PBENCH_DOCKER:-sudo -E docker}"
export PBENCH_DOCKER="$DOCKER"

# LLM wiring: .env.pbench-single-agent carries the endpoint, key and model.
# The env file wins over the shell, so a stray ANTHROPIC_MODEL export in the
# caller's shell cannot change the model.
ENV_FILE="${PBENCH_SINGLE_ENV_FILE:-$ROOT/.env.pbench-single-agent}"
getenv() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true; }
_envf_upstream="$(getenv PBENCH_LLM_UPSTREAM)"
_envf_key="$(getenv ANTHROPIC_API_KEY)"
_envf_model="$(getenv ANTHROPIC_MODEL)"
export PBENCH_LLM_UPSTREAM="${_envf_upstream:-${PBENCH_LLM_UPSTREAM:-}}"
export ANTHROPIC_API_KEY="${_envf_key:-${ANTHROPIC_API_KEY:-}}"
export ANTHROPIC_MODEL="${_envf_model:-${ANTHROPIC_MODEL:-}}"
export ANTHROPIC_AUTH_TOKEN="$ANTHROPIC_API_KEY"
export ANTHROPIC_BASE_URL="http://egress-proxy:4180"

# Copilot BYOK provider — derived from ANTHROPIC_* by default so callers only
# have to set the one env file. `openai` is the OpenAI-compatible /v1 shape.
export COPILOT_PROVIDER_TYPE="${COPILOT_PROVIDER_TYPE:-$(getenv COPILOT_PROVIDER_TYPE)}"
export COPILOT_PROVIDER_TYPE="${COPILOT_PROVIDER_TYPE:-openai}"
export COPILOT_PROVIDER_BASE_URL="${COPILOT_PROVIDER_BASE_URL:-http://egress-proxy:4180/v1}"
export COPILOT_PROVIDER_API_KEY="${COPILOT_PROVIDER_API_KEY:-$ANTHROPIC_API_KEY}"
export COPILOT_MODEL="${COPILOT_MODEL:-$ANTHROPIC_MODEL}"
# Optional responses transport and context window, as the team profiles set them.
# gpt-5.6-sol needs both: the gateway refuses it on /v1/chat/completions (400
# unsupported_api_for_model), and Copilot's catalogue has no window for it.
# Exported only when set, so a profile without them keeps Copilot's defaults.
for v in COPILOT_PROVIDER_WIRE_API COPILOT_PROVIDER_MAX_PROMPT_TOKENS; do
    val="${!v:-$(getenv "$v")}"
    if [ -n "$val" ]; then export "$v=$val"; else unset "$v"; fi
done
unset v val
# COPILOT_AGENT_MODEL is deliberately unset (and actively cleared, so an
# operator's stale export cannot leak in): Copilot 1.0.70 validates it against
# GitHub's own catalog, rejects BYOK ids, and silently falls back to a default
# the BYOK endpoint 404s on. COPILOT_MODEL alone is what selects the model.
# See docker-compose.pbench-single-agent.yml.
unset COPILOT_AGENT_MODEL
export OPENAI_API_KEY="${OPENAI_API_KEY:-$ANTHROPIC_API_KEY}"

log() { echo "[pbench-single-agent] $*" >&2; }
die() { echo "[pbench-single-agent] FATAL: $*" >&2; exit 1; }

[ -n "$PBENCH_LLM_UPSTREAM" ] || die "PBENCH_LLM_UPSTREAM unset and not in $ENV_FILE"
[ -n "$ANTHROPIC_API_KEY" ]   || die "ANTHROPIC_API_KEY unset and not in $ENV_FILE"
[ -n "$ANTHROPIC_MODEL" ]     || die "ANTHROPIC_MODEL unset and not in $ENV_FILE"
[ -f "$SETTINGS_TMPL" ]       || die "settings.json.tmpl not at $SETTINGS_TMPL (needed for effort + deny-list)"
# Copilot exits on a level it does not know, which would kill every turn's child.
case "$EFFORT" in
    none|minimal|low|medium|high|xhigh|max) ;;
    *) die "PBENCH_ACP_EFFORT=$EFFORT is not a Copilot effort level (none|minimal|low|medium|high|xhigh|max)" ;;
esac
command -v envsubst >/dev/null 2>&1 || die "envsubst not found (apt install gettext-base); it renders the prompts under prompts/"
source "$ROOT/scripts/lib_prompts.sh"

# Per-task single-agent image, tagged with the task id.
SINGLE_AGENT_IMAGE="${SINGLE_AGENT_IMAGE:-$SINGLE_AGENT_IMAGE_REPO:$(printf '%s' "$TASK" | tr -c 'A-Za-z0-9_.-' '-')}"
export SINGLE_AGENT_IMAGE

img_base="$DOCKER_ORG/$(printf '%s' "$TASK" | sed 's/__/_1776_/')"
CLEANROOM_IMG="$img_base:task_cleanroom"

TASK_DIR="$OUT_DIR/$TASK"
SEED_DIR="$TASK_DIR/workspace"
BIN_PATH="$TASK_DIR/bin/executable"
CC_HOME="$TASK_DIR/cchome"

# Anti-leakage: refuse to start if leftover state exists. Operator must `rm -rf $TASK_DIR` before re-running.
if [ -e "$TASK_DIR" ]; then
    die "$TASK_DIR already exists — leftover state from a prior run would leak into this one. Remove it (\`rm -rf $TASK_DIR\`) before re-running."
fi
mkdir -p "$TASK_DIR"

compose() { $DOCKER compose -p "$PROJ" -f "$COMPOSE_FILE" "$@"; }

export PBENCH_SEED_DIR="$SEED_DIR"
export PBENCH_BIN="$BIN_PATH"
export PBENCH_CC_HOME="$CC_HOME"
export ACP_CHILD_UID ACP_CHILD_GID

# --- always export a submission on the way out ------------------------------
export_submission() {
    local cc_cn sub="$TASK_DIR/submission.tar.gz"
    cc_cn="$(compose ps -q cc-agent 2>/dev/null || true)"
    if [ -n "$cc_cn" ]; then
        $DOCKER exec -w /workspace "$cc_cn" sh -lc '
            git config --global --add safe.directory /workspace 2>/dev/null || true
            git rev-parse --git-dir >/dev/null 2>&1 || { git init -q; }
            git config user.email cc@pbench.local 2>/dev/null || true
            git config user.name  cc-agent        2>/dev/null || true
            git add -A 2>/dev/null || true
            git commit -qm "pbench-single-agent: final snapshot" 2>/dev/null || true' \
            >/dev/null 2>&1 || true
        if $DOCKER exec -w /workspace "$cc_cn" git archive --format=tar.gz HEAD > "$sub" 2>>"$TASK_DIR/export.log"; then
            if tar -tzf "$sub" 2>/dev/null | sed 's#^\./##' | grep -qx 'compile.sh'; then
                log "submission.tar.gz written ($(stat -c%s "$sub" 2>/dev/null) bytes)"
                return 0
            fi
            log "WARN: submission has no root compile.sh (agent may not have produced one)"
            return 0
        fi
    fi
    log "WARN: could not export from cc-agent; writing an empty submission so eval records no_submission"
    : > "$sub"
}

# --- capture cc's LLM call count -------------------------------------------
# Counted from the agent's own session log.
capture_metrics() {
    local metrics="$TASK_DIR/cc_calls.txt"
    local sess steps=0 tool_uses=0
    # Copilot writes .copilot/session-state/<id>/events.jsonl, claude-agent-acp
    # .claude/projects/*/*.jsonl. Prefer copilot, fall back to claude.
    sess="$(sudo find "$CC_HOME/.copilot/session-state" -name 'events.jsonl' 2>/dev/null | head -1 || true)"
    [ -n "$sess" ] || sess="$(sudo find "$CC_HOME/.claude/projects" -name '*.jsonl' 2>/dev/null | head -1 || true)"
    if [ -n "$sess" ]; then
        # jsonl may be uid-10000 owned; use sudo to read.
        steps="$(sudo cat "$sess" 2>/dev/null | python3 -c '
import sys,json
# Two schemas. claude-agent-acp: {"message":{"role":"assistant","id":..,
# "content":[{"type":"tool_use"}..]}}. copilot: flat events with a "type",
# where an assistant message is assistant.message and a tool call is
# tool.execution_start.
ids=set(); tu=0; amsg=0; texec=0
for l in sys.stdin:
    try: d=json.loads(l)
    except: continue
    t=d.get("type")
    if t=="assistant.message": amsg+=1
    elif t=="tool.execution_start": texec+=1
    m=d.get("message") or {}
    if m.get("role")=="assistant" and m.get("id"): ids.add(m["id"])
    c=m.get("content")
    if isinstance(c,list): tu+=sum(1 for b in c if isinstance(b,dict) and b.get("type")=="tool_use")
print(len(ids) or amsg, tu or texec)' 2>/dev/null || echo "0 0")"
        tool_uses="${steps#* }"; steps="${steps%% *}"
    fi
    local px log_out="$TASK_DIR/egress-proxy.log"
    px="$(compose ps -q egress-proxy 2>/dev/null || true)"
    [ -n "$px" ] && { $DOCKER logs "$px" > "$log_out" 2>&1 || true; }
    {
        echo "task=$TASK"
        echo "cc_steps=$steps              # assistant messages (claude: distinct message.id)"
        echo "cc_tool_uses=$tool_uses      # tool calls issued by the agent"
        echo "session_jsonl=${sess:-<none>}"
    } | tee "$metrics" | sed 's/^/[pbench-single-agent] metric: /' >&2
}

# --- per-N-min code snapshots -----------------------------------------------
# Freeze /workspace as a candidate submission every SNAPSHOT_INTERVAL_SECS
# seconds (default 20 min). Each snapshot is a `git archive HEAD` tarball —
# the exact same shape as the final submission.tar.gz — so we can replay
# progress across time (compile.sh evolution, tests passing over time, etc.)
# without waiting for the 6h budget.
#
# Runs as a background process kicked off from main() and killed by teardown().
# All work happens via `docker exec` on the same container the driver uses;
# git commits are additive and do not conflict with the driver's activity.
SNAPSHOT_INTERVAL_SECS="${SNAPSHOT_INTERVAL_SECS:-1200}"
SNAPSHOTS_DIR="$TASK_DIR/snapshots"
SNAPSHOT_PIDFILE="$TASK_DIR/.snapshot.pid"

snapshot_once() {
    local seq="$1" elapsed="$2"
    local cc_cn; cc_cn="$(compose ps -q cc-agent 2>/dev/null || true)"
    [ -n "$cc_cn" ] || { echo "[snapshot] no cc-agent container" >&2; return 1; }

    local ts; ts="$(date -u '+%Y%m%dT%H%M%SZ')"
    local snap="$SNAPSHOTS_DIR/snap-$(printf '%03d' "$seq")-${ts}-${elapsed}s.tar.gz"
    local index="$SNAPSHOTS_DIR/index.log"

    $DOCKER exec -w /workspace "$cc_cn" sh -lc '
        git config --global --add safe.directory /workspace 2>/dev/null || true
        git rev-parse --git-dir >/dev/null 2>&1 || { git init -q; }
        git config user.email cc@pbench.local 2>/dev/null || true
        git config user.name  cc-agent        2>/dev/null || true
        git add -A 2>/dev/null || true
        git commit -qm "pbench-single-agent: snapshot t+'"${elapsed}"'s" 2>/dev/null || true' \
        >/dev/null 2>&1 || true

    if $DOCKER exec -w /workspace "$cc_cn" git archive --format=tar.gz HEAD > "$snap" 2>>"$SNAPSHOTS_DIR/snap.err"; then
        local sz; sz="$(stat -c%s "$snap" 2>/dev/null || echo 0)"
        local has_cs="no"
        tar -tzf "$snap" 2>/dev/null | sed 's#^\./##' | grep -qx 'compile.sh' && has_cs="yes"
        printf 'seq=%s ts=%s elapsed=%ss size=%s has_compile_sh=%s file=%s\n' \
            "$seq" "$ts" "$elapsed" "$sz" "$has_cs" "$(basename "$snap")" >> "$index"
        log "snapshot #$seq written (t+${elapsed}s, ${sz}B, compile.sh=$has_cs)"
        return 0
    fi
    rm -f "$snap" 2>/dev/null || true
    log "WARN: snapshot #$seq failed at t+${elapsed}s"
    return 1
}

snapshot_loop() {
    mkdir -p "$SNAPSHOTS_DIR"
    local start; start="$(date +%s)"
    local seq=0
    while sleep "$SNAPSHOT_INTERVAL_SECS"; do
        seq=$((seq + 1))
        local now elapsed
        now="$(date +%s)"
        elapsed=$((now - start))
        snapshot_once "$seq" "$elapsed" || true
    done
}

start_snapshot_loop() {
    [ "$SNAPSHOT_INTERVAL_SECS" -gt 0 ] 2>/dev/null || { log "SNAPSHOT_INTERVAL_SECS=$SNAPSHOT_INTERVAL_SECS → snapshots disabled"; return 0; }
    mkdir -p "$SNAPSHOTS_DIR"
    log "starting snapshot loop (interval=${SNAPSHOT_INTERVAL_SECS}s → $SNAPSHOTS_DIR)"
    ( snapshot_loop ) &
    echo $! > "$SNAPSHOT_PIDFILE"
}

stop_snapshot_loop() {
    [ -f "$SNAPSHOT_PIDFILE" ] || return 0
    local pid; pid="$(cat "$SNAPSHOT_PIDFILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        log "snapshot loop stopped (pid=$pid)"
    fi
    rm -f "$SNAPSHOT_PIDFILE" 2>/dev/null || true
}

teardown() {
    local rc=$?
    log "teardown (rc=$rc): stopping snapshot loop + capturing metrics + exporting submission + stopping stack"
    stop_snapshot_loop || true
    capture_metrics || true
    export_submission || true
    compose down -v >/dev/null 2>&1 || true
    return 0
}

# --- 1. seed cleanroom workspace + pull the reference binary OUT --------------
seed_workspace() {
    log "seeding cleanroom workspace from $CLEANROOM_IMG"
    if ! $DOCKER image inspect "$CLEANROOM_IMG" >/dev/null 2>&1; then
        log "pulling $CLEANROOM_IMG (agent gets NO internet; this MUST happen host-side now)"
        $DOCKER pull "$CLEANROOM_IMG" >/dev/null 2>&1 \
            || die "cannot pull $CLEANROOM_IMG (check task id / dockerhub access)"
    fi
    sudo rm -rf "$SEED_DIR" "$(dirname "$BIN_PATH")" 2>/dev/null || true
    mkdir -p "$SEED_DIR" "$(dirname "$BIN_PATH")"
    PROGRAMBENCH_DOCKER_ORG="$DOCKER_ORG" \
        python3 tools/pbench_submission.py seed --image "$CLEANROOM_IMG" \
        --into "$SEED_DIR" --bin-out "$BIN_PATH" \
        || die "seed extraction failed"
    if [ -f "$BIN_PATH" ]; then
        sudo chown 0:0 "$BIN_PATH"
        sudo chmod 0111 "$BIN_PATH"
        log "reference binary staged 0111 root:root at $BIN_PATH"
    else
        log "WARN: no reference binary extracted; agent will get a /dev/null mount"
    fi
    grep -qxF 'executable' "$SEED_DIR/.gitignore" 2>/dev/null \
        || echo 'executable' >> "$SEED_DIR/.gitignore"
    sudo chown -R "$ACP_CHILD_UID:$ACP_CHILD_GID" "$SEED_DIR"
    log "seed workspace ready at $SEED_DIR (owned $ACP_CHILD_UID:$ACP_CHILD_GID, NO binary)"
    mkdir -p "$CC_HOME"
    sudo chown -R "$ACP_CHILD_UID:$ACP_CHILD_GID" "$CC_HOME"
    log "persistent cc HOME ready at $CC_HOME (mounted /home/ccagent, owned $ACP_CHILD_UID:$ACP_CHILD_GID)"
}

# --- 2. build the Copilot agent image FROM the cleanroom --------------------
# The per-task agent image build happens on the HOST (which has network) BEFORE the net-lock stack comes up. The running
# agent has ZERO public egress, so node + @github/copilot MUST be baked in now.
build_copilot_image() {
    log "building single-agent image $SINGLE_AGENT_IMAGE FROM $CLEANROOM_IMG (+ node + @github/copilot)"
    $DOCKER build --build-arg "CLEANROOM_IMG=$CLEANROOM_IMG" \
        -t "$SINGLE_AGENT_IMAGE" -f docker/single-agent/Dockerfile docker/single-agent \
        || die "single-agent image build failed"
}

# --- the prompts: ProgramBench's rules, the task brief, the resume prompt -----
pb_rules() { render_prompt "$PROMPTS_DIR/single-agent/rules.md"; }
task_brief() { render_prompt "$PROMPTS_DIR/single-agent/brief.md" TASK="$TASK" HOURS="$HOURS"; }
# Sent without a trailing newline.
resume_prompt() { printf '%s' "$(render_prompt "$PROMPTS_DIR/single-agent/resume.md")"; }

# --- 4. drive ONE ACP session ------------------------------------------------
drive_cc() {
    local cc_cn; cc_cn="$(compose ps -q cc-agent)"
    [ -n "$cc_cn" ] || die "cc-agent container not found after up"

    # Seed the workspace git repo so a zero-progress run still exports a valid
    # submission.
    $DOCKER exec -w /workspace "$cc_cn" sh -lc '
        git config --global --add safe.directory /workspace
        git config --global user.email cc@pbench.local
        git config --global user.name  cc-agent
        git init -q
        git add -A
        git commit -qm "pbench-single-agent: seed cleanroom workspace" || true' \
        || log "WARN: in-container git seed failed"

    # Stage prompt files OUTSIDE /workspace so they are not committed.
    local pdir="/home/ccagent/.pbench"
    $DOCKER exec -u 0:0 "$cc_cn" mkdir -p "$pdir" >/dev/null 2>&1 || true
    pb_rules   | $DOCKER exec -i -u 0:0 "$cc_cn" sh -c "cat > $pdir/rules.txt && chmod 0644 $pdir/rules.txt"
    task_brief | $DOCKER exec -i -u 0:0 "$cc_cn" sh -c "cat > $pdir/brief.txt && chmod 0644 $pdir/brief.txt"
    resume_prompt | $DOCKER exec -i -u 0:0 "$cc_cn" sh -c "cat > $pdir/resume.txt && chmod 0644 $pdir/resume.txt"

    log "driving ACP session for ${HOURS}h wall-clock (effort=$EFFORT, resume loop until deadline)…"
    # DEADLINE_SECS env var wins over HOURS (useful for sub-hour smoke tests
    # since HOURS is bash-integer).
    local deadline_secs="${DEADLINE_SECS:-$(( HOURS * 3600 ))}"
    log "deadline_secs=$deadline_secs"
    local acp_log="$TASK_DIR/cc.log"
    local acp_err="$TASK_DIR/acp-child.stderr.log"
    local sess_state="$TASK_DIR/session_id.txt"

    # Copilot ACP child command: the team agents' copilot command from
    # docker/agent/entrypoint.sh, minus --additional-mcp-config because
    # the single agent has no mini-router or MCP bridge.
    local child_cmd="/opt/copilot-cli/node_modules/.bin/copilot --acp --stdio --no-auto-login --no-auto-update --no-remote --disable-builtin-mcps --no-ask-user --effort $EFFORT"

    # The driver logs to stderr; tee it into cc.log. The driver's rc is read from
    # PIPESTATUS inside the `||`: as a bare pipeline, a non-zero driver would end
    # the launcher here (set -e with pipefail), before its export and eval.
    local rc=0
    PBENCH_DOCKER="$DOCKER" python3 "$ROOT/scripts/acp_driver.py" \
        --container "$cc_cn" \
        --workspace-cwd /workspace \
        --deadline-secs "$deadline_secs" \
        --brief "$pdir/brief.txt" \
        --rules "$pdir/rules.txt" \
        --resume "$pdir/resume.txt" \
        --settings-tmpl "$SETTINGS_TMPL" \
        --effort "$EFFORT" \
        --docker "$DOCKER" \
        --session-state "$sess_state" \
        --child-stderr "$acp_err" \
        --stuck-secs "${STUCK_SECS:-600}" \
        --child-cmd "$child_cmd" \
        2>&1 | tee -a "$acp_log" || rc=${PIPESTATUS[0]}
    log "acp_driver exit rc=$rc"
}

main() {
    log "TASK=$TASK HOURS=$HOURS OUT_DIR=$OUT_DIR PROJ=$PROJ COMPOSE=$COMPOSE_FILE"
    trap teardown EXIT

    seed_workspace
    build_copilot_image

    log "bringing up the single-agent stack (egress-proxy + cc-agent)"
    compose down -v --remove-orphans >/dev/null 2>&1 || true
    local up_ok=0
    for attempt in 1 2 3 4; do
        if compose up -d --remove-orphans 2>&1 | tee -a "$TASK_DIR/compose-up.log"; then
            up_ok=1; break
        fi
        log "WARN: compose up attempt $attempt failed; forcing down and retrying"
        compose down -v --remove-orphans >/dev/null 2>&1 || true
        sleep $((attempt * 10))
    done
    [ "$up_ok" -eq 1 ] || die "compose up failed after 4 attempts"

    start_snapshot_loop

    drive_cc

    log "wall-clock budget elapsed; exporting + evaluating"
    trap - EXIT
    stop_snapshot_loop
    capture_metrics
    export_submission
    compose down -v >/dev/null 2>&1 || true

    if [ -n "${PBENCH_SKIP_EVAL:-}" ]; then
        log "PBENCH_SKIP_EVAL set — skipping inline programbench eval"
        return 0
    fi
    log "running programbench eval on $OUT_DIR"
    export PROGRAMBENCH_DOCKER_EXECUTABLE="${PROGRAMBENCH_DOCKER_EXECUTABLE:-$ROOT/scripts/pbench-docker-sudo.sh}"
    local pbench_tmp="$TASK_DIR/_evaltmp"
    rm -rf "$pbench_tmp"; mkdir -p "$pbench_tmp"
    export TMPDIR="$pbench_tmp"
    if command -v uv >/dev/null 2>&1; then
        ( cd "$PB_REPO" && PROGRAMBENCH_DOCKER_EXECUTABLE="$PROGRAMBENCH_DOCKER_EXECUTABLE" TMPDIR="$pbench_tmp" \
            uv run programbench eval "$OUT_DIR" --filter "$TASK" ) \
            || log "WARN: programbench eval returned non-zero"
    elif command -v programbench >/dev/null 2>&1; then
        programbench eval "$OUT_DIR" --filter "$TASK" || log "WARN: eval non-zero"
    else
        die "neither 'uv' nor 'programbench' on PATH — cannot evaluate"
    fi

    local eval_json="$TASK_DIR/$TASK.eval.json"
    [ -f "$eval_json" ] && log "eval.json written: $eval_json" \
        || log "WARN: eval.json not found at $eval_json"
}

main "$@"
