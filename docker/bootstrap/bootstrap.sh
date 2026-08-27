#!/bin/bash
# omcgitea M1 bootstrap
#
# Idempotent. Sets up Gitea so hermes agents can collaborate via PR/review/merge.
#
# Inputs (env):
#   GITEA_HOST                http://gitea:3000
#   GITEA_ADMIN_USER          chairman
#   GITEA_ADMIN_PASSWORD      <required>
#   GITEA_ADMIN_EMAIL         chairman@local
#   AGENTS                    "agent1,agent2"           (comma-separated)
#   REPOS                     "test-sandbox"            (comma-separated, owned by admin)
#   BOOTSTRAP_DATA_DIR        /data                     (where tokens/ secrets/ live)
#   REQUIRED_APPROVALS        1                         (branch protection on main)
#
# Outputs (disk under $BOOTSTRAP_DATA_DIR/tokens/):
#   admin.token
#   agent-<name>.token        per agent
#   .bootstrap-done           marker
#
# Outputs (Gitea):
#   - chairman admin user
#   - agent-<name> users (write on each repo, in approvals_whitelist)
#   - chairman/<repo> repos (auto-init=true, default branch main)
#   - branch protection on main (required_approvals = REQUIRED_APPROVALS, approvals_whitelist=agents)
#   - any legacy hermes-agent-*:8644/webhooks/gitea repo hook is DELETED (the
#     M2-E.1 router is now the sole event source; webhook path is decommissioned).

set -euo pipefail

: "${GITEA_HOST:=http://gitea:3000}"
: "${GITEA_ADMIN_USER:=chairman}"
: "${GITEA_ADMIN_PASSWORD:?GITEA_ADMIN_PASSWORD required}"
: "${GITEA_ADMIN_EMAIL:=chairman@omcgitea.local}"
: "${GITEA_ORG:=omcgitea}"
: "${AGENTS:=agent1,agent2}"
: "${REPOS:=test-sandbox}"
: "${BOOTSTRAP_DATA_DIR:=/data}"
: "${REQUIRED_APPROVALS:=1}"
# R5 / TEAMCONFIG. Format: lead=<a>;reviewer=<a,b>;coder=<c,d,...>
# Drives org team membership only — md files do NOT contain role/roster info.
: "${ROLES:=}"

TOKENS_DIR="$BOOTSTRAP_DATA_DIR/tokens"
DONE_MARK="$TOKENS_DIR/.bootstrap-done"
ADMIN_TOKEN_FILE="$TOKENS_DIR/admin.token"

mkdir -p "$TOKENS_DIR"
chmod 700 "$TOKENS_DIR"

log() { echo "[bootstrap] $*" >&2; }

if [ -f "$DONE_MARK" ]; then
    log "Already done (mark=$DONE_MARK), exit 0"
    exit 0
fi

# ------------------------------------------------------------------
# 1. Wait for Gitea
# ------------------------------------------------------------------
log "Waiting for Gitea at $GITEA_HOST ..."
for i in $(seq 1 120); do
    if curl -fsS "$GITEA_HOST/api/v1/version" >/dev/null 2>&1; then
        log "Gitea up after ${i}s"
        break
    fi
    sleep 1
    if [ "$i" = "120" ]; then
        log "Gitea NOT up after 120s — abort"
        exit 1
    fi
done

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
api_admin() {
    # api_admin METHOD PATH [data]
    local m="$1" p="$2" d="${3:-}"
    if [ -n "$d" ]; then
        curl -fsS -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
            -H "Content-Type: application/json" \
            -X "$m" "${GITEA_HOST}${p}" -d "$d"
    else
        curl -fsS -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
            -X "$m" "${GITEA_HOST}${p}"
    fi
}

api_admin_status() {
    # api_admin_status METHOD PATH [data]  -> prints HTTP status code only
    local m="$1" p="$2" d="${3:-}"
    if [ -n "$d" ]; then
        curl -s -o /dev/null -w "%{http_code}" -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
            -H "Content-Type: application/json" \
            -X "$m" "${GITEA_HOST}${p}" -d "$d"
    else
        curl -s -o /dev/null -w "%{http_code}" -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
            -X "$m" "${GITEA_HOST}${p}"
    fi
}

# ------------------------------------------------------------------
# 2. Ensure admin user exists
#    (gitea container is started with INSTALL_LOCK=true; admin must
#    be created on first boot via gitea CLI from env GITEA_ADMIN_*.
#    If not, fall back to /api/v1/admin/users which requires existing
#    admin — chicken-and-egg. We assume gitea image bootstrap created it.)
# ------------------------------------------------------------------
admin_check_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
    "${GITEA_HOST}/api/v1/users/${GITEA_ADMIN_USER}")
if [ "$admin_check_code" != "200" ]; then
    log "Admin user '$GITEA_ADMIN_USER' check failed (HTTP $admin_check_code)."
    log "Make sure gitea container env GITEA__security__INSTALL_LOCK=true and"
    log "GITEA__service__DISABLE_REGISTRATION=true were set, AND that you"
    log "ran 'gitea admin user create' once (the gitea entrypoint does this"
    log "automatically when GITEA_ADMIN_* envs are set)."
    exit 1
fi
log "Admin user OK"

# ------------------------------------------------------------------
# 3. Create admin scoped token (idempotent: if exists with same name, reuse)
# ------------------------------------------------------------------
get_or_create_token() {
    local user="$1" pass="$2" name="$3" scopes_json="$4" out_file="$5"

    # If file already exists and the token still works, keep it.
    if [ -f "$out_file" ]; then
        local tok
        tok=$(cat "$out_file")
        local code
        code=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: token $tok" \
            "${GITEA_HOST}/api/v1/user")
        if [ "$code" = "200" ]; then
            log "Token reused for $user from $out_file"
            return 0
        fi
        log "Cached token in $out_file invalid (HTTP $code); will rotate"
    fi

    # Drop any prior token with same name
    local existing
    existing=$(curl -fsS -u "${user}:${pass}" \
        "${GITEA_HOST}/api/v1/users/${user}/tokens" | jq -c ".[] | select(.name==\"$name\") | .id" || true)
    for id in $existing; do
        log "Deleting stale token $name (id=$id) for $user"
        curl -fsS -u "${user}:${pass}" -X DELETE \
            "${GITEA_HOST}/api/v1/users/${user}/tokens/${id}" >/dev/null
    done

    local body
    body=$(jq -nc --arg n "$name" --argjson s "$scopes_json" '{name:$n, scopes:$s}')
    local resp
    resp=$(curl -fsS -u "${user}:${pass}" \
        -H "Content-Type: application/json" \
        -X POST "${GITEA_HOST}/api/v1/users/${user}/tokens" -d "$body")
    local sha1
    sha1=$(echo "$resp" | jq -r '.sha1')
    if [ -z "$sha1" ] || [ "$sha1" = "null" ]; then
        log "FAILED creating token for $user: $resp"
        exit 1
    fi
    install -m 0600 /dev/stdin "$out_file" <<<"$sha1"
    log "Token created for $user → $out_file"
}

ADMIN_SCOPES='["write:admin","write:repository","write:user","write:organization","write:issue","read:issue"]'
get_or_create_token "$GITEA_ADMIN_USER" "$GITEA_ADMIN_PASSWORD" "omcgitea-admin" "$ADMIN_SCOPES" "$ADMIN_TOKEN_FILE"
ADMIN_TOKEN=$(cat "$ADMIN_TOKEN_FILE")

api_token() {
    # api_token METHOD PATH [data]
    local m="$1" p="$2" d="${3:-}"
    if [ -n "$d" ]; then
        curl -fsS -H "Authorization: token $ADMIN_TOKEN" \
            -H "Content-Type: application/json" \
            -X "$m" "${GITEA_HOST}${p}" -d "$d"
    else
        curl -fsS -H "Authorization: token $ADMIN_TOKEN" \
            -X "$m" "${GITEA_HOST}${p}"
    fi
}

api_token_status() {
    local m="$1" p="$2" d="${3:-}"
    if [ -n "$d" ]; then
        curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: token $ADMIN_TOKEN" \
            -H "Content-Type: application/json" \
            -X "$m" "${GITEA_HOST}${p}" -d "$d"
    else
        curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: token $ADMIN_TOKEN" \
            -X "$m" "${GITEA_HOST}${p}"
    fi
}

# ------------------------------------------------------------------
# 4. Create agent users
# ------------------------------------------------------------------
IFS=',' read -r -a AGENT_LIST <<<"$AGENTS"
IFS=',' read -r -a REPO_LIST <<<"$REPOS"

# ------------------------------------------------------------------
# 4a. Parse ROLES → LEAD_LIST / REVIEWER_LIST / CODER_LIST.
# Default fallback (when ROLES unset): first agent=lead, second=reviewer, rest=coder.
# ------------------------------------------------------------------
LEAD_LIST=(); REVIEWER_LIST=(); CODER_LIST=(); DIRECTOR_LIST=()
if [ -n "$ROLES" ]; then
    IFS=';' read -r -a _BUCKETS <<<"$ROLES"
    for _b in "${_BUCKETS[@]}"; do
        _key="${_b%%=*}"
        _val="${_b#*=}"
        IFS=',' read -r -a _members <<<"$_val"
        case "$_key" in
            lead)     LEAD_LIST=("${_members[@]}") ;;
            reviewer) REVIEWER_LIST=("${_members[@]}") ;;
            coder)    CODER_LIST=("${_members[@]}") ;;
            director) DIRECTOR_LIST=("${_members[@]}") ;;
        esac
    done
fi
if [ "${#LEAD_LIST[@]}" -eq 0 ] && [ "${#REVIEWER_LIST[@]}" -eq 0 ] && [ "${#CODER_LIST[@]}" -eq 0 ]; then
    [ "${#AGENT_LIST[@]}" -ge 1 ] && LEAD_LIST=("${AGENT_LIST[0]}")
    [ "${#AGENT_LIST[@]}" -ge 2 ] && REVIEWER_LIST=("${AGENT_LIST[1]}")
    [ "${#AGENT_LIST[@]}" -ge 3 ] && CODER_LIST=("${AGENT_LIST[@]:2}")
fi
log "Roles: director=[${DIRECTOR_LIST[*]}] lead=[${LEAD_LIST[*]}] reviewer=[${REVIEWER_LIST[*]}] coder=[${CODER_LIST[*]}]"

# Build a single-line CSV per role (used for diagnostics only — R5 stops
# writing roles.env; agent introspects role via Gitea team API).
_csv() { local IFS=,; echo "$*"; }
LEAD_CSV=$(_csv "${LEAD_LIST[@]}")
REVIEWER_CSV=$(_csv "${REVIEWER_LIST[@]}")
CODER_CSV=$(_csv "${CODER_LIST[@]}")
log "Role CSVs (informational): lead=${LEAD_CSV} reviewer=${REVIEWER_CSV} coder=${CODER_CSV}"
# R5: explicitly remove any stale roles.env from earlier R4 runs.
rm -f "$TOKENS_DIR/roles.env" 2>/dev/null || true

ensure_user() {
    local name="$1"
    local password="$2"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: token $ADMIN_TOKEN" \
        "${GITEA_HOST}/api/v1/users/${name}")
    if [ "$code" != "200" ]; then
        local body
        body=$(jq -nc --arg u "$name" --arg p "$password" \
            --arg e "${name}@omcgitea.local" \
            '{username:$u, password:$p, email:$e, must_change_password:false}')
        api_token POST "/api/v1/admin/users" "$body" >/dev/null
        log "User $name created"
    else
        log "User $name exists"
    fi
    # R3 fix (B1/B2/B5): set max_repo_creation=0 so agents cannot create
    # repos at runtime, even though their token now carries write:repository
    # (needed for push/merge/review). max_repo_creation is the orthogonal
    # Gitea control that doesn't bleed into PR auth. Verified against
    # Gitea 1.22.6: hits CreateRepository's MaxCreationLimit check before
    # any repo row is touched. Idempotent — PATCH each boot.
    local pbody
    pbody=$(jq -nc --arg n "$name" '{source_id:0, login_name:$n, max_repo_creation:0}')
    api_token PATCH "/api/v1/admin/users/${name}" "$pbody" >/dev/null
    log "User $name max_repo_creation=0 enforced"
}

PASSWORDS_DIR="$TOKENS_DIR"

for agent in "${AGENT_LIST[@]}"; do
    pwfile="$PASSWORDS_DIR/agent-${agent}.password"
    if [ ! -f "$pwfile" ]; then
        openssl rand -hex 16 > "$pwfile"
        chmod 600 "$pwfile"
    fi
    pw=$(cat "$pwfile")
    ensure_user "$agent" "$pw"
    # read:notification is needed by omcgitea-router to do per-user
    # notification pulls (DESIGN §6.C).
    # R3 fix (B1/B2/B5): write:repository is REQUIRED for push, merge,
    # and create-review. Removing it broke merge entirely and pushed
    # agents to discover password-basic-auth back-channels (security
    # incident — see R3 deep test report). Repo-creation prevention is
    # handled at user-level by max_repo_creation=0 in ensure_user().
    AGENT_SCOPES='["read:repository","write:repository","write:issue","write:user","read:notification"]'
    get_or_create_token "$agent" "$pw" "omcgitea-agent" "$AGENT_SCOPES" "$TOKENS_DIR/agent-${agent}.token"
done

# Purge legacy webhook secrets — the M2-E.1 router replaces the webhook path.
# Safe on fresh data dirs (glob with no matches just no-ops).
rm -f "$TOKENS_DIR"/webhook-*.secret 2>/dev/null || true

# ------------------------------------------------------------------
# 4b. R5 — ensure org `omcgitea` + leads/reviewers/coders teams + members.
# ------------------------------------------------------------------
ensure_org() {
    local code
    code=$(api_token_status GET "/api/v1/orgs/${GITEA_ORG}")
    if [ "$code" = "200" ]; then
        log "Org ${GITEA_ORG} exists"
        return 0
    fi
    local body
    body=$(jq -nc --arg n "$GITEA_ORG" \
        '{username:$n, full_name:"omcgitea", visibility:"public", repo_admin_change_team_access:true}')
    api_token POST "/api/v1/orgs" "$body" >/dev/null
    log "Org ${GITEA_ORG} created"
}

team_id_of() {
    local name="$1"
    api_token GET "/api/v1/orgs/${GITEA_ORG}/teams/search?q=${name}" \
        | jq -r ".data[]? | select(.name==\"${name}\") | .id" | head -n1
}

ensure_team() {
    local name="$1" permission="$2"
    local id
    id=$(team_id_of "$name" || true)
    local body
    body=$(jq -nc --arg n "$name" --arg p "$permission" '{
        name:$n, permission:$p, can_create_org_repo:false, includes_all_repositories:true,
        units:["repo.code","repo.issues","repo.pulls","repo.releases","repo.wiki","repo.ext_wiki","repo.ext_issues","repo.projects"],
        units_map:{"repo.code":$p,"repo.issues":$p,"repo.pulls":$p,"repo.releases":$p,"repo.wiki":$p,"repo.ext_wiki":$p,"repo.ext_issues":$p,"repo.projects":$p}
    }')
    if [ -n "$id" ]; then
        api_token PATCH "/api/v1/teams/${id}" "$body" >/dev/null
        log "Team ${name} updated (id=$id, permission=$permission)"
    else
        api_token POST "/api/v1/orgs/${GITEA_ORG}/teams" "$body" >/dev/null
        log "Team ${name} created (permission=$permission)"
    fi
}

ensure_team_member() {
    local team_name="$1" user="$2"
    local id
    id=$(team_id_of "$team_name" || true)
    if [ -z "$id" ]; then
        log "ERROR: team $team_name not found"; return 1
    fi
    local code
    code=$(api_token_status PUT "/api/v1/teams/${id}/members/${user}")
    log "Team ${team_name} += ${user} (HTTP $code)"
}

ensure_team_membership_strict() {
    # Make sure each role team contains exactly the configured set —
    # remove members not in ROLES so role changes propagate cleanly.
    local team_name="$1"; shift
    local want=("$@")
    local id
    id=$(team_id_of "$team_name" || true)
    [ -z "$id" ] && { log "ERROR: team $team_name missing"; return 1; }
    local current
    current=$(api_token GET "/api/v1/teams/${id}/members" | jq -r '.[].login' || true)
    for u in $current; do
        local keep="no"
        for w in "${want[@]}"; do [ "$w" = "$u" ] && keep="yes"; done
        if [ "$keep" = "no" ]; then
            api_token DELETE "/api/v1/teams/${id}/members/${u}" >/dev/null || true
            log "Team ${team_name} -= ${u}"
        fi
    done
    for w in "${want[@]}"; do
        ensure_team_member "$team_name" "$w" || true
    done
}

ensure_org
ensure_team "leads" "admin"
ensure_team "reviewers" "write"
ensure_team "coders" "write"
ensure_team "directors" "admin"
ensure_team_membership_strict "leads"     "${LEAD_LIST[@]}"
ensure_team_membership_strict "reviewers" "${REVIEWER_LIST[@]}"
ensure_team_membership_strict "coders"    "${CODER_LIST[@]}"
ensure_team_membership_strict "directors" "${DIRECTOR_LIST[@]}"

# ------------------------------------------------------------------
# 5. Create repos under the omcgitea org. Team `leads/reviewers/coders`
# already cover all member access (includes_all_repositories=true).
# ------------------------------------------------------------------
ensure_repo() {
    local repo="$1"
    local code
    code=$(api_token_status GET "/api/v1/repos/${GITEA_ORG}/${repo}")
    if [ "$code" = "200" ]; then
        log "Repo ${GITEA_ORG}/${repo} exists"
        return 0
    fi
    # Optional one-time migration: if a legacy chairman/<repo> exists,
    # transfer it into the org. Otherwise create fresh.
    local legacy_code
    legacy_code=$(api_token_status GET "/api/v1/repos/${GITEA_ADMIN_USER}/${repo}")
    if [ "$legacy_code" = "200" ]; then
        local tbody
        tbody=$(jq -nc --arg n "$GITEA_ORG" '{new_owner:$n}')
        api_token POST "/api/v1/repos/${GITEA_ADMIN_USER}/${repo}/transfer" "$tbody" >/dev/null
        log "Repo transferred ${GITEA_ADMIN_USER}/${repo} → ${GITEA_ORG}/${repo}"
        return 0
    fi
    local body
    body=$(jq -nc --arg n "$repo" \
        '{name:$n, private:false, auto_init:true, default_branch:"main", description:"omcgitea test sandbox — written to by e2e tests"}')
    api_token POST "/api/v1/orgs/${GITEA_ORG}/repos" "$body" >/dev/null
    log "Repo ${GITEA_ORG}/${repo} created"
}

ensure_branch_protection() {
    local repo="$1"
    # R5: branch protection uses team whitelists, not user lists.
    # R7+: require_code_owner_review=true so changes touching paths in
    # CODEOWNERS (e.g. .team/*) require the listed owner's approval.
    #
    # R6.5 — REQUIRED_APPROVALS=0 selects the test-gate topology: there is no
    # review stage, so CI is the only gate. Every OTHER review-derived blocker
    # has to come off with it, or a merge stalls forever waiting on a review
    # that no agent is ever going to perform:
    #   block_on_official_review_requests — a stray request_review blocks merge
    #   require_code_owner_review         — CODEOWNERS approval nobody will give
    #   block_on_rejected_reviews         — a stale REJECT can never be cleared
    # block_on_outdated_branch stays ON in both modes: stale branches silently
    # merged over each other in sweep 6.3 and corrupted shared files.
    local rev_blockers=true
    if [ "$REQUIRED_APPROVALS" = "0" ]; then rev_blockers=false; fi
    # The lead publishes tests/ straight to main (it is the spec, and gating it
    # on itself is circular), so it needs push rights alongside the admin.
    local lead_user="${PBENCH_LEAD_USER:-}"
    # Required status checks. lead-tests is opt-in via PBENCH_REQUIRE_LEAD_TESTS
    # because a REQUIRED context whose job never runs sits at "pending" forever,
    # and pending blocks merge — i.e. a misconfigured runner would deadlock all
    # PRs in the sweep rather than fail loudly. Prove it green on one task first.
    local checks='["closes-issue-check / check (pull_request)"]'
    if [ "${PBENCH_REQUIRE_LEAD_TESTS:-0}" = "1" ]; then
        checks='["closes-issue-check / check (pull_request)","lead-tests / test (pull_request)"]'
    fi
    local body
    body=$(jq -nc --arg b "main" \
        --arg admin "$GITEA_ADMIN_USER" \
        --arg lead "$lead_user" \
        --argjson revb "$rev_blockers" \
        --argjson checks "$checks" \
        --argjson appr "$REQUIRED_APPROVALS" \
        '{branch_name:$b,
          enable_push:true,
          enable_push_whitelist:true,
          push_whitelist_usernames:(if $lead == "" then [$admin] else [$admin,$lead] end),
          push_whitelist_teams:[],
          push_whitelist_deploy_keys:false,
          required_approvals:$appr,
          enable_approvals_whitelist:true,
          approvals_whitelist_username:[],
          approvals_whitelist_teams:["reviewers"],
          enable_merge_whitelist:true,
          merge_whitelist_usernames:[],
          merge_whitelist_teams:["directors","leads","reviewers","coders"],
          dismiss_stale_approvals:$revb,
          block_on_rejected_reviews:$revb,
          block_on_official_review_requests:$revb,
          block_on_outdated_branch:true,
          require_code_owner_review:$revb,
          enable_status_check:true,
          status_check_contexts:$checks}')
    local code
    code=$(api_token_status GET "/api/v1/repos/${GITEA_ORG}/${repo}/branch_protections/main")
    if [ "$code" = "200" ]; then
        api_token PATCH "/api/v1/repos/${GITEA_ORG}/${repo}/branch_protections/main" "$body" >/dev/null
        log "Branch protection updated on ${GITEA_ORG}/${repo}/main"
    else
        api_token POST "/api/v1/repos/${GITEA_ORG}/${repo}/branch_protections" "$body" >/dev/null
        log "Branch protection created on ${GITEA_ORG}/${repo}/main"
    fi
}

ensure_codeowners() {
    # R7+: write .gitea/CODEOWNERS so changes to .team/* require chairman.
    # Branch protection has require_code_owner_review=true; CODEOWNERS only
    # listing .team/ means normal PRs are NOT gated by chairman, only the
    # team-charter file is.
    local repo="$1"
    local path=".gitea/CODEOWNERS"
    local cur_sha
    cur_sha=$(api_token GET "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" 2>/dev/null \
        | jq -r '.sha // empty' || true)
    local content
    content=$(printf '.team/  @%s\n' "$GITEA_ADMIN_USER")
    local content_b64
    content_b64=$(echo -n "$content" | base64 -w0)
    local body
    if [ -n "$cur_sha" ]; then
        body=$(jq -nc --arg c "$content_b64" --arg s "$cur_sha" --arg m "bootstrap: ensure CODEOWNERS for .team/" \
            '{message:$m, content:$c, sha:$s, branch:"main"}')
        api_token PUT "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" "$body" >/dev/null
        log "CODEOWNERS updated on ${GITEA_ORG}/${repo}"
    else
        body=$(jq -nc --arg c "$content_b64" --arg m "bootstrap: add CODEOWNERS for .team/" \
            '{message:$m, content:$c, branch:"main"}')
        api_token POST "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" "$body" >/dev/null
        log "CODEOWNERS created on ${GITEA_ORG}/${repo}"
    fi
}

ensure_closes_workflow() {
    local repo="$1"
    local path=".gitea/workflows/closes-check.yml"
    local cur_sha
    cur_sha=$(api_token GET "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" 2>/dev/null \
        | jq -r '.sha // empty' || true)
    local content_b64
    content_b64=$(base64 -w0 <<'YML'
name: closes-issue-check
on:
  pull_request:
    types: [opened, edited, synchronize, reopened]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
        - name: ensure PR body links its sub-issue
          env:
            BODY: ${{ github.event.pull_request.body }}
          # Accept Refs as well as Closes. Workers open one PR per behaviour,
          # not per assignment, so most PRs are a partial slice of their
          # sub-issue -- requiring "Closes" on every one made gitea close the
          # issue on the FIRST slice, and the lead reads a closed sub-issue as
          # "this worker is free" and hands out the next area. Refs links
          # without closing; Closes goes on the slice that finishes the goal.
          run: |
            echo "$BODY" | grep -Eqi '(closes|refs)[[:space:]]+#[0-9]+' \
              || { echo "PR body needs 'Closes #<n>' (finishes the sub-issue) or 'Refs #<n>' (partial slice)"; exit 1; }
YML
)
    local body
    if [ -n "$cur_sha" ]; then
        body=$(jq -nc --arg c "$content_b64" --arg s "$cur_sha" --arg m "bootstrap: ensure closes-issue-check workflow" \
            '{message:$m, content:$c, sha:$s, branch:"main"}')
        api_token PUT "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" "$body" >/dev/null
        log "closes-check.yml updated on ${GITEA_ORG}/${repo}"
    else
        body=$(jq -nc --arg c "$content_b64" --arg m "bootstrap: add closes-issue-check workflow" \
            '{message:$m, content:$c, branch:"main"}')
        api_token POST "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" "$body" >/dev/null
        log "closes-check.yml created on ${GITEA_ORG}/${repo}"
    fi
}

# R6.5 — the test gate. The lead authors tests/ from observing the reference
# binary; this job re-runs that suite on every PR so "done" is decided by
# executing the code, not by a human reading a diff.
#
# Why a bare `git clone` and no `uses:` action: DEFAULT_ACTIONS_URL is "github",
# which the sealed stack cannot reach, so actions/checkout can never run here.
# The clone works because act_runner is now pinned to the stack network
# (ACT_JOB_NETWORK), so gitea:3000 resolves from inside the job.
#
# An empty or absent suite yields 0 passes on both sides, so 0 >= 0 passes and
# the gate is a no-op until the lead publishes cases. That is deliberate: the
# gate must never be the reason nothing can merge.
# The lead's suite lives on its own `tests` branch, never on main.
#
# Under block_on_outdated_branch every commit to main invalidates every open PR,
# and the lead authored 56% (s68a) to 81% (s68c) of all commits to main -- all of
# them tests/, which cannot break a worker's build. Measured median gap between
# main commits was 42s (s68a) / 87s (s68c), shorter than a CI run, so no branch
# could stay mergeable: s68c lost 5 PRs at 18-157 commits behind and its slowest
# worker merged 1 PR in twelve hours. Moving the suite off main makes "main
# moved" mean "a worker merged src/", which is exactly when a re-sync IS needed.
# Projected effect: s68c 272 -> ~49 commits on main, median gap 87s -> ~8min.
#
# Left UNPROTECTED on purpose: the lead pushes here constantly, and a protected
# branch that the lead cannot push to would silence the whole suite. The tests/
# vs src/ boundary held with zero violations across all six 6.8 stacks, so it
# does not need enforcing here.
ensure_tests_branch() {
    local repo="$1" code
    code=$(api_token_status GET "/api/v1/repos/${GITEA_ORG}/${repo}/branches/tests")
    if [ "$code" = "200" ]; then
        log "tests branch already present on ${GITEA_ORG}/${repo}"
        return 0
    fi
    local body
    body=$(jq -nc '{new_branch_name:"tests", old_branch_name:"main"}')
    if api_token POST "/api/v1/repos/${GITEA_ORG}/${repo}/branches" "$body" >/dev/null 2>&1; then
        log "tests branch created on ${GITEA_ORG}/${repo}"
    else
        log "WARN: could not create tests branch on ${GITEA_ORG}/${repo}"
    fi
}

ensure_ci_list() {
    # Seed src/ci-list.txt at repo init so the range exists before anything lands. A worker
    # appends its <goal> in the PR that lands it, and lead-tests runs the cases under
    # tests/cases/<goal>/ for every goal listed. Empty is valid: the gate degrades to pure
    # regression checking, which is the whole verdict anyway.
    local repo="$1" path="src/ci-list.txt"
    api_token GET "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" 2>/dev/null \
        | jq -e '.sha' >/dev/null 2>&1 && return 0
    local body
    body=$(jq -nc --arg c "$(printf '# one goal per line; a worker appends its own when it lands the goal.\n' | base64 -w0)" \
        --arg m "bootstrap: seed src/ci-list.txt (CI range)" \
        '{message:$m, content:$c, branch:"main"}')
    api_token POST "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" "$body" >/dev/null
    log "src/ci-list.txt seeded on ${GITEA_ORG}/${repo}"
}

ensure_lead_tests_workflow() {
    local repo="$1"
    local path=".gitea/workflows/lead-tests.yml"
    local cur_sha
    cur_sha=$(api_token GET "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" 2>/dev/null \
        | jq -r '.sha // empty' || true)
    local content_b64
    content_b64=$(base64 -w0 <<'YML'
name: lead-tests
on:
  pull_request:
    types: [opened, synchronize, reopened]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: no-regression check against the lead's suite
        env:
          REPO_URL: ${{ github.server_url }}/${{ github.repository }}
          API_BASE: ${{ github.server_url }}/api/v1/repos/${{ github.repository }}
          GT: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
        shell: bash
        run: |
          set +e
          # The verdict is posted to the PR from THIS step, not a second one: act_runner
          # planned only workflow/0.sh and silently dropped a second step -- no error, no
          # `evaluating expression 'always()'` line -- so all four CI runs in the 0.5h smoke
          # produced a verdict nobody could receive. A subshell keeps the body's `exit N`
          # from ending the job before the post runs.
          (
          set -e
          # Every test in this project belongs to the lead. CI does not
          # implement its own: it runs tests/run.sh, which the lead wrote, and
          # reads the failure count off the summary line. Having two runners
          # was a real cost -- the lead's was parallel, the CI copy was serial,
          # so the gate ran ~20x slower than the identical suite locally and
          # degraded from 3s to 200s+ within a single run as the suite grew.
          #
          # run.sh must end with a line containing "failed=N" (or "N failed" /
          # "N failures"). If no count can be parsed the gate PASSES: an
          # unparseable summary is a lead problem, and must never be the reason
          # four workers cannot merge.
          failures_at() {
            git checkout -q -f "$1" 2>/dev/null || { echo ""; return; }
              # Overlay the CURRENT suite. tests/ does not live on main: the lead
              # authored 56% (s68a) to 81% (s68c) of all commits there, and under
              # block_on_outdated_branch every one of them invalidates every open
              # PR. Median gap between main commits was 42s / 87s -- shorter than
              # a CI run -- so branches could not stay mergeable (s68c lost 5 PRs
              # at 18-157 commits behind). With the suite on its own branch,
              # "main moved" means "a worker merged src", which is exactly when a
              # re-sync IS needed. Overlaying it on BOTH sides also removes the
              # s68f defect where base ran 1185 cases and head ran 1075.
              rm -rf tests
              cp -r /tmp/suite/tests tests
              # $3, when given, is a file of case names to KEEP: everything else is removed
              # before the run. run.sh globs tests/cases/*.sh, so pruning the directory is
              # how an arbitrary subset gets selected -- run.sh only takes a prefix, and
              # "assigned + already-passing" is not one.
              if [ -n "${3:-}" ] && [ -s "$3" ]; then
                for f in $(find tests/cases -name '*.sh' 2>/dev/null); do
                  n=${f#tests/cases/}; n=${n%.sh}
                  grep -qxF "$n" "$3" || rm -f "$f" "tests/cases/$n.expected" "tests/cases/$n.rc"
                done
              fi
            bash tests/run.sh > "/tmp/run.$2.log" 2>&1 || true
              # The failing SET, by name. This is the one thing CI knows that a
              # worker cannot cheaply derive, because only CI runs both sides: a
              # local run.sh shows what fails on the branch, not which of those
              # are NEW.
              grep -oE '^FAIL +[^ ]+' "/tmp/run.$2.log" | awk '{print $2}' | sort -u > "/tmp/fails.$2"
              # Prefer the explicit "failed=N" form. The looser "N failed"
              # pattern must only be a fallback: on "ran=951 failed=334" it
              # matches "951 failed" first and reports 951 instead of 334.
              n=$(tail -5 "/tmp/run.$2.log" | grep -oiE 'fail(ed|ures?)[=: ]+[0-9]+' | grep -oE '[0-9]+' | tail -1)
              [ -n "$n" ] || n=$(tail -5 "/tmp/run.$2.log" | grep -oiE '[0-9]+ +fail(ed|ures?)' | grep -oE '[0-9]+' | tail -1)
              echo "$n"
          }
          git clone "$REPO_URL" repo
          cd repo
          if ! git rev-parse --verify -q origin/tests >/dev/null 2>&1; then
            echo "no tests branch yet -- the lead has not published a suite; passing"
            exit 0
          fi
          rm -rf /tmp/suite; mkdir -p /tmp/suite
          git archive origin/tests tests 2>/dev/null | tar -x -C /tmp/suite 2>/dev/null || true
          if [ ! -f /tmp/suite/tests/run.sh ]; then
            echo "tests branch carries no tests/run.sh yet; passing"
            exit 0
          fi
          BASE=$(failures_at "$BASE_SHA" base); echo "base $BASE_SHA failures=${BASE:-unparsed}"

          # A case is `<goal>/<task>`: one directory per goal, so a worker assigned a goal
          # finds every case it owns in one place instead of parsing filenames out of prose.
          ( cd /tmp/suite/tests/cases 2>/dev/null && find . -name '*.sh' \
            | sed 's|^\./||; s|\.sh$||' ) | sort -u > /tmp/allcases
          sed 's|/.*||' /tmp/allcases | sort -u > /tmp/allgoals
          # P = what already passes on main: what previous merged PRs established.
          comm -23 /tmp/allcases /tmp/fails.base > /tmp/passing
          # G = the cases of the goals in CI's range. `src/ci-list.txt` lists one goal per
          # line and a worker appends its own in the PR that lands it, so the range is data in
          # the repo at the commit under test -- no API call, no issue-body parsing, nothing
          # that can fail to be retrieved.
          #
          # This replaces reading `Refs #<n>` and fetching that issue, which BLOCKED the merge
          # on any retrieval failure. That gate could not change the verdict it guarded: the
          # base side runs the FULL suite, so `passing` is complete, and `keep = G u passing`
          # only ever ADDS to what the head runs. It was blocking merges to protect a
          # non-blocking report -- and the blocked worker had no way to find out, since gitea
          # raises no notification when an Actions run finishes. In the 0.5h smoke a PR sat
          # blocked for the run's last ~15 minutes for exactly that reason. An absent or empty
          # list degrades to pure regression checking, which is the whole verdict anyway.
          : > /tmp/goals; : > /tmp/assigned
          git show "$HEAD_SHA:src/ci-list.txt" 2>/dev/null \
            | sed 's/#.*//' | tr -d ' \t' | grep -v '^$' | sort -u > /tmp/goals || true
          if [ -s /tmp/goals ]; then
            echo "goals in range: $(tr '\n' ' ' < /tmp/goals)"
            while IFS= read -r g; do
              [ -n "$g" ] || continue
              # A goal owns exactly the cases under its directory. Literal compare, so no
              # regex metacharacter in a goal name can widen or empty the selection.
              n=$(awk -v g="$g" 'index($0, g "/") == 1' /tmp/allcases \
                  | tee -a /tmp/assigned | wc -l)
              # A goal that selects nothing -- misspelled, or its cases not written yet --
              # produces an empty report, indistinguishable from "my goal is fully green".
              # Nothing here blocks, so saying it is the only way it reaches anyone.
              [ "$n" -gt 0 ] || echo "  note: goal '$g' has no cases -- tests/cases/$g/ is empty or absent"
            done < /tmp/goals
            sort -u -o /tmp/assigned /tmp/assigned
          else
            echo "goals in range: none listed in src/ci-list.txt (regression check only)"
          fi
          # The head runs only A u P. Anything outside it fails on both sides and can never
          # be a regression, so running it is pure cost and pure noise.
          sort -u /tmp/assigned /tmp/passing > /tmp/keep
          echo "scope: $(wc -l < /tmp/keep) cases on the head ($(wc -l < /tmp/assigned) assigned + $(wc -l < /tmp/passing) passing on main, of $(wc -l < /tmp/allcases) in the suite)"
          HEAD=$(failures_at "$HEAD_SHA" head /tmp/keep); echo "head $HEAD_SHA failures=${HEAD:-unparsed}"
          echo "--- tail of the head run (for diagnosing a broken run.sh) ---"
          tail -5 /tmp/run.head.log
          # A regression is a case that PASSED on main and FAILS here. That is a SET
          # question, not a count question: comparing totals merges a PR that fixes 20
          # cases and breaks 1 (885 -> 866 reads as progress), and that break is then
          # baked into the next PR's base, invisible forever.
          # Assigned cases that still fail are REPORTED, not blocking: gating on them is
          # the all-green gate that deadlocked 17 of 20 teams in sweep 6.5, six of which
          # shipped a repo containing tests/ and no source at all.
          STILL=$(comm -12 /tmp/fails.head /tmp/assigned)
          if [ -n "$STILL" ]; then
            echo "your sub-issue's cases still failing:"
            printf '%s\n' "$STILL" | head -20 | sed 's/^/  /'
            echo "(these do NOT block the merge -- partial progress lands)"
          fi
          # A regression is a head failure that PASSES on main. If the suite's cases could
          # not be enumerated (a lead free to lay tests/ out however they like), /tmp/passing
          # is empty and that intersection would be empty too -- i.e. the gate would silently
          # stop blocking anything. Fall back to the unscoped set difference in that case:
          # a scoping optimisation must never be able to disable the gate.
          if [ -s /tmp/allcases ]; then
            REGRESSED=$(comm -12 /tmp/fails.head /tmp/passing)
          else
            echo "note: no tests/cases/*.sh to enumerate; head ran unscoped"
            REGRESSED=$(comm -13 /tmp/fails.base /tmp/fails.head)
          fi
          NREG=$(printf '%s\n' "$REGRESSED" | grep -c . || true)
          if [ "$NREG" -gt 0 ]; then
            echo "REGRESSION: $NREG case(s) pass on main and fail on this branch:"
            printf '%s\n' "$REGRESSED" | head -50 | sed 's/^/  /'
            if [ "$NREG" -gt 50 ]; then echo "  ... and $((NREG - 50)) more"; fi
            echo ""
            echo "--- details for up to 10 of them; reproduce the rest with 'bash tests/run.sh <case>' ---"
            printf '%s\n' "$REGRESSED" | head -10 | while read -r c; do
              [ -n "$c" ] || continue
              awk -v c="$c" '$1=="FAIL" && $2==c {f=1} f && $1=="FAIL" && $2!=c {exit} f' /tmp/run.head.log | head -40
              echo ""
            done
            if [ "$NREG" -gt 10 ]; then echo "(showed 10 of $NREG regressed cases)"; fi
            exit 1
          fi
          # Backstop: if run.sh emits no '^FAIL <case>' lines the set is empty, and a
          # set-only gate would never block anything. Fall back to the totals.
          if [ -n "$BASE" ] && [ -n "$HEAD" ] && [ "$HEAD" -gt "$BASE" ]; then
            echo "REGRESSION: failures $BASE -> $HEAD, and run.sh printed no 'FAIL <case>'"
            echo "lines, so CI cannot tell you which. Have run.sh print one per failure."
            exit 1
          fi
          if [ -z "$BASE" ] || [ -z "$HEAD" ]; then
            echo "could not read a failure count from tests/run.sh output; passing."
            echo "the last line of run.sh should contain e.g. 'ran=120 failed=7'"
            exit 0
          fi
          echo "OK: failures $BASE -> $HEAD (no regression)"
          ) > /tmp/verdict.txt 2>&1
          rc=$?
          cat /tmp/verdict.txt
          # Gitea raises no notification when an Actions run finishes, so the router -- which
          # polls /api/v1/notifications -- can never emit an event for a check. A PR comment
          # does notify participants, and is the only push path back to the author.
          if [ -s /tmp/verdict.txt ] && [ -n "${PR_NUMBER:-}" ] && [ -n "${GT:-}" ]; then
            head -c 50000 /tmp/verdict.txt | jq -Rs '{body: .}' > /tmp/comment.json
            curl -fsS -X POST "$API_BASE/issues/$PR_NUMBER/comments" \
              -H "Authorization: token $GT" -H 'Content-Type: application/json' \
              --data-binary @/tmp/comment.json >/dev/null \
              || echo "could not post the verdict comment; the gate's verdict still stands"
          fi
          exit $rc

YML
)
    local body
    if [ -n "$cur_sha" ]; then
        body=$(jq -nc --arg c "$content_b64" --arg s "$cur_sha" --arg m "bootstrap: ensure lead-tests workflow" \
            '{message:$m, content:$c, sha:$s, branch:"main"}')
        api_token PUT "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" "$body" >/dev/null
        log "lead-tests.yml updated on ${GITEA_ORG}/${repo}"
    else
        body=$(jq -nc --arg c "$content_b64" --arg m "bootstrap: add lead-tests workflow" \
            '{message:$m, content:$c, branch:"main"}')
        api_token POST "/api/v1/repos/${GITEA_ORG}/${repo}/contents/${path}" "$body" >/dev/null
        log "lead-tests.yml created on ${GITEA_ORG}/${repo}"
    fi
}

ensure_agent_unwatched() {
    local repo="$1" agent="$2"
    local pwfile="$TOKENS_DIR/agent-${agent}.token"
    local agent_token
    agent_token=$(cat "$pwfile")
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: token $agent_token" \
        -X DELETE "${GITEA_HOST}/api/v1/repos/${GITEA_ORG}/${repo}/subscription")
    case "$code" in
        204|404) ;;
        # Best-effort cleanup. This used to `return 1`, and the call site runs it
        # bare inside a loop under `set -e` -- so one transient 502 from gitea
        # killed bootstrap BEFORE the act-runner registration token and all of
        # mattermost provisioning, and without .bootstrap-done nothing downstream
        # starts. Warn and carry on.
        *) log "WARN: unwatch ${agent}@${repo} returned HTTP $code (continuing)" ;;
    esac
    log "Unwatched ${agent} on ${GITEA_ORG}/${repo}"
}

ensure_no_legacy_hermes_webhook() {
    local repo="$1"
    local stale_ids
    stale_ids=$(api_token GET "/api/v1/repos/${GITEA_ORG}/${repo}/hooks" \
        | jq -c '.[] | select(.config.url // "" | test("hermes-agent-.*:8644/webhooks/gitea")) | .id' \
        || true)
    for id in $stale_ids; do
        api_token DELETE "/api/v1/repos/${GITEA_ORG}/${repo}/hooks/${id}" >/dev/null
        log "Deleted legacy hermes-agent webhook on ${GITEA_ORG}/${repo} (id=$id)"
    done
}

for repo in "${REPO_LIST[@]}"; do
    ensure_repo "$repo"
    ensure_codeowners "$repo"
    ensure_closes_workflow "$repo"
    ensure_tests_branch "$repo"
    ensure_ci_list "$repo"
    ensure_lead_tests_workflow "$repo"
    ensure_branch_protection "$repo"
    ensure_no_legacy_hermes_webhook "$repo"
    for agent in "${AGENT_LIST[@]}"; do
        ensure_agent_unwatched "$repo" "$agent"
    done
done

# ------------------------------------------------------------------
# 5b. R6 — fetch a global runner registration token for act_runner.
# Idempotent: re-fetch on every run; act_runner's `register` only uses
# it once and persists state to /data/.runner.
# ------------------------------------------------------------------
RUNNER_TOKEN_FILE="$TOKENS_DIR/runner.token"
runner_tok=$(api_token GET "/api/v1/admin/runners/registration-token" 2>/dev/null \
    | jq -r '.token // empty' || true)
if [ -n "$runner_tok" ]; then
    install -m 0600 /dev/stdin "$RUNNER_TOKEN_FILE" <<<"$runner_tok"
    log "Runner registration token written to $RUNNER_TOKEN_FILE"
else
    log "WARN: failed to fetch runner registration token (Actions may be disabled)"
fi

# ------------------------------------------------------------------
# 5c. R8 — mattermost user + PAT per agent (only if MATTERMOST_HOST set).
# Idempotent: skip user creation on conflict; reuse cached token if file
# exists and still validates.
# ------------------------------------------------------------------
if [ -n "${MATTERMOST_HOST:-}" ]; then
    : "${MATTERMOST_ADMIN_USER:=mmadmin}"
    : "${MATTERMOST_ADMIN_PASSWORD:?MATTERMOST_ADMIN_PASSWORD required when MATTERMOST_HOST set}"
    : "${MATTERMOST_ADMIN_EMAIL:=mmadmin@omcgitea.local}"
    : "${MATTERMOST_TEAM_NAME:=omcgitea}"
    : "${MATTERMOST_TEAM_DISPLAY:=omcgitea}"

    log "MATTERMOST_HOST=$MATTERMOST_HOST — provisioning users + tokens"

    # Wait for mattermost. The timeout must SKIP provisioning, not fall through:
    # `break` only leaves the for-loop, so execution continued into the admin
    # login below, where a connection-level curl failure under `set -euo pipefail`
    # killed bootstrap outright. That means .bootstrap-done is never written, and
    # secret-service / act-runner / every mini-router and agent gate on
    # `bootstrap: service_completed_successfully` -- so a degraded-chat condition
    # took down the entire stack instead of costing us mattermost.
    mm_ok=0
    log "Waiting for Mattermost at $MATTERMOST_HOST ..."
    for i in $(seq 1 180); do
        if curl -fsS "$MATTERMOST_HOST/api/v4/system/ping" >/dev/null 2>&1; then
            log "Mattermost up after ${i}s"
            mm_ok=1
            break
        fi
        sleep 1
    done
    if [ "$mm_ok" != "1" ]; then
        log "WARN: Mattermost NOT up after 180s — skipping mattermost provisioning"
        log "WARN: agents will have gitea but no chat channel this run"
    fi
    if [ "$mm_ok" = "1" ]; then

    # Login admin → session token
    mm_admin_token=$(curl -sS -i -d "{\"login_id\":\"${MATTERMOST_ADMIN_USER}\",\"password\":\"${MATTERMOST_ADMIN_PASSWORD}\"}" \
        "${MATTERMOST_HOST}/api/v4/users/login" | awk -F': ' '/^[Tt]oken:/ {gsub(/\r/,""); print $2; exit}')
    if [ -z "$mm_admin_token" ]; then
        # Bootstrap admin user (on truly fresh install)
        log "Mattermost admin login failed; creating admin via /api/v4/users (first user gets system_admin)"
        curl -fsS -X POST -H "Content-Type: application/json" \
            -d "$(jq -nc --arg u "$MATTERMOST_ADMIN_USER" --arg p "$MATTERMOST_ADMIN_PASSWORD" --arg e "$MATTERMOST_ADMIN_EMAIL" \
                '{username:$u, password:$p, email:$e, allow_marketing:false}')" \
            "${MATTERMOST_HOST}/api/v4/users" >/dev/null || true
        mm_admin_token=$(curl -sS -i -d "{\"login_id\":\"${MATTERMOST_ADMIN_USER}\",\"password\":\"${MATTERMOST_ADMIN_PASSWORD}\"}" \
            "${MATTERMOST_HOST}/api/v4/users/login" | awk -F': ' '/^[Tt]oken:/ {gsub(/\r/,""); print $2; exit}')
    fi

    if [ -z "$mm_admin_token" ]; then
        log "ERROR: cannot get mattermost admin session token; skipping mm provisioning"
    else
        log "Mattermost admin session OK"

        # Ensure team exists
        team_id=$(curl -sS -H "Authorization: Bearer $mm_admin_token" \
            "${MATTERMOST_HOST}/api/v4/teams/name/${MATTERMOST_TEAM_NAME}" | jq -r '.id // empty')
        if [ -z "$team_id" ]; then
            team_id=$(curl -sS -H "Authorization: Bearer $mm_admin_token" -H "Content-Type: application/json" \
                -X POST -d "$(jq -nc --arg n "$MATTERMOST_TEAM_NAME" --arg d "$MATTERMOST_TEAM_DISPLAY" \
                    '{name:$n, display_name:$d, type:"O"}')" \
                "${MATTERMOST_HOST}/api/v4/teams" | jq -r '.id // empty')
            log "Mattermost team ${MATTERMOST_TEAM_NAME} created (id=$team_id)"
        fi

        ensure_mm_user_token() {
            local agent="$1"
            local password_file="$TOKENS_DIR/agent-${agent}.password"
            local mm_token_file="$TOKENS_DIR/agent-${agent}-mm.token"
            local password
            password=$(cat "$password_file")

            # Cached token still valid?
            if [ -f "$mm_token_file" ]; then
                local tok code
                tok=$(cat "$mm_token_file")
                code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $tok" \
                    "${MATTERMOST_HOST}/api/v4/users/me")
                if [ "$code" = "200" ]; then
                    log "Mattermost token reused for $agent"
                    return 0
                fi
            fi

            # Ensure user
            local user_id user_resp lookup_resp
            lookup_resp=$(curl -sS -H "Authorization: Bearer $mm_admin_token" \
                "${MATTERMOST_HOST}/api/v4/users/username/${agent}")
            # NB: a 404 response body has shape `{"id":"app.user.get_by_username.app_error", ...}`,
            # so naively reading .id collides with user.id ("foo123..."). The error
            # response also has `.status_code` while the success response has `.create_at`.
            user_id=$(echo "$lookup_resp" | jq -r 'select(.status_code == null) | .id // empty')
            if [ -z "$user_id" ]; then
                user_resp=$(curl -sS -H "Authorization: Bearer $mm_admin_token" -H "Content-Type: application/json" \
                    -X POST -d "$(jq -nc --arg u "$agent" --arg p "$password" --arg e "${agent}@omcgitea.local" \
                        '{username:$u, password:$p, email:$e}')" \
                    "${MATTERMOST_HOST}/api/v4/users")
                user_id=$(echo "$user_resp" | jq -r 'select(.status_code == null) | .id // empty')
                if [ -z "$user_id" ]; then
                    log "Mattermost user $agent CREATE failed: $(echo "$user_resp" | head -c 200)"
                else
                    log "Mattermost user $agent created (id=$user_id)"
                fi
            fi
            [ -z "$user_id" ] && { log "WARN: cannot create mm user $agent"; return 1; }

            # Add to team (idempotent)
            curl -sS -o /dev/null -H "Authorization: Bearer $mm_admin_token" -H "Content-Type: application/json" \
                -X POST -d "$(jq -nc --arg t "$team_id" --arg u "$user_id" '{team_id:$t, user_id:$u}')" \
                "${MATTERMOST_HOST}/api/v4/teams/${team_id}/members" || true

            # Login as agent → grab session token (PAT requires
            # `EnableUserAccessTokens` config + per-user permission;
            # session tokens work everywhere with same auth surface.)
            local sess
            sess=$(curl -sS -i -d "$(jq -nc --arg u "$agent" --arg p "$password" '{login_id:$u, password:$p}')" \
                "${MATTERMOST_HOST}/api/v4/users/login" | awk -F': ' '/^[Tt]oken:/ {gsub(/\r/,""); print $2; exit}')
            if [ -z "$sess" ]; then
                log "WARN: cannot login as mm user $agent"
                return 1
            fi
            install -m 0600 /dev/stdin "$mm_token_file" <<<"$sess"
            log "Mattermost token written for $agent → $mm_token_file"
        }

        for agent in "${AGENT_LIST[@]}"; do
            ensure_mm_user_token "$agent" || true
        done
    fi
    fi
fi

# ------------------------------------------------------------------
# 6. Mark done
# ------------------------------------------------------------------
date -u +%FT%TZ > "$DONE_MARK"
log "Bootstrap done."
