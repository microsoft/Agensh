#!/bin/bash
# omcgitea M1 bootstrap
#
# Idempotent. Sets up Gitea so agents can collaborate via PR/review/merge.
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
# TEAMCONFIG. Format: lead=<a>;reviewer=<a,b>;coder=<c,d,...>
# Drives org team membership only — md files do NOT contain role/roster info.
: "${ROLES:=}"

TOKENS_DIR="$BOOTSTRAP_DATA_DIR/tokens"
DONE_MARK="$TOKENS_DIR/.bootstrap-done"
ADMIN_TOKEN_FILE="$TOKENS_DIR/admin.token"

mkdir -p "$TOKENS_DIR"
chmod 700 "$TOKENS_DIR"

log() { echo "[bootstrap] $*" >&2; }

if [ -f "$DONE_MARK" ] && [ "${PBENCH_BOOTSTRAP_FORCE:-0}" != "1" ]; then
    log "Already done (mark=$DONE_MARK), exit 0"
    exit 0
fi
# PBENCH_BOOTSTRAP_FORCE=1 ignores the marker. It exists for the k8s path, where
# "has bootstrap run" is already recorded by the Job's completion status and
# scripts/pbench_k8s_up.sh deletes the old Job before applying. Two sources of
# truth for the same fact, and the file one wins: a redeploy carrying a real fix
# short-circuits to "Already done" and changes nothing, while the Job reports
# success. Under compose the marker stays authoritative (the container restarts
# in place); `make bootstrap-rerun` still clears it.
[ "${PBENCH_BOOTSTRAP_FORCE:-0}" = "1" ] && [ -f "$DONE_MARK" ] && \
    log "PBENCH_BOOTSTRAP_FORCE=1 — ignoring $DONE_MARK and re-provisioning"

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

# Build a single-line CSV per role (diagnostics only — bootstrap writes no
# roles.env; an agent introspects its role via the Gitea team API).
_csv() { local IFS=,; echo "$*"; }
LEAD_CSV=$(_csv "${LEAD_LIST[@]}")
REVIEWER_CSV=$(_csv "${REVIEWER_LIST[@]}")
CODER_CSV=$(_csv "${CODER_LIST[@]}")
log "Role CSVs (informational): lead=${LEAD_CSV} reviewer=${REVIEWER_CSV} coder=${CODER_CSV}"
# Remove any stale roles.env a reused tokens dir still carries.
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
    # max_repo_creation=0 so agents cannot create repos at runtime, even
    # though their token carries write:repository (needed for push/merge/
    # review). max_repo_creation is the orthogonal Gitea control that doesn't
    # bleed into PR auth. On Gitea 1.22.6 it hits CreateRepository's
    # MaxCreationLimit check before any repo row is touched. Idempotent —
    # PATCH each boot.
    #
    # The password rides along, and that is what makes this idempotent for an
    # EXISTING user rather than only for a fresh one. $pwfile is the source of
    # truth: the callers below basic-auth as the agent with it, and mini-router
    # reads it for mattermost form auth. Without this line the two can diverge
    # and nothing says so -- lose the tokens dir while gitea keeps its users
    # (a wiped volume, a fresh k8s namespace over an old gitea disk) and
    # bootstrap generates a NEW random password, stores it, never tells gitea,
    # then dies at get_or_create_token's basic auth with a bare
    # `curl: (22) ... 401` naming neither the user nor the call.
    local pbody
    pbody=$(jq -nc --arg n "$name" --arg p "$password" \
        '{source_id:0, login_name:$n, max_repo_creation:0, password:$p, must_change_password:false}')
    api_token PATCH "/api/v1/admin/users/${name}" "$pbody" >/dev/null
    log "User $name max_repo_creation=0 enforced, password synced to file"
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
    # notification pulls.
    # write:repository is REQUIRED for push, merge, and create-review.
    # Without it merge breaks entirely and agents go looking for
    # password-basic-auth back-channels. Repo-creation prevention is
    # handled at user-level by max_repo_creation=0 in ensure_user().
    AGENT_SCOPES='["read:repository","write:repository","write:issue","write:user","read:notification"]'
    get_or_create_token "$agent" "$pw" "omcgitea-agent" "$AGENT_SCOPES" "$TOKENS_DIR/agent-${agent}.token"
done

# Purge legacy webhook secrets — the M2-E.1 router replaces the webhook path.
# Safe on fresh data dirs (glob with no matches just no-ops).
rm -f "$TOKENS_DIR"/webhook-*.secret 2>/dev/null || true

# ------------------------------------------------------------------
# 4b. Ensure org `omcgitea` + leads/reviewers/coders teams + members.
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
    # Branch protection uses team whitelists, not user lists.
    # require_code_owner_review=true so changes touching paths in
    # CODEOWNERS (e.g. .team/*) require the listed owner's approval.
    #
    # REQUIRED_APPROVALS=0 selects the test-gate topology: there is no
    # review stage, so CI is the only gate. Every OTHER review-derived blocker
    # has to come off with it, or a merge stalls forever waiting on a review
    # that no agent is ever going to perform:
    #   block_on_official_review_requests — a stray request_review blocks merge
    #   require_code_owner_review         — CODEOWNERS approval nobody will give
    #   block_on_rejected_reviews         — a stale REJECT can never be cleared
    # block_on_outdated_branch: ON by default (otherwise stale branches can
    # silently merge over each other and corrupt shared files), switchable via
    # PBENCH_BLOCK_OUTDATED.
    #
    # What it costs with 16 peers merging continuously: `main` moves between
    # opening a PR and merging it, so most merges return HTTP 405 "not
    # mergeable". The team misdiagnoses it as an authorship rule -- "PR creator
    # cannot merge own PR", "reciprocal peer merge required" -- and rarely
    # reaches for gitea's actual remedy, update_branch.
    #
    # Note what it does NOT protect against being lost: git still refuses
    # TEXTUAL conflicts either way. What only this setting prevents is a
    # semantic conflict -- two branches editing different regions of one file,
    # auto-merging cleanly, producing an incoherent result. That is a real risk
    # on a task with a large shared core.
    local rev_blockers=true
    if [ "$REQUIRED_APPROVALS" = "0" ]; then rev_blockers=false; fi
    local block_outdated=true
    if [ "${PBENCH_BLOCK_OUTDATED:-1}" != "1" ]; then block_outdated=false; fi
    # There is no lead role: every agent is a peer coder who picks its own
    # area, so no one publishes a shared suite to main and nothing needs a
    # whitelist beyond the admin. No lead-tests context is required.
    local checks='["closes-issue-check / check (pull_request)"]'
    # PBENCH_CI_GATE=0: no workflows are seeded, so no context can ever report.
    # enable_status_check MUST go false with them -- leaving it true with any
    # context listed parks every PR at "pending" permanently.
    local status_gate=true
    if [ "${PBENCH_CI_GATE:-1}" != "1" ]; then
        status_gate=false
        checks='[]'
    fi
    local body
    body=$(jq -nc --arg b "main" \
        --arg admin "$GITEA_ADMIN_USER" \
        --argjson revb "$rev_blockers" \
        --argjson outdated "$block_outdated" \
        --argjson checks "$checks" \
        --argjson gate "$status_gate" \
        --argjson appr "$REQUIRED_APPROVALS" \
        '{branch_name:$b,
          enable_push:true,
          enable_push_whitelist:true,
          push_whitelist_usernames:[$admin],
          push_whitelist_teams:[],
          push_whitelist_deploy_keys:false,
          required_approvals:$appr,
          enable_approvals_whitelist:true,
          approvals_whitelist_username:[],
          approvals_whitelist_teams:["reviewers"],
          enable_merge_whitelist:true,
          merge_whitelist_usernames:[],
          merge_whitelist_teams:["directors","reviewers","coders"],
          dismiss_stale_approvals:$revb,
          block_on_rejected_reviews:$revb,
          block_on_official_review_requests:$revb,
          block_on_outdated_branch:$outdated,
          require_code_owner_review:$revb,
          enable_status_check:$gate,
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
    # Write .gitea/CODEOWNERS so changes to .team/* require chairman.
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
        # Best-effort cleanup, never `return 1`: the call site runs it bare
        # inside a loop under `set -e`, so one transient 502 from gitea would
        # kill bootstrap BEFORE the act-runner registration token and all of
        # mattermost provisioning, and without .bootstrap-done nothing
        # downstream starts. Warn and carry on.
        *) log "WARN: unwatch ${agent}@${repo} returned HTTP $code (continuing)" ;;
    esac
    log "Unwatched ${agent} on ${GITEA_ORG}/${repo}"
}

for repo in "${REPO_LIST[@]}"; do
    ensure_repo "$repo"
    ensure_codeowners "$repo"
    # PBENCH_CI_GATE=0 removes the gate ENTIRELY: no workflows seeded, and
    # ensure_branch_protection drops status checks to match. Both halves must
    # move together -- a required context whose job never runs sits at "pending"
    # forever and pending blocks merge, so seeding neither workflow while still
    # requiring their contexts would deadlock every PR in the run and score
    # 0.00% without a single error line.
    if [ "${PBENCH_CI_GATE:-1}" = "1" ]; then
        ensure_closes_workflow "$repo"
    else
        log "PBENCH_CI_GATE=0 — skipping closes-issue-check workflow on ${GITEA_ORG}/${repo}"
    fi
    ensure_branch_protection "$repo"
    for agent in "${AGENT_LIST[@]}"; do
        ensure_agent_unwatched "$repo" "$agent"
    done
done

# ------------------------------------------------------------------
# 5b. Fetch a global runner registration token for act_runner.
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
# 5c. Mattermost user + PAT per agent (only if MATTERMOST_HOST set).
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

            # Sync the password, for the same reason ensure_user() does on the
            # gitea side: $pwfile is the source of truth and this account may
            # predate it. A user that already existed keeps whatever password it
            # was created with, the login below then fails with the freshly
            # generated one, and the only symptom is "WARN: cannot login as mm
            # user" plus a missing -mm.token -- so the agent comes up, gets no
            # mattermost credential, and is simply never woken by a DM.
            # Sysadmin may set another user's password with new_password alone.
            curl -sS -o /dev/null -H "Authorization: Bearer $mm_admin_token" \
                -H "Content-Type: application/json" \
                -X PUT -d "$(jq -nc --arg p "$password" '{new_password:$p}')" \
                "${MATTERMOST_HOST}/api/v4/users/${user_id}/password" || true

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
