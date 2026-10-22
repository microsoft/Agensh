#!/bin/bash
# Provision peer accounts, repositories, permissions and service tokens once per profile.
# Reuse valid credentials on reruns; write the completion marker after provisioning.

set -euo pipefail

: "${GITEA_HOST:=http://gitea:3000}"
: "${GITEA_ADMIN_USER:=chairman}"
: "${GITEA_ADMIN_PASSWORD:?GITEA_ADMIN_PASSWORD required}"
: "${GITEA_ORG:=omcgitea}"
: "${AGENTS:=agent1,agent2}"
: "${REPOS:=test-sandbox}"
: "${BOOTSTRAP_DATA_DIR:=/data}"

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
[ "${PBENCH_BOOTSTRAP_FORCE:-0}" = "1" ] && [ -f "$DONE_MARK" ] && \
    log "PBENCH_BOOTSTRAP_FORCE=1 — ignoring $DONE_MARK and re-provisioning"

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

get_or_create_token() {
    # Reuse a working cached token; otherwise remove its stale namesake before rotation.
    local user="$1" pass="$2" name="$3" scopes_json="$4" out_file="$5"

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

IFS=',' read -r -a AGENT_LIST <<<"$AGENTS"
IFS=',' read -r -a REPO_LIST <<<"$REPOS"

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
    local pbody
    pbody=$(jq -nc --arg n "$name" --arg p "$password" \
        '{source_id:0, login_name:$n, max_repo_creation:0, password:$p, must_change_password:false}')
    api_token PATCH "/api/v1/admin/users/${name}" "$pbody" >/dev/null
    log "User $name max_repo_creation=0 enforced, password synced to file"
}

PASSWORDS_DIR="$TOKENS_DIR"
# Persist passwords because the router's Gitea SSE feed requires browser-form login.

for agent in "${AGENT_LIST[@]}"; do
    pwfile="$PASSWORDS_DIR/agent-${agent}.password"
    if [ ! -f "$pwfile" ]; then
        openssl rand -hex 16 > "$pwfile"
        chmod 600 "$pwfile"
    fi
    pw=$(cat "$pwfile")
    ensure_user "$agent" "$pw"
    AGENT_SCOPES='["read:repository","write:repository","write:issue","write:user","read:notification"]'
    get_or_create_token "$agent" "$pw" "omcgitea-agent" "$AGENT_SCOPES" "$TOKENS_DIR/agent-${agent}.token"
done

rm -f "$TOKENS_DIR"/webhook-*.secret 2>/dev/null || true

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
    # Keep the coders team aligned with the configured peer list on forced reruns.
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
ensure_team "coders" "write"
ensure_team_membership_strict "coders" "${AGENT_LIST[@]}"

ensure_repo() {
    local repo="$1"
    local code
    code=$(api_token_status GET "/api/v1/repos/${GITEA_ORG}/${repo}")
    if [ "$code" = "200" ]; then
        log "Repo ${GITEA_ORG}/${repo} exists"
        return 0
    fi
    local body
    body=$(jq -nc --arg n "$repo" \
        '{name:$n, private:false, auto_init:true, default_branch:"main", description:"ProgramBench agent collaboration repository"}')
    api_token POST "/api/v1/orgs/${GITEA_ORG}/repos" "$body" >/dev/null
    log "Repo ${GITEA_ORG}/${repo} created"
}

ensure_branch_protection() {
    # Peers integrate through PR merges; direct main pushes are reserved for the admin.
    local repo="$1"
    local body
    body=$(jq -nc --arg b "main" \
        --arg admin "$GITEA_ADMIN_USER" \
        '{branch_name:$b,
          enable_push:true,
          enable_push_whitelist:true,
          push_whitelist_usernames:[$admin],
          push_whitelist_teams:[],
          push_whitelist_deploy_keys:false,
          required_approvals:0,
          enable_approvals_whitelist:true,
          approvals_whitelist_username:[],
          approvals_whitelist_teams:[],
          enable_merge_whitelist:true,
          merge_whitelist_usernames:[],
          merge_whitelist_teams:["coders"],
          dismiss_stale_approvals:false,
          block_on_rejected_reviews:false,
          block_on_official_review_requests:false,
          block_on_outdated_branch:false,
          require_code_owner_review:false,
          enable_status_check:false,
          status_check_contexts:[]}')
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

ensure_agent_unwatched() {
    # Avoid broadcasting every repository action to every worker through auto-watch.
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
        *) log "WARN: unwatch ${agent}@${repo} returned HTTP $code (continuing)" ;;
    esac
    log "Unwatched ${agent} on ${GITEA_ORG}/${repo}"
}

for repo in "${REPO_LIST[@]}"; do
    ensure_repo "$repo"
    ensure_codeowners "$repo"
    ensure_branch_protection "$repo"
    for agent in "${AGENT_LIST[@]}"; do
        ensure_agent_unwatched "$repo" "$agent"
    done
done

RUNNER_TOKEN_FILE="$TOKENS_DIR/runner.token"
runner_tok=$(api_token GET "/api/v1/admin/runners/registration-token" 2>/dev/null \
    | jq -r '.token // empty' || true)
if [ -n "$runner_tok" ]; then
    install -m 0600 /dev/stdin "$RUNNER_TOKEN_FILE" <<<"$runner_tok"
    log "Runner registration token written to $RUNNER_TOKEN_FILE"
else
    log "WARN: failed to fetch runner registration token (Actions may be disabled)"
fi

if [ -n "${MATTERMOST_HOST:-}" ]; then
    : "${MATTERMOST_ADMIN_USER:=mmadmin}"
    : "${MATTERMOST_ADMIN_PASSWORD:?MATTERMOST_ADMIN_PASSWORD required when MATTERMOST_HOST set}"
    : "${MATTERMOST_ADMIN_EMAIL:=mmadmin@omcgitea.local}"
    : "${MATTERMOST_TEAM_NAME:=omcgitea}"
    : "${MATTERMOST_TEAM_DISPLAY:=omcgitea}"

    log "MATTERMOST_HOST=$MATTERMOST_HOST — provisioning users + tokens"

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

    mm_admin_token=$(curl -sS -i -d "{\"login_id\":\"${MATTERMOST_ADMIN_USER}\",\"password\":\"${MATTERMOST_ADMIN_PASSWORD}\"}" \
        "${MATTERMOST_HOST}/api/v4/users/login" | awk -F': ' '/^[Tt]oken:/ {gsub(/\r/,""); print $2; exit}')
    if [ -z "$mm_admin_token" ]; then
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
            # Share the worker identity/password with Gitea and cache its chat session.
            local agent="$1"
            local password_file="$TOKENS_DIR/agent-${agent}.password"
            local mm_token_file="$TOKENS_DIR/agent-${agent}-mm.token"
            local password
            password=$(cat "$password_file")

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

            local user_id user_resp lookup_resp
            lookup_resp=$(curl -sS -H "Authorization: Bearer $mm_admin_token" \
                "${MATTERMOST_HOST}/api/v4/users/username/${agent}")
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

            curl -sS -o /dev/null -H "Authorization: Bearer $mm_admin_token" \
                -H "Content-Type: application/json" \
                -X PUT -d "$(jq -nc --arg p "$password" '{new_password:$p}')" \
                "${MATTERMOST_HOST}/api/v4/users/${user_id}/password" || true

            curl -sS -o /dev/null -H "Authorization: Bearer $mm_admin_token" -H "Content-Type: application/json" \
                -X POST -d "$(jq -nc --arg t "$team_id" --arg u "$user_id" '{team_id:$t, user_id:$u}')" \
                "${MATTERMOST_HOST}/api/v4/teams/${team_id}/members" || true

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

date -u +%FT%TZ > "$DONE_MARK"
log "Bootstrap done."
