#!/usr/bin/env bash
# pbench_gen_env_sweep.sh — mint 20 single-task method-2a profiles for sweep_6.2.
#
# Sweep 6.2 differs from 6/6.1 in two ways:
#
#   1. FULL PARALLELISM. 6 and 6.1 ran 7 chains of ~3 tasks; 6.2 runs all 20
#      tasks at once, one profile each. So each profile is pinned to exactly
#      one task and carries that task's identity in its env.
#
#   2. PER-TASK AGENT IMAGE. Every profile sets AGENT_IMAGE to the image built
#      FROM that task's own ProgramBench cleanroom (Dockerfile.pertask), so the
#      agent's toolchain and crate versions are the grader's by construction.
#      Sweeps through 6.1 used the union image v48-cleanroom, whose clap 4.6.4 /
#      serde 1.0.229 could not be resolved by graders pinned to 4.6.1 / 1.0.228 —
#      pueue, ast-grep and typst each scored 0.00% on that skew alone.
#
# Profile names are org-pbench-method-2a-s62<letter> so the Makefile's
# `org-pbench-method-2a-%` rule layers 1team + 1team-board (the "2a" stack:
# 6 agents + one shared context board).
#
# Port block: 14800-14990, clear of 13300 (sweep_2), 14300-14342 (sweep_5),
# 14400-14460 (sweep_6) and 14600-14660 (sweep_6.1). Two ports per profile
# (gitea, mattermost) at a stride of 10.
set -euo pipefail
# Sweep-scoped knobs so a later round does not need a near-duplicate script.
SLUG_BASE="${SLUG_BASE:-s62}"      # profile infix -> org-pbench-method-2a-<SLUG_BASE><letter>
PORT_BASE="${PORT_BASE:-14800}"    # gitea port; mattermost = +2; stride 10
NET_OCTET="${NET_OCTET:-176}"      # 10.<NET_OCTET>.<3i..3i+2>.0/24 per profile
IMAGE_TAG="${IMAGE_TAG:-pertask}"  # agent image tag; 6.9 uses pertask-claude
LETTERS="${LETTERS:-}"             # subset of chains, e.g. "a b c d"; empty = all 20
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="$ROOT/.env.org-pbench-method-2a"
[ -f "$BASE" ] || { echo "FATAL: $BASE missing" >&2; exit 1; }

# letter:task — operator order preserved from the brief.
TASKS=(
  "a:ffmpeg__ffmpeg.360a402"
  "b:universal-ctags__ctags.243595e"
  "c:typst__typst.88356d0"
  "d:php__php-src.c891263"
  "e:gromacs__gromacs.665ea4c"
  "f:jgm__pandoc.5caad90"
  "g:bellard__quickjs.d7ae12a"
  "h:danmar__cppcheck.0a5b103"
  "i:osgeo__gdal.0847f12"
  "j:duckdb__duckdb.bdb65ec"
  "k:nukesor__pueue.8b9d6fe"
  "l:samtools__samtools.aa823b5"
  "m:tstack__lnav.ee34494"
  "n:ast-grep__ast-grep.dde0fe0"
  "o:alecthomas__chroma.8d04def"
  "p:johnkerl__miller.8d85b46"
  "q:stathissideris__ditaa.f2286c4"
  "r:tinycc__tinycc.9b8765d"
  "s:zk-org__zk.10d93d5"
  "t:osgeo__proj.75d455c"
)

# Image name is derived from the REPO, not the org: osgeo__gdal and osgeo__proj
# both reduce to "osgeo" otherwise. Must match pbench_build_pertask_images.sh.
short() { t="${1#*__}"; echo "${t%%.*}" | tr -cd 'a-z0-9-'; }

i=0
for entry in "${TASKS[@]}"; do
    if [ -n "$LETTERS" ]; then _k=0; for w in $LETTERS; do [ "${entry%%:*}" = "$w" ] && _k=1; done; [ "$_k" = 1 ] || { i=$((i+1)); continue; }; fi
    L="${entry%%:*}"; task="${entry#*:}"
    http=$((PORT_BASE + i*10)); mm=$((http + 2))
    idx=$i                      # 0-based; used for the subnet triple below
    i=$((i+1))
    slug="${SLUG_BASE}$L"
    profile="org-pbench-method-2a-$slug"
    image="omcgitea-agent-$(short "$task"):$IMAGE_TAG"
    out="$ROOT/.env.$profile"

    sudo docker image inspect "$image" >/dev/null 2>&1 \
        || { echo "FATAL: $image missing (run scripts/pbench_build_pertask_images.sh)" >&2; exit 1; }

    cp "$BASE" "$out"
    # Three pinned /24s per profile. Docker's built-in address pool holds only
    # 31 subnets and each stack needs three, so 20 concurrent stacks cannot be
    # auto-allocated — and the daemon-side fix does not survive Ansible's
    # 30-minute reconciliation on this host. See docker-compose.pbench.yml.
    sub_default="10.$NET_OCTET.$((idx*3)).0/24"
    sub_egress="10.$NET_OCTET.$((idx*3+1)).0/24"
    sub_edge="10.$NET_OCTET.$((idx*3+2)).0/24"
    python3 - "$out" "$profile" "$http" "$mm" "$slug" "$image" "$task" \
             "$sub_default" "$sub_egress" "$sub_edge" "$ROOT" <<'PY'
import sys, re
(path, profile, http, mm, slug, image, task,
 sub_default, sub_egress, sub_edge, root) = sys.argv[1:12]
s = open(path).read()
def setv(s, k, v):
    if re.search(rf'(?m)^{k}=.*$', s):
        return re.sub(rf'(?m)^{k}=.*$', f'{k}={v}', s)
    return s + f'\n{k}={v}\n'
s = setv(s, 'PROFILE', profile)
s = setv(s, 'EDGE_HTTP_PORT', http)
s = setv(s, 'EDGE_MM_PORT', mm)
s = setv(s, 'MATTERMOST_SITE_URL', f'http://localhost:{mm}')
# Container state lands under THIS checkout, not a hard-coded one — otherwise two
# trees on the same host share one data dir and fight over each profile's state.
s = setv(s, 'DATA_ROOT', f'{root}/.claude-team-data-{slug}')
# Read by docker compose interpolation for x-hermes-agent's image:.
s = setv(s, 'AGENT_IMAGE', image)
# Pinned per-stack networks (see docker-compose.pbench.yml).
s = setv(s, 'PBENCH_SUBNET_DEFAULT', sub_default)
s = setv(s, 'PBENCH_SUBNET_EGRESS', sub_egress)
s = setv(s, 'PBENCH_SUBNET_EDGE', sub_edge)
# Recorded for provenance only — the runner takes TASK from its own env.
s = setv(s, 'PBENCH_TASK', task)
open(path, 'w').write(s)
PY
    echo "  .env.$profile  http=$http mm=$mm  net=10.$NET_OCTET.$((idx*3)).0-$((idx*3+2))  image=$image"
done
echo "minted ${#TASKS[@]} profiles"
