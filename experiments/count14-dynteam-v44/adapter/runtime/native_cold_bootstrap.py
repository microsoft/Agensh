"""Executable SAME-owner native infrastructure/initial-role bootstrap prefix.

Original Make/Bash functions, pinned private Compose/environment and existing
peer/control owner are orchestrated here. No new scientific dispatcher/model
release. Popen objects survive timeout/failed observation; no blind retries.
Full task/tool/checkpoint/K3 ports are STILL required for science PREPARED.
"""
from pathlib import Path
import json
import os
import subprocess
import time
import traceback

from common import need,digest
from native_beta_layout import native_aliases
from native_host_environment import INFRA,infra_labels

GIB=1024**3


def mem_available():
    # Fixed system resource metadata only, not process maps or scientific data.
    with open('/proc/meminfo','rb') as source:
        for line in source:
            if line.startswith(b'MemAvailable:'):return int(line.split()[1])*1024
    raise RuntimeError('DYNTEAM_HOST_MEMAVAILABLE_UNAVAILABLE')


class NativeColdBootstrap:
    def __init__(self,core,*,projected_additional_bytes,memory_reader=None):
        need(hasattr(core,'native_host_environment') and
             core.native_host_environment['state']=='HOST_ENV_EXPORTED_MODEL_GATES_HELD' and
             not hasattr(core,'cold_bootstrap') and type(projected_additional_bytes) is int and projected_additional_bytes>=0 and
             (memory_reader is None or core.qualification_only), 'DYNTEAM_ORIGINAL_COLD_BOOTSTRAP_BINDINGS')
        self.core=core;self.forecast=projected_additional_bytes
        self.memory=mem_available if memory_reader is None else memory_reader
        self.records={};self.infra_birth_records={};core.cold_bootstrap=self

    def _held(self):
        need(set(self.core.gate.startup_held)==set(self.core.rows) and not self.core.scientific_activation_qualified,
             'DYNTEAM_BOOTSTRAP_NEVER_RELEASES_MODEL_OR_SCIENTIFIC_GATES')
        with self.core.ledger.mutex:
            need(self.core.ledger.db.execute("SELECT COUNT(*) FROM requests WHERE state IN ('SENT','SETTLED','UNKNOWN')").fetchone()[0]==0,
                 'DYNTEAM_BOOTSTRAP_NO_ALREADY_PAID_MODEL_TRAJECTORY')

    def _resources(self):
        self._held();available=self.memory()
        need(type(available) is int and available-self.forecast>=80*GIB,
             'DYNTEAM_NATIVE_BOOTSTRAP_KEEP64GIB_PLUS_SMOKE16GIB_AFTER_FORECAST')
        self.core.native_containers.docker.verify_daemon()
        resources=getattr(self.core,'cohort_resources',None)
        need(resources is not None or self.core.qualification_only,
             'DYNTEAM_PRODUCTION_BOOTSTRAP_REQUIRES_BOUND_COHORT_RESOURCES')
        if resources is not None:
            producer=getattr(self.core,'resource_producer',None)
            if producer is not None:producer.poll()
            resources.refresh()
            resources.before_bootstrap(self.forecast)

    def _receipt(self,record,kind,**extra):
        record['sequence']+=1
        value=dict(schema='count14-native-cold-bootstrap-public-v1',trajectory_id=record['trajectory'],kind=kind,
            sequence=record['sequence'],phase=record['phase'],at_mono_ns=time.monotonic_ns(),models=0,
            model_gates_released=False,scientific_PREPARED=False,**extra)
        path=record['receipt_root']/(str(record['sequence']).zfill(4)+'-'+kind+'.json')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        try:
            with os.fdopen(fd,'wb',closefd=False) as out:out.write((json.dumps(value,sort_keys=True)+'\n').encode());out.flush();os.fsync(fd)
        finally:os.close(fd)

    def _spawn(self,record,argv,env,*,cwd):
        self._resources()
        self._receipt(record,'CONTROL_START_INTENT')
        record['child']=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        from native_peer_registry import process_birth
        from dataclasses import asdict
        record.setdefault('control_births',[]).append(asdict(process_birth(record['child'].pid)))
        record['started_ns']=time.monotonic_ns()
        self._receipt(record,'CONTROL_STARTED',own_control_pid=record['child'].pid)

    def start(self,t):
        need(t in self.core.rows,'DYNTEAM_NATIVE_BOOTSTRAP_REGISTERED_TRAJECTORY')
        self._resources()
        if t in self.records:return self.public(t) # no second Popen/UP
        host=self.core.native_host_environment['trajectories'][t]
        root=Path(self.core.rows[t]['root'])/'native-bootstrap-public';root.mkdir(mode=0o700)
        record=dict(trajectory=t,phase='INFRA_PENDING',child=None,sequence=0,receipt_root=root,
                    started_ns=None,warning120=False,failure_type=None)
        self.records[t]=record
        # Exact safe service list: no act-runner, official test/evaluator or
        # latent worker/helper services. Images were frozen by env compiler.
        command=[*host['compose'],'up','-d','--no-build','--pull','never',*INFRA]
        try:self._spawn(record,command,{'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(root)},cwd=host['project_root'])
        except Exception as error:
            record['failure_type']=type(error).__name__
            self._receipt(record,'FAILED_RETAINED',exception_type=record['failure_type'],
                exception_message=str(error),infra_traceback=traceback.format_exc())
        return self.public(t)

    def _initial(self,record):
        t=record['trajectory'];host=self.core.native_host_environment['trajectories'][t]
        aliases=native_aliases(self.core.rows[t]['arm'])
        need(set(host['initial_roles'])=={'worker-00','checker-00','tester-00'},
             'DYNTEAM_NATIVE_EXACT_THREE_INITIAL_SCIENTIFIC_ROLES')
        services=[aliases[r][k] for r in ('tester-00','checker-00','worker-00') for k in ('agent_service','router_service')]
        env=dict(PATH='/usr/bin:/bin',LANG='C.UTF-8',HOME=str(record['receipt_root']),
            **host['launcher_env'],SPAWN_SOURCE=host['spawn_source'],PROFILE=host['profile'],
            INITIAL_SERVICES=' '.join(services))
        record['phase']='INITIAL_COMMAND_PENDING'
        # Real extracted original Make recipe; no ProgramBench main, question
        # loading, task DM, native spawn consumer or racing round starts here.
        script='source "$SPAWN_SOURCE"; make up-slot PROFILE="$PROFILE" UP_FLAGS="--no-build --pull never" SERVICES="$INITIAL_SERVICES"'
        self._spawn(record,['/bin/bash','-c',script],env,cwd=host['project_root'])

    def try_start_initial(self,t):
        # ORIGINAL initial is not entered until eligibility is real. No
        # record phase, CONFIG_ENTERED, intent, child or native action on HOLD.
        self._held();record=self.records[t]
        need(record['phase']=='INFRA_READY_AWAIT_SOURCE_PUBLICATION' and record['child'] is None and
             record['failure_type'] is None,'DYNTEAM_INITIAL_AFTER_EXACT_INFRA_READY_ONCE')
        resources=getattr(self.core,'cohort_resources',None)
        need(resources is not None or self.core.qualification_only,
             'DYNTEAM_PRODUCTION_BOOTSTRAP_REQUIRES_BOUND_COHORT_RESOURCES')
        if resources is not None:
            producer=getattr(self.core,'resource_producer',None)
            need(producer is not None or self.core.qualification_only,
                 'DYNTEAM_INITIAL_PRECONSUMPTION_REQUIRES_ORIGINAL_REGISTERED_PRODUCER')
            if producer is not None:producer.poll() # original20s/RUNNING/55s controls
            resources.refresh() # original real receipt; no new census/probe
            if not resources.before_bootstrap(self.forecast,_defer_unadmitted=True):return False
        self.start_initial(t) # original selected formal/compose/UID0 wrapper
        return True

    def start_initial(self,t):
        """Publish real source/task/tester inputs BEFORE native clone/start."""
        self._held();record=self.records[t]
        need(record['phase']=='INFRA_READY_AWAIT_SOURCE_PUBLICATION' and record['child'] is None and
             record['failure_type'] is None,'DYNTEAM_INITIAL_AFTER_EXACT_INFRA_READY_ONCE')
        ports=getattr(self.core,'source_task_ports',None)
        checkpoint=getattr(self.core,'smoke_checkpoint_ports',{}).get(t)
        tester=getattr(self.core,'native_tester_initial',{}).get(t)
        from smoke_bootstrap_task_ports import NewRootSourceTaskPorts
        from native_dynamic_checkpoint import DynamicCheckpointPorts
        from smoke_bootstrap_task_tester import NativeTesterInitialRelease
        need(type(ports) is NewRootSourceTaskPorts and ports.core is self.core and
             ports.rows[t]['state']=='SOURCE_TASK_CHANNEL_READY' and
             type(checkpoint) is DynamicCheckpointPorts and checkpoint.core is self.core and checkpoint.t==t and
             type(tester) is NativeTesterInitialRelease and tester.core is self.core and tester.t==t and
             tester.state=='ORIGINAL_TESTER_CYCLE0_PUBLISHED_MODELS_HELD',
             'DYNTEAM_SOURCE_RELAY_AND_REAL_TESTER_INPUTS_BEFORE_INITIAL_NATIVE_START')
        self._initial(record)
        return self.public(t)

    def _infra_ready(self,t):
        docker=self.core.native_containers.docker
        host=self.core.native_host_environment['trajectories'][t]
        for name in INFRA:
            expected=infra_labels(self.core,t,name);ids=docker.list_scope_ids(expected)
            need(len(ids)<=1,'DYNTEAM_NO_PARALLEL_INFRA_GENERATIONS')
            if not ids:return False
            row=docker.inspect(ids[0])
            labels={k:expected[v] for k,v in {'root':'count14.root','trajectory':'count14.trajectory-sha256',
                'contract':'count14.contract-sha256','role':'count14.role','component':'count14.component'}.items()}
            need(row['labels']==labels and row['image']==host['image_ids'][name] and not row['paused'] and not row['dead'],
                 'DYNTEAM_EXACT_PINNED_INFRA_SCOPE_IMAGE')
            if name in ('bootstrap','gitea-admin-init'):
                if row['running'] or row['restarting']:return False
                need(row['exit_code']==0 and row['pid']==0,'DYNTEAM_ORIGINAL_BOOTSTRAP_NOT_SUCCESSFULLY_COMPLETE')
            elif not row['running'] or row['pid']<=0 or row['restarting']:return False
            elif not self.core.qualification_only:
                # Bind genuine init identity during original zero-model infra
                # launch, not first observation at a later paid checkpoint.
                from native_peer_registry import process_birth
                birth=process_birth(row['pid']);key=t,name
                value=dict(cid=row['id'],image_id=row['image'],init_birth=birth)
                previous=self.infra_birth_records.get(key)
                need(previous is None or previous==value,'DYNTEAM_INFRA_ORIGINAL_LAUNCH_IDENTITY_CHANGED')
                if previous is None:
                    with self.core.ledger.mutex:
                        need(t in self.core.gate.startup_held and self.core.ledger.db.execute(
                            'SELECT COUNT(*) FROM requests WHERE trajectory=?',(t,)).fetchone()[0]==0,
                            'DYNTEAM_INFRA_BIND_ONLY_ORIGINAL_UNPAID_STARTUP')
                    self.infra_birth_records[key]=value
        return True

    def step(self,t):
        self._held();record=self.records[t]
        if record['failure_type'] is not None:return self.public(t)
        try:
            self.core.poll_native_control_once() # same owner control, not a second model dispatcher
            child=record['child']
            if child is not None:
                code=child.poll()
                if code is None:
                    if time.monotonic_ns()-record['started_ns']>=120*10**9 and not record['warning120']:
                        record['warning120']=True
                        self._receipt(record,'CONTROL120_RETAIN_SAME_CHILD_NO_SIGNAL',own_control_pid=child.pid)
                    return self.public(t)
                self._receipt(record,'CONTROL_EXIT',exit_code=code,own_control_pid=child.pid)
                need(code==0,'DYNTEAM_NATIVE_BOOTSTRAP_CONTROL_FAILED_RETAIN_NO_RETRY')
                record['child']=None
                if record['phase']=='INFRA_PENDING':record['phase']='INFRA_COMMAND_RETURNED_WAIT_BOOTSTRAP_READY'
                else:
                    record['phase']='INITIAL_UP_COMMANDS_RETURNED_MODEL_HELD'
                    self._receipt(record,'INITIAL_COMMANDS_RETURNED_NEEDS_ACTUAL_NATIVE_TASK_READY')
            if record['phase']=='INFRA_COMMAND_RETURNED_WAIT_BOOTSTRAP_READY':
                if self._infra_ready(t):
                    record['phase']='INFRA_READY_AWAIT_SOURCE_PUBLICATION'
                    self._receipt(record,'ACTUAL_INFRA_READY_SOURCE_PUBLICATION_REQUIRED_BEFORE_INITIAL')
                return self.public(t)
            # Only actual initial/admitted-role IDs are imported into trusted
            # boot plans. Missing peers remain pending, never fake PREPARED.
            if record['phase']=='INITIAL_UP_COMMANDS_RETURNED_MODEL_HELD':
                record['discovery']=self.core.native_containers.sync_boot_plans(t,list(self.core.rows[t]['initial_active_roles']))
            return self.public(t)
        except Exception as error:
            record['failure_type']=type(error).__name__
            self._receipt(record,'FAILED_RETAINED',exception_type=record['failure_type'],
                exception_message=str(error),infra_traceback=traceback.format_exc())
            return self.public(t)

    def public(self,t):
        r=self.records[t]
        return dict(phase=r['phase'],control_live=r['child'] is not None and r['child'].poll() is None,
            failure_type=r['failure_type'],discovery=r.get('discovery'),model_gates_held=True,
            scientific_PREPARED=False,scientific_ACTIVATED=False)
