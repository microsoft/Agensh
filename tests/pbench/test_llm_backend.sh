#!/usr/bin/env bash
# T: pbench LLM 后端功能性 smoke —— 真打 .env.org-pbench 里配置的后端,证明
# "对端活着 + key 能用 + agent 实际请求的模型可用",而不只是"compose 线接对了"
# (后者由 test_compose_netlock.sh 覆盖)。
#
# 一律从 .env.org-pbench 读(不写死任何后端):
#   PBENCH_LLM_UPSTREAM  egress-proxy 转发到的真实 LLM 地址
#   ANTHROPIC_API_KEY    agent 透传的 key(x-api-key)
#   ANTHROPIC_MODEL      默认 claude-opus-4.8[1m](prod 模板默认值)
#
# 是 LIVE smoke:需要网络 + 真实 key。占位值(CHANGE_ME / *.example)
# 或拿不到配置 → SKIP(退出 0),不会在脱敏快照 / CI 里误失败。
#
# Run:  bash tests/pbench/test_llm_backend.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
ENV_FILE=".env.org-pbench"

skip() { echo "SKIP: $*"; exit 0; }
fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "  ok: $*"; }

[ -f "$ENV_FILE" ] || skip "$ENV_FILE missing (no live config to probe)"
getenv() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true; }

UPSTREAM="$(getenv PBENCH_LLM_UPSTREAM)"
KEY="$(getenv ANTHROPIC_API_KEY)"
MODEL="$(getenv ANTHROPIC_MODEL)"; MODEL="${MODEL:-claude-opus-4.8[1m]}"

[ -n "$UPSTREAM" ] && [ -n "$KEY" ] || skip "PBENCH_LLM_UPSTREAM / ANTHROPIC_API_KEY not set"
case "$UPSTREAM$KEY" in
    *CHANGE_ME*|*example*) skip "config is sanitized placeholder, not a live backend" ;;
esac
BASE="${UPSTREAM%/}"
echo "  probing $BASE  model=$MODEL"

# 1. GET /v1/models → 200 + the model's base id present (strip a trailing [..] tag)
code="$(curl -sS -m 10 -o /tmp/_pb_models.json -w '%{http_code}' \
    -H "x-api-key: $KEY" "$BASE/v1/models" 2>/dev/null || echo 000)"
[ "$code" = "200" ] || fail "GET /v1/models returned HTTP $code (backend unreachable / key rejected)"
MODEL_BASE="${MODEL%%[*}"   # claude-opus-4.8[1m] -> claude-opus-4.8
python3 - "$MODEL_BASE" <<'PY' || fail "configured model not offered by backend"
import json, sys
want = sys.argv[1]
ids = [m["id"] for m in json.load(open("/tmp/_pb_models.json")).get("data", [])]
assert want in ids, f"model {want!r} not in backend list ({len(ids)} models)"
print(f"  ok: GET /v1/models 200; base model {want!r} offered")
PY

# 2. POST /v1/messages with the EXACT model agents request → 200 + non-empty text.
#    This is the real end-to-end check (incl. that a [1m]-style routing suffix
#    is accepted by the backend, not just the base id).
code="$(curl -sS -m 30 -o /tmp/_pb_msg.json -w '%{http_code}' \
    -X POST "$BASE/v1/messages" \
    -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
    -d "{\"model\":\"$MODEL\",\"max_tokens\":16,\"messages\":[{\"role\":\"user\",\"content\":\"reply with the single word: pong\"}]}" \
    2>/dev/null || echo 000)"
[ "$code" = "200" ] || fail "POST /v1/messages model=$MODEL returned HTTP $code"
python3 - <<'PY' || fail "no assistant text in /v1/messages response"
import json
d = json.load(open("/tmp/_pb_msg.json"))
text = "".join(b.get("text","") for b in d.get("content", []) if b.get("type") == "text")
assert text.strip(), f"empty assistant text; keys={list(d)}"
bs = ""
u = d.get("copilot_usage", {})
for t in u.get("token_details", []):
    if t.get("token_type") == "input":
        bs = t.get("batch_size", "")
print(f"  ok: POST /v1/messages 200; assistant replied {text.strip()[:40]!r}" + (f" (batch_size={bs})" if bs else ""))
PY

echo "PASS: tests/pbench/test_llm_backend.sh"
