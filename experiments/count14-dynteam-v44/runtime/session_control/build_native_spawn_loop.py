"""Cold extraction of the PINNED original native CLAIM-driven spawn loop.

Not a replacement algorithm/dispatcher or ProgramBench main. Original SQL,
one-newcomer/900s/slot-selection/launch/wake behavior survives. Only control
admission, original-owner active time/token stop and serial retirement seams
are inserted. The exact stopped-container retire port must still be bound.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH1 = _count14_os.environ.get('COUNT14_SCRATCH1_ROOT', '/srv/count14/scratch1')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import hashlib

from common import need

SOURCE_SHA='8b5da992d5eae47484d85267927054ddf6b63a8751f47b07475b43d8ea93653c'


def function(source,name):
    marker=name+'() {'
    need(source.count('\n'+marker)==1,'DYNTEAM_ONE_PINNED_NATIVE_FUNCTION')
    start=source.index('\n'+marker)+1;end=source.index('\n}\n',start)+3
    return source[start:end]


def spawn_delta(source):
    old=function(source,'spawn_loop');new=old
    sites=[('    stop_at=$((PBENCH_RUN_T0 + secs - 900))\n',''),
        ('    newcomer_since=$(date +%s)\n','    newcomer_since=-1\n'),
        ('    while [ "$stopping" = 0 ] && [ "$(date +%s)" -lt "$stop_at" ]; do\n',
'''    local control mode active_now nonce
    while [ "$stopping" = 0 ]; do
        control=$(count14_spawn_ctl READ) || { sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue; }
        read -r mode active_now nonce <<< "$control"
        [ "$mode" != FINAL ] || break
        [ "$mode" = RUNNING ] || { sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue; }
        [ "$newcomer_since" -ge 0 ] || newcomer_since="$active_now"
'''),
        ('$(date +%s) - newcomer_since','active_now - newcomer_since'),
        ('newcomer_since=$(date +%s)','newcomer_since="$active_now"'),
        ('                launched=$((launched + 1))\n',
'''                control=$(count14_spawn_ctl BEGIN "$((launched + 1))" "$next" 0) || return 2
                read -r mode active_now nonce <<< "$control"
                [ "$mode" != HOLD ] || { sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue; }
                [ "$mode" = ALLOW ] || return 2
                launched=$((launched + 1))
'''),
        ('                launch_worker "$launched" "$kickoff"\n',
'''                launch_worker "$launched" "$kickoff" || return 2
                count14_finish_same_launch "$launched" "$next" "$nonce" || return 2
'''),
        ('                if reuse_slot "$slot" "$request"; then\n',
'''                control=$(count14_spawn_ctl BEGIN "$slot" "$next" 1) || return 2
                read -r mode active_now nonce <<< "$control"
                [ "$mode" != HOLD ] || { sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue; }
                [ "$mode" = ALLOW ] || return 2
                if reuse_slot "$slot" "$request" "$nonce"; then
                    count14_finish_same_launch "$slot" "$next" "$nonce" || return 2
''')]
    for before,after in sites:
        expected=2 if before=='newcomer_since=$(date +%s)' else 1
        need(new.count(before)==expected,'DYNTEAM_PINNED_NATIVE_SPAWN_EXACT_DELTA_SITE')
        new=new.replace(before,after)
    need('date +%s' not in new and 'SELECT COUNT(*) FROM spawn_requests' in new and
         "SELECT COUNT(*) FROM board_gists WHERE type='CLAIM' AND account='$newcomer'" in new,
         'DYNTEAM_NATIVE_SPAWN_ORIGINAL_COUNT_QUERIES_AND_ACTIVE_CLOCK')
    return new


def reuse_delta(source):
    old=function(source,'reuse_slot')
    at=old.index('    # Provision the account')
    end=old.index('    sudo -n install -d')
    provision=old[at:old.index('    # The old agent keeps running')]
    need('secret_call "$wi" revive' in provision,'DYNTEAM_NATIVE_ORIGINAL_ACCOUNT_REVIVE_SITE')
    # Serial retirement/move must precede original revive. There can be no
    # parallel old/new bridge over one archive/control/role registration.
    serial='''    ids=$(slot_containers "$wi")
    retire_old_agent "$wname" "$request" "$retire_nonce" $ids || return 2
    if [ -d "$PROFILE_DATA_DIR/agents/$wname" ]; then
        sudo -n mv "$PROFILE_DATA_DIR/agents/$wname" "$PROFILE_DATA_DIR/agents/$wname.retiring-$request" || return 2
    fi
    if [ -d "$PROFILE_DATA_DIR/acp/$wname" ]; then
        sudo -n mv "$PROFILE_DATA_DIR/acp/$wname" "$PROFILE_DATA_DIR/acp/$wname.retiring-$request" || return 2
    fi
'''
    result=old[:at]+serial+provision+old[end:]
    result=result.replace('    REUSED_ACCOUNT=""\n','    REUSED_ACCOUNT=""\n    local retire_nonce="${3:-}"\n')
    need('retire_old_agent "$wname" "$request" $ids &' not in result and
         result.index('retire_old_agent')<result.index('secret_call "$wi" revive'),
         'DYNTEAM_NATIVE_REUSE_SERIAL_OLD_ARCHIVE_BEFORE_ACCOUNT_REVIVE')
    return result


CONTROL=('''# Retain the original up-slot/run-slot recipes, but NEVER implicitly add
# ProgramBench's private-reference overlay/default ENV_FILE. The cold owner
# supplies a frozen command containing only our generated base/safe overlay.
make() {
    local target="$1" arg profile_seen=0
    shift
    case "$target" in up-slot|run-slot) ;; *) return 64 ;; esac
    for arg in "$@"; do
        case "$arg" in
          PROFILE=*) [ "$arg" = "PROFILE=${COUNT14_NATIVE_PROFILE:?}" ] || return 64;profile_seen=1 ;;
          UP_FLAGS=*|SERVICES=*|SERVICE=*|NAME=*) ;;
          *) return 64 ;;
        esac
    done
    [ "$profile_seen" = 1 ] || return 64
    command "${COUNT14_NATIVE_MAKE:?}" "$target" "$@" \\
        "ENV_FILE=${COUNT14_NATIVE_ENV_FILE:?}" \\
        "COMPOSE_BASE=${COUNT14_NATIVE_COMPOSE_BASE:?}" \\
        "COMPOSE=${COUNT14_NATIVE_COMPOSE_COMMAND:?}"
}
# Never let sudo drop DOCKER_HOST and silently hit the system root disk.
# This is local to these frozen native functions, not a host/sudo configuration.
sudo() {
    [ "$1" != -n ] || shift
    if [ "$1" = docker ]; then
        shift
        case "${COUNT14_NATIVE_DOCKER_SOCKET:?}" in
          unix://''' + _C14_SCRATCH + '''/*|unix://''' + _C14_SCRATCH1 + '''/*) ;;
          *) return 64 ;;
        esac
        "${COUNT14_NATIVE_DOCKER:?}" --host "$COUNT14_NATIVE_DOCKER_SOCKET" "$@"
    else
        [ "$EUID" = 0 ] || return 64
        command "$@"
    fi
}
# Fixed host control child. All calls MUST use command substitution,
# so exec preserves the exact registered parent/child relation for SO_PEERCRED.
count14_spawn_ctl() {
    exec "${COUNT14_NATIVE_PYTHON:?}" -I -B "${COUNT14_NATIVE_SPAWN_CLIENT:?}" "$@"
}
count14_finish_same_launch() {
    local control mode active nonce attempt
    for attempt in $(seq 1 8); do
        control=$(count14_spawn_ctl FINISH "$1" "$2" "$3" 1) || return 2
        read -r mode active nonce <<< "$control"
        [ "$mode" != DONE ] || return 0
        [ "$mode" = RETAINED ] || return 2
        sleep "${PBENCH_SPAWN_POLL_S:-15}"
    done
    return 2  # retain SAME admitted effect; never repeat launch/wake/revive
}
retire_old_agent() {
    # Actual same-owner state machine. Original spawn BEGIN's exact nonce is
    # argument3; every CID is full length and checked against registration.
    count14_native_retire_stopped_exact "$@"
}
count14_native_retire_stopped_exact() {
    local wi="${1##*-worker}" ordinal="${2#spawn-}" nonce="$3" control mode active reply attempt
    shift 3
    [ "$#" = 2 ] || return 2
    # Repeated metadata BEGIN/POLL resumes the SAME job/Popen, never repeats a
    # model or native launch, and cannot authorize a different CID/nonce.
    for attempt in $(seq 1 8); do
        control=$(count14_spawn_ctl RETIRE_BEGIN "$wi" "$ordinal" "$nonce" "$@") || {
            sleep "${PBENCH_SPAWN_POLL_S:-15}"; continue;
        }
        read -r mode active reply <<< "$control"
        [ "$mode" != DONE ] || return 0
        [ "$mode" = RETAINED ] || return 2
        sleep "${PBENCH_SPAWN_POLL_S:-15}"
    done
    return 2  # retain SAME job and all original control children, no force
}
count14_run_original_spawn() {
    local required
    for required in log mm_dm_channel mm_post count14_native_retire_stopped_exact; do
        declare -F "$required" >/dev/null || return 64
    done
    spawn_loop "$@"
}
''')


def build(source,destination):
    source,destination=Path(source),Path(destination);raw=source.read_bytes()
    need(not source.is_symlink() and hashlib.sha256(raw).hexdigest()==SOURCE_SHA and not destination.exists(),
         'DYNTEAM_NATIVE_SPAWN_SOURCE_PIN_AND_NEW_COLD_OUTPUT')
    text=raw.decode()
    names=('start_agent_containers','launch_worker','retired_slot','slot_containers','secret_call','account_live')
    output='#!/bin/bash\n# Source-only frozen native functions, NOT ProgramBench main.\n'+CONTROL+'\n'
    functions=[function(text,n) for n in names]
    slot=names.index('slot_containers')
    need(functions[slot].count('sudo docker ps -aq --filter')==1,'DYNTEAM_NATIVE_EXACT_CONTAINER_ID_PROJECTION_SITE')
    functions[slot]=functions[slot].replace('sudo docker ps -aq --filter','sudo docker ps -aq --no-trunc --filter')
    output+='\n'.join(functions)+'\n'+reuse_delta(text)+'\n'+spawn_delta(text)+'\n'
    need('rm -f' not in output and 'docker logs' not in output and 'docker stop' not in output,
         'DYNTEAM_NATIVE_FORCE_REMOVE_LOG_BODY_AND_STOP_TIMEOUT_NOT_EXPORTED')
    with destination.open('x') as out:out.write(output)
    destination.chmod(0o500)
    return dict(source_sha256=SOURCE_SHA,output_sha256=hashlib.sha256(output.encode()).hexdigest(),
        original_functions=list(names),original_count_queries_preserved=True,
        still_required_actual_stopped_container_retire_port=False,
        still_required_actual_daemon_container_registration_and_full_cold_entry=True,scientific_activation_qualified=False)
