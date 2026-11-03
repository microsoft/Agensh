#!/usr/bin/env bash
# A short team run with a real model on a tiny local project, to see how agents use
# the software-project pack end to end: claims, PRs through CI, delivery and
# acceptance. Run it inside tests/smoke/run_isolated.sh, which keeps the host's
# Docker daemon untouched:
#   install -m 600 ~/.agensh/upstream.env DATA_DIR/tmp/upstream.env
#   bash tests/smoke/run_isolated.sh DATA_DIR bash tests/live/run_live.sh
# Model credentials come from /tmp/upstream.env (LLM_UPSTREAM, LLM_UPSTREAM_TOKEN),
# which the script deletes once read. Settings: LIVE_WORKERS (2), LIVE_HOURS (0.5),
# LIVE_HARNESS (copilot), LIVE_MAX_TOKENS (5000000). Not part of CI: it spends tokens.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
WORKERS="${LIVE_WORKERS:-2}"
HOURS="${LIVE_HOURS:-0.5}"
HARNESS="${LIVE_HARNESS:-copilot}"
MAX_TOKENS="${LIVE_MAX_TOKENS:-5000000}"
OUT="$ROOT/out/live"
PROJECT_FILE="$OUT/project/.agensh/project.toml"
UPSTREAM="$OUT/upstream.git"
PROFILE=software-project-live-widget
IMAGE_ORG=agensh-smoke
DOCKER=(sudo -n docker)

log() { echo "[live $(date -u +%H:%M:%S)] $*" >&2; }

[ -s /tmp/upstream.env ] || { log "put the model gateway in /tmp/upstream.env first"; exit 2; }
set -a
# shellcheck disable=SC1091
. /tmp/upstream.env
set +a
rm -f /tmp/upstream.env

make_project() {
    # A small CLI with tests; the goal needs a feature, tests and documentation.
    local work="$OUT/upstream-work"
    sudo -n rm -rf "$OUT"
    mkdir -p "$work/widget" "$work/tests" "$(dirname "$PROJECT_FILE")"
    cat > "$work/widget/__init__.py" <<'EOF'
ITEMS = [
    {"name": "bolt", "size": 3, "price": 0.25},
    {"name": "gear", "size": 12, "price": 4.5},
    {"name": "spring", "size": 5, "price": 1.1},
]
EOF
    cat > "$work/widget/__main__.py" <<'EOF'
import sys

from widget import ITEMS


def table(items):
    lines = [f"{'name':<8} {'size':>4} {'price':>6}"]
    lines += [f"{i['name']:<8} {i['size']:>4} {i['price']:>6.2f}" for i in items]
    return "\n".join(lines)


def main(argv):
    if argv[:1] != ["list"]:
        print("usage: python3 -m widget list", file=sys.stderr)
        return 2
    print(table(ITEMS))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
EOF
    cat > "$work/tests/test_cli.py" <<'EOF'
import subprocess
import sys
import unittest


class ListTest(unittest.TestCase):
    def test_table(self):
        out = subprocess.run([sys.executable, "-m", "widget", "list"], capture_output=True, text=True, check=True)
        self.assertIn("gear", out.stdout)
EOF
    printf '# widget\n\n`python3 -m widget list` prints the parts table.\n' > "$work/README.md"
    git init -q --initial-branch=main "$work"
    git -C "$work" add . && git -C "$work" -c user.name=Live -c user.email=live@localhost commit -qm "Start widget"
    git clone -q --bare "$work" "$UPSTREAM"
    rm -rf "$work"
    cat > "$PROJECT_FILE" <<EOF
pack = "software-project"
name = "live-widget"
goal = """
Add two options to \`python3 -m widget list\`:
1. \`--json\` prints the items as a JSON array of objects with the same fields.
2. \`--sort FIELD\` sorts by name, size or price (ascending) for both outputs, and
   exits with status 2 and a message for any other field.
Cover both with unit tests and document them in the README.
"""
[upstream]
repo = "$UPSTREAM"
[acceptance]
pr = ["python3 -m unittest discover -s tests -q"]
[team]
workers = $WORKERS
[budget]
hours = $HOURS
max_model_tokens = $MAX_TOKENS
[environment]
base_image = "python:3.12-slim-bookworm"
EOF
}

images() {
    log "building images (the smoke test's cache is reused)"
    "${DOCKER[@]}" build -q -f agent/Dockerfile.base -t "$IMAGE_ORG/agent-base:local" agent/ >/dev/null
    "${DOCKER[@]}" build -q -t "$IMAGE_ORG/mini-router:local" mini-router/ >/dev/null
    "${DOCKER[@]}" build -q -t "$IMAGE_ORG/board:local" board-service/ >/dev/null
    live_env python3 -m agensh.project build "$PROJECT_FILE" --agent-harness "$HARNESS" > "$OUT/build.log" 2>&1 \
        || { log "worker image build failed; see $OUT/build.log"; exit 1; }
}

live_env() {
    env AGENT_IMAGE_TAG=live AGENT_BASE_IMAGE="$IMAGE_ORG/agent-base:local" \
        MINI_ROUTER_IMAGE="$IMAGE_ORG/mini-router:local" BOARD_IMAGE="$IMAGE_ORG/board:local" \
        BOOTSTRAP_IMAGE="$IMAGE_ORG/bootstrap:local" SECRET_SERVICE_IMAGE="$IMAGE_ORG/secret-service:local" \
        DOCKER="sudo -n docker" OUT_DIR="$OUT/run" RUN_ID=live "$@"
}

report() {
    # What the team delivered and how; the stack is down, its data is kept until clean.
    local task="$OUT/run/live-widget" data
    data="$(grep -E '^DATA_ROOT=' ".env.$PROFILE" | cut -d= -f2-)/$PROFILE"
    log "report"
    python3 - "$task" "$UPSTREAM" "$data" <<'REPORT'
import json, subprocess, sys
from pathlib import Path
task, upstream, data = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
load = lambda name: json.loads((task / name).read_text()) if (task / name).is_file() else None
delivery, acceptance, health, state = load('delivery.json'), load('acceptance.json'), load('main-health.json'), load('run_state.json')
print('run state:', json.dumps(state))
print('delivery:', json.dumps(delivery))
print('acceptance:', json.dumps(acceptance))
print('main health:', json.dumps(health))
if delivery and delivery.get('branch'):
    log = subprocess.run(['git', '-C', upstream, 'log', '--format=%h %an: %s', f'{delivery["base_sha"]}..{delivery["branch"]}'],
                         capture_output=True, text=True).stdout
    print('delivered commits:\n' + log)
    print(subprocess.run(['git', '-C', upstream, 'diff', '--stat', f'{delivery["base_sha"]}..{delivery["branch"]}'],
                         capture_output=True, text=True).stdout)
usage = subprocess.run(['sudo', '-n', 'cat', str(data / 'usage/usage.jsonl')], capture_output=True, text=True).stdout
totals = {}
for line in usage.splitlines():
    record = json.loads(line)
    agent = totals.setdefault(record['agent'], {'requests': 0, 'input': 0, 'output': 0})
    agent['requests'] += 1
    agent['input'] += (record.get('usage') or {}).get('input_tokens', 0)
    agent['output'] += (record.get('usage') or {}).get('output_tokens', 0)
print('usage:', json.dumps(totals))
lifecycle = subprocess.run(['sudo', '-n', 'sh', '-c', f'cat {data}/board-lifecycle/*.jsonl'], capture_output=True, text=True).stdout
kinds = {}
for line in lifecycle.splitlines():
    try:
        kind = json.loads(line).get('type')
    except ValueError:
        continue
    kinds[kind] = kinds.get(kind, 0) + 1
print('board entries:', json.dumps(kinds))
REPORT
}

make_project
images
live_env python3 -m agensh.project profile "$PROJECT_FILE" --agent-harness "$HARNESS" >/dev/null
log "running $WORKERS $HARNESS workers for ${HOURS}h (log: $OUT/run.log)"
rc=0
live_env HOURS="$HOURS" python3 -m agensh.project run "$PROJECT_FILE" > "$OUT/run.log" 2>&1 || rc=$?
log "runner exited $rc"
report || true
if [ "${LIVE_KEEP:-0}" != 1 ]; then
    make -s clean PROFILE="$PROFILE" >/dev/null 2>&1 || true
fi
exit "$rc"
