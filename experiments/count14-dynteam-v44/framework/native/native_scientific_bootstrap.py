"""First-start scientific source hand-off; original native mode unchanged.

Builds from the exact accepted public conditional V2. Only trusted host launch
configuration may choose trusted-publisher mode, in a NEW root before workers.
It does not publish or approve a source bundle or complete native bootstrap.
"""
import hashlib
from common import need
V2_SHA256='a3672ccf64316790edeace917e36968fa9b3b9484ab935de22af4c11732426eb'
DEFAULT=': "${BOOTSTRAP_DATA_DIR:=/data}"\n'
MODE='''# Host-only scientific first-start selector. Native/gate4 default is unchanged.
: "${COUNT14_REPOSITORY_OWNER:=bootstrap}"
case "$COUNT14_REPOSITORY_OWNER" in
    bootstrap|trusted-publisher) ;;
    *) printf '%s\\n' '[bootstrap] COUNT14_REPOSITORY_OWNER_INVALID' >&2; exit 2 ;;
esac
'''
MARK='ADMIN_TOKEN_FILE="$TOKENS_DIR/admin.token"\n'
FIRSTSTART='''
# Never reuse the native DONE marker to attest scientific source publication.
if [ "$COUNT14_REPOSITORY_OWNER" = "trusted-publisher" ] && [ -e "$DONE_MARK" ]; then
    printf '%s\\n' '[bootstrap] COUNT14_SCIENTIFIC_NEW_ROOT_REQUIRED' >&2
    exit 2
fi
'''
START='for repo in "${REPO_LIST[@]}"; do\n    ensure_repo "$repo"\n'
END='\nRUNNER_TOKEN_FILE="$TOKENS_DIR/runner.token"'
EXTERNAL='''if [ "$COUNT14_REPOSITORY_OWNER" = "trusted-publisher" ]; then
    # No README, CODEOWNERS, branch protection or public auto-init repository.
    # Publication belongs to the existing trusted NativeGitea first-start port.
    # Check the configured exact target(s), never delete or rewrite old history.
    for repo in "${REPO_LIST[@]}"; do
        case "$repo" in
            ''|*[!a-zA-Z0-9_.-]*|[!a-zA-Z0-9]*) log "COUNT14_REPOSITORY_NAME_INVALID"; exit 2 ;;
        esac
        code=$(api_token_status GET "/api/v1/repos/${GITEA_ORG}/${repo}")
        if [ "$code" != "404" ]; then
            log "COUNT14_FRESH_REPOSITORY_REQUIRED"
            exit 1
        fi
    done
    log "COUNT14_SOURCE_PUBLICATION_DEFERRED_WORKERS_NOT_RELEASED"
else
'''

def build_scientific_bootstrap(source):
    need(type(source)is bytes and hashlib.sha256(source).hexdigest()==V2_SHA256,'SCIENTIFIC_BOOTSTRAP_V2_PIN')
    text=source.decode('utf-8');need(text.count(DEFAULT)==text.count(MARK)==text.count(START)==text.count(END)==1,'SCIENTIFIC_BOOTSTRAP_EXACT_ANCHORS')
    text=text.replace(DEFAULT,DEFAULT+MODE).replace(MARK,MARK+FIRSTSTART)
    first=text.index(START);last=text.index(END,first)
    original=text[first:last]
    return (text[:first]+EXTERNAL+original+'fi\n'+text[last:]).encode()
