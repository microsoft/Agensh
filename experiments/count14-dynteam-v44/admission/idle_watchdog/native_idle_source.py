"""Pinned native watchdog/MM/library bytes; never inspect a prompt asset."""
from pathlib import Path
from dataclasses import dataclass
import hashlib

SOURCE_SHA='8b5da992d5eae47484d85267927054ddf6b63a8751f47b07475b43d8ea93653c'
LIB_SHA='9c79edd349b7bf1707472742139433535139a1c42b89ba9bb2b5866692e15adb'
FUNCTIONS=('mm_login','mm_user_id','mm_post','mm_dm_channel','watchdog_uem_pending',
           'watchdog_current_account','watchdog_consider','watchdog_tick_compose')


def need(ok,code):
    if not ok:raise ValueError(code)


@dataclass(frozen=True)
class NativeIdleSources:
    pbench_source:Path
    prompt_render_library:Path
    opaque_prompts_directory:Path


def function(source,name):
    marker='\n'+name+'() {'
    need(source.count(marker)==1,'IDLE_ONE_PINNED_NATIVE_FUNCTION')
    start=source.index(marker)+1;end=source.index('\n}\n',start)+3
    return source[start:end]


def compile_script(sources):
    need(type(sources)is NativeIdleSources,'IDLE_EXACT_TYPED_ORIGINAL_SOURCE_BINDINGS')
    source,lib=Path(sources.pbench_source),Path(sources.prompt_render_library)
    need(source.resolve()==source and lib.resolve()==lib and not source.is_symlink() and not lib.is_symlink() and
         lib==source.with_name('lib_prompts.sh') and
         Path(sources.opaque_prompts_directory)==source.parent.parent/'prompts',
         'IDLE_SAME_ORIGINAL_NATIVE_SOURCE_LIBRARY_AND_OPAQUE_ASSET_DIRECTORY')
    raw=source.read_bytes();library=lib.read_bytes()
    need(hashlib.sha256(raw).hexdigest()==SOURCE_SHA and hashlib.sha256(library).hexdigest()==LIB_SHA,
         'IDLE_EXACT_70E_NATIVE_SOURCE_AND_RENDER_LIBRARY_PINS')
    text=raw.decode();parts=[];proof=[]
    for name in FUNCTIONS:
        body=function(text,name)
        if name in('watchdog_current_account','watchdog_consider'):
            replaced=body.replace(name+'() {','_count14_original_'+name+'() {',1)
            need(replaced.replace('_count14_original_'+name+'() {',name+'() {',1)==body,
                 'IDLE_ORIGINAL_FUNCTION_ONLY_PRIVATE_NAME_ALIAS_INVERSE_BYTES')
            parts.append(replaced)
        else:parts.append(body)
        proof.append(dict(function=name,original_source_sha256=hashlib.sha256(body.encode()).hexdigest(),
                          scientific_conditions_original_bytes=True))
    # The original rendered body and every scientific current-account/queue/
    # threshold/recheck/fallback condition stay in these exact native functions.
    script='''#!/bin/bash
set -e
set -a
source "$ENV_FILE"
set +a
source "$SPAWN_SOURCE"
ROOT="$COUNT14_IDLE_NATIVE_ROOT"
MM_ADMIN_TOKEN=""
MM_BASE="http://127.0.0.1:$EDGE_MM_PORT"
MYSQL_ROOT_PW="$MYSQL_ROOT_PASSWORD"
WORKER_IDLE_THRESHOLD=600
WORKER_IDLE_REPEAT=600
WORKER_CHECK_INTERVAL=60
log() { :; }
'''+library.decode()+'\n'+'\n'.join(parts)+'''\n# Source data stays opaque; wrappers project only native control timestamps.
watchdog_current_account() {
    local routing
    routing="$(_count14_original_watchdog_current_account "$@")" || return $?
    [ -n "$routing" ] || return 0
    printf '%s' "$routing" | "$COUNT14_IDLE_PYTHON" -I -B "$COUNT14_IDLE_RUNTIME" WAKE "$COUNT14_IDLE_HOME" "$1"
}
watchdog_consider() {
    local times active_idle active_now
    times=$("$COUNT14_IDLE_PYTHON" -I -B "$COUNT14_IDLE_RUNTIME" ACTIVITY "$COUNT14_IDLE_HOME" "$1" "$2" "$3") || return 0
    read -r active_idle active_now <<< "$times"
    COUNT14_IDLE_CURRENT_WORKER="$1"
    _count14_original_watchdog_consider "$1" "$active_idle" "$active_now" "$4"
}
sudo() {
    [ "$1" != -n ] || shift
    case "$1" in
      docker) shift; "$COUNT14_IDLE_PYTHON" -I -B "$COUNT14_IDLE_RUNTIME" BOUNDED "$COUNT14_IDLE_HOME" "$COUNT14_NATIVE_DOCKER" --host "$COUNT14_NATIVE_DOCKER_SOCKET" "$@" ;;
      python3) shift; "$COUNT14_IDLE_PYTHON" -I -B "$COUNT14_IDLE_RUNTIME" BOUNDED "$COUNT14_IDLE_HOME" /usr/bin/python3 "$@" ;;
      find) shift; "$COUNT14_IDLE_PYTHON" -I -B "$COUNT14_IDLE_RUNTIME" BOUNDED "$COUNT14_IDLE_HOME" /usr/bin/find "$@" ;;
      *) return 64 ;;
    esac
}
curl() {
    local arg previous="" payload="" post=0 url="";local -a args=()
    for arg in "$@"; do
        if [ "$previous" = -d ]; then payload="$arg"; args+=(COUNT14_OPAQUE_STDIN)
        else args+=("$arg"); fi
        [ "$arg" != POST ] || post=1
        previous="$arg";url="$arg"
    done
    if [ "$post" = 1 ] && [ "$url" = "$MM_BASE/api/v4/posts" ]; then
        printf '%s' "$payload" | "$COUNT14_IDLE_PYTHON" -I -B "$COUNT14_IDLE_RUNTIME" POST "$COUNT14_IDLE_HOME" "$COUNT14_IDLE_CURRENT_WORKER" "${args[@]}"
    else
        command curl --connect-timeout 5 --max-time 15 "$@"
    fi
}
watchdog_tick_compose "$COUNT14_IDLE_WALL_SECONDS" "$COUNT14_IDLE_DEDUP"
'''
    return script.encode(),proof
