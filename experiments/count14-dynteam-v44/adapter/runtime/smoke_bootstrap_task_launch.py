"""One original CLAIM-driven shell in the SAME held smoke owner.

No new relay, ledger, dispatcher, signal, request replay or synthetic released
flag. Original shell/Make/MM functions run from their frozen source. Child and
exact birth survive observation failures; every wait is finite and lock-free.
"""
from pathlib import Path
import hashlib
import os
import select
import subprocess
import time

from common import need,digest
from native_peer_registry import process_birth
from build_native_spawn_loop import function,SOURCE_SHA
from native_docker_scope import scope_labels

READY=b'COUNT14_NATIVE_SPAWN_LAUNCHER_PREPARED\n'


def shell_prefix(source):
    need(type(source) is bytes and hashlib.sha256(source).hexdigest()==SOURCE_SHA,
         'DYNTEAM_ORIGINAL_NATIVE_LAUNCH_MM_HELPER_SOURCE_PIN')
    raw=source.decode('utf-8')
    # Exact original infrastructure functions only. No ProgramBench main,
    # source seed/evaluator/reference/prompt renderer or idle watchdog is run.
    log='log() { echo "[pbench] $*" >&2; }'
    need(raw.splitlines().count(log)==1,'DYNTEAM_ORIGINAL_NATIVE_LOG_FUNCTION_PIN')
    return log+'\n'+'\n'.join(function(raw,n) for n in ('mm_login','mm_user_id','mm_post','mm_dm_channel'))


def launcher_script(source):
    return ('#!/bin/bash\nset -e\n'
        'set -a\nsource "$ENV_FILE"\nset +a\n'
        'source "$SPAWN_SOURCE"\n'+shell_prefix(source)+'\n'
        'MM_ADMIN_TOKEN=""\nMM_BASE="http://127.0.0.1:$EDGE_MM_PORT"\n'
        'kickoff="$(cat -- "$TASK_DESCRIPTION_FILE"; printf x)"\n'
        'kickoff="${kickoff%x}"\n'
        'printf "COUNT14_NATIVE_SPAWN_LAUNCHER_PREPARED\\n" >&"$COUNT14_READY_FD"\n'
        'eval "exec ${COUNT14_READY_FD}>&-"\n'
        'read -r -n 1 count14_registered || exit 2\n'
        'count14_run_original_spawn 0 32 "$kickoff"\n').encode()


class NativeSameCoreSmokeLaunch:
    def __init__(self,core,trajectory,source_task_ports,*,pbench_source):
        need(core.contract.get('mode')=='smoke' and trajectory in core.rows and
             core.rows[trajectory]['arm']=='DYNTEAM' and
             source_task_ports is getattr(core,'source_task_ports',None) and
             source_task_ports.core is core and trajectory in core.gate.startup_held,
             'DYNTEAM_FIRST_REAL_SMOKE_ONLY_SAME_HELD_CORE_AND_SOURCE_TASK_PORTS')
        self.core,self.t,self.source_ports=core,trajectory,source_task_ports
        self.source=Path(pbench_source);self.source_bytes=self.source.read_bytes()
        self.script=launcher_script(self.source_bytes)
        self.child=None;self.birth=None;self.started=False;self.failure_type=None
        if not hasattr(core,'native_spawn_launches'):core.native_spawn_launches={}
        need(trajectory not in core.native_spawn_launches,'DYNTEAM_SOLE_ORIGINAL_NATIVE_LAUNCHER_NO_REPLAY')
        core.native_spawn_launches[trajectory]=self

    def _initial(self):
        core=self.core;t=self.t;docker=core.native_containers.docker
        roles=tuple(core.rows[t]['initial_active_roles'])
        need(set(roles)=={'worker-00','tester-00','checker-00'},'DYNTEAM_ORIGINAL_THREE_NATIVE_INITIAL_ROLES')
        core.native_containers.sync_boot_plans(t,roles)
        for role in roles:
            for component in ('agent','router'):
                key=t,role,component
                record=core.native_containers.records.get(key) or core.native_containers.boot_plans.get(key)
                need(record is not None,'DYNTEAM_INITIAL_EXACT_DOCKER_BOOT_PLAN_REQUIRED')
                row=docker.inspect(record.cid)
                need(row['running'] and row['pid']>0 and not row['paused'] and not row['dead'] and not row['restarting'] and
                     row['image']==core.native_containers.image_ids[component] and
                     process_birth(row['pid'])==record.init_birth,
                     'DYNTEAM_INITIAL_NATIVE_CONTAINER_FRESH_PID_START_BOOT_IMAGE')
                core.native_containers.validate(record if hasattr(record,'peer_birth') else
                    __import__('native_container_retirement').ContainerBinding(t,role,component,record.cid,
                        record.image_id,record.init_birth,record.init_birth),row,running=True)
        return True

    def try_start(self):
        # Explicit pre-effect HOLD, not an exception/replay/partial recovery.
        return self.start(_defer_unadmitted=True) is not None

    def start(self,*,_defer_unadmitted=False):
        need(not self.started and self.child is None and self.source_ports.rows[self.t]['state']=='SOURCE_TASK_CHANNEL_READY' and
             self.t in self.core.gate.startup_held,
             'DYNTEAM_NATIVE_LAUNCHER_ONCE_BEFORE_TASK_AND_MODEL_RELEASE')
        producer=getattr(self.core,'resource_producer',None)
        if producer is not None:producer.poll()
        self.core.cohort_resources.refresh()
        admitted = self.core.cohort_resources.system_open() and self.core.cold_bootstrap._infra_ready(self.t)
        if _defer_unadmitted is True and not admitted:
            return None  # No _initial/script/pipe/Popen/peer/task/release consumed.
        need(admitted,
             'DYNTEAM_NATIVE_LAUNCHER_FRESH_RESOURCES_AND_ACTUAL_INFRA_REQUIRED')
        self._initial()
        host=self.core.native_host_environment['trajectories'][self.t]
        layout=self.core.native_layout.current(self.t)
        root=Path(self.core.rows[self.t]['root']);path=root/'native-original-spawn-launcher.sh'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        try:
            with os.fdopen(fd,'wb',closefd=False) as out:out.write(self.script);out.flush();os.fsync(fd)
        finally:os.close(fd)
        env=dict(PATH='/usr/bin:/bin',HOME=str(root),LANG='C.UTF-8',**host['launcher_env'],
            ENV_FILE=host['envfile'],SPAWN_SOURCE=host['spawn_source'],ROOT=host['project_root'],
            PROFILE=host['profile'],PROFILE_DATA_DIR=layout['profile_root'],ORG_NAME=layout['org'],
            TASK_DESCRIPTION_FILE=str(self.source_ports.rows[self.t]['source_root']/'task-description.bin'))
        r,w=os.pipe2(os.O_CLOEXEC)
        try:
            env['COUNT14_READY_FD']=str(w)
            self.child=subprocess.Popen(['/bin/bash',str(path)],cwd=host['project_root'],env=env,
                stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,pass_fds=(w,))
            os.close(w);w=None
            self.birth=process_birth(self.child.pid)
            ready,_,_=select.select([r],[],[],15)
            need(bool(ready) and os.read(r,128)==READY and self.child.poll() is None,
                 'DYNTEAM_NATIVE_SPAWN_LAUNCHER_READY_BOUND_RETAIN_SAME_CHILD')
            self.core.peers.register_from_launcher(self.t,'worker-00',self.birth,
                expected_birth=self.birth,purpose='launcher')
            self.child.stdin.write(b'1');self.child.stdin.flush()
            self.started=True
        except Exception as error:
            self.failure_type=type(error).__name__
            raise
        finally:
            os.close(r)
            if w is not None:os.close(w)
        return self.public()

    @property
    def released(self):
        # True only after the actual ORIGINAL gate appends its durable event.
        with self.core.ledger.mutex:
            n=self.core.ledger.db.execute("SELECT COUNT(*) FROM events WHERE trajectory=? AND kind='NATIVE_STARTUP_SEARCH_RELEASED'",(self.t,)).fetchone()[0]
            return self.started and self.t not in self.core.gate.startup_held and n==1

    def validate_release_prefix(self):
        need(self.started and self.child is not None and self.child.poll() is None and
             process_birth(self.child.pid)==self.birth and not self.released and
             self.t in self.core.gate.startup_held,
             'DYNTEAM_RELEASE_REQUIRES_SAME_LIVE_NATIVE_SPAWN_LAUNCHER')
        with self.core.peers._lock:
            registered=self.core.peers._peers.get((self.t,'worker-00','launcher'))
        need(registered==self.birth,'DYNTEAM_RELEASE_EXACT_REGISTERED_LAUNCHER_BIRTH')
        # Publish only a completed original scheduled sampler before admission.
        # Never restamp a receipt, wait for a new census, or relax its predicate.
        producer=getattr(self.core,'resource_producer',None)
        if producer is not None:producer.poll()
        self.core.cohort_resources.refresh()
        admission_deadline=time.monotonic()+45
        while not self.core.cohort_resources.experiment_open() and time.monotonic()<admission_deadline:
            time.sleep(min(.5,max(0,admission_deadline-time.monotonic())))
            if producer is not None:producer.poll()
            self.core.cohort_resources.refresh()
        need(self.core.cohort_resources.experiment_open() and self.source_ports.rows[self.t]['state']=='SOURCE_TASK_CHANNEL_READY',
             'DYNTEAM_RELEASE_FRESH_RESOURCES_AND_SAME_SOURCE_TASK')
        self._initial()
        return self.public()

    def public(self):
        return dict(trajectory=self.t,started=self.started,released=self.released,
            original_native_spawn_child_pid=None if self.child is None else self.child.pid,
            failure_type=self.failure_type,model_dispatched_by_host=0,no_automatic_retry=True)
