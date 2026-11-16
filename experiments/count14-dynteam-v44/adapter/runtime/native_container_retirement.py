"""Same-owner exact retired native containers: normal stop, stopped-only rm.

No models, log bodies, force signal, image/volume/root deletion, financial
rewrite or dispatcher. A step never waits on a subprocess; each exact Popen
is retained across observation timeouts. All Docker/receipt I/O is outside
the original science/ledger mutex and framework fence locks.
"""
from dataclasses import dataclass
from pathlib import Path
import json
import os
import stat
import threading
import time

from common import need,digest
from native_docker_scope import ScopedDocker,scope_labels,sha64
from native_peer_registry import ProcessBirth,process_birth


def alive(birth):
    try:return process_birth(birth.pid)==birth
    except (FileNotFoundError,ProcessLookupError):return False


@dataclass(frozen=True)
class ContainerBinding:
    trajectory:str
    role:str
    component:str
    cid:str
    image_id:str
    init_birth:ProcessBirth
    peer_birth:ProcessBirth


@dataclass(frozen=True)
class ContainerBootPlan:
    trajectory:str
    role:str
    component:str
    cid:str
    image_id:str
    init_birth:ProcessBirth


def descendant_in_container(init,peer):
    """Only exact sender's bounded parent chain; no argv/stacks/global scan."""
    current=peer;seen=set()
    for _ in range(16):
        if current==init:return alive(init)
        if current.pid in seen:return False
        seen.add(current.pid)
        if (current.pid_namespace,current.mount_namespace,current.network_namespace)!=(
                init.pid_namespace,init.mount_namespace,init.network_namespace):return False
        raw=Path('/proc',str(current.pid),'stat').read_bytes()
        parent=int(raw[raw.rfind(b')')+2:].split()[1])
        if parent<=1:return False
        current=process_birth(parent)
    return False


class NativeContainerRegistry:
    def __init__(self,core,docker,*,image_ids=None):
        need(type(docker) is ScopedDocker and docker.route.qualification_only is core.qualification_only,
             'DYNTEAM_ORIGINAL_OWNER_TYPED_DOCKER_REGISTRY')
        self.core,self.docker=core,docker;self.records={};self.retired=[]
        self.boot_plans={};self.bootstrap_lock=threading.Lock();self.bootstrap_busy=set()
        self.bootstrap_failures={}
        self.discovery_lock=threading.Lock()
        need(image_ids is None and core.qualification_only or type(image_ids) is dict and
             set(image_ids)=={'agent','router'} and all(type(v) is str and v.startswith('sha256:') and sha64(v[7:])
             for v in image_ids.values()),'DYNTEAM_NATIVE_FROZEN_AGENT_ROUTER_IMAGE_PINS_REQUIRED')
        self.image_ids=None if image_ids is None else dict(image_ids)

    def sync_boot_plans(self,t,roles):
        """Finite real bootstrap step; discovers only already-admitted roles.

        Original native launch function still starts the containers. This
        imports PUBLIC daemon IDs/PID births before the first peer receipt,
        without eagerly starting rendered/latent workers or racing helpers.
        """
        # Serialize discovery callers without holding the bootstrap, ledger,
        # science, or membership mutex across Docker/proc I/O. The original
        # REGISTER_ONCE guard remains strict; a later caller sees the actual
        # completed plan rather than racing a second registration after I/O.
        with self.discovery_lock:
            need(t in self.core.rows and self.image_ids is not None and type(roles) in (list,tuple) and
                 set(roles)<=set(self.core.rows[t]['roles']),'DYNTEAM_PINNED_NATIVE_BOOTSTRAP_ROLE_GRID')
            counts=dict(plans_registered=0,pending_components=0,existing_components=0)
            for role in roles:
                for component in ('agent','router'):
                    key=t,role,component
                    with self.bootstrap_lock:existing=key in self.records or key in self.boot_plans
                    if existing:counts['existing_components']+=1;continue
                    launch=self.core.pending_native_launches.get((t,role))
                    if launch is None:
                        with self.core.ledger.mutex:
                            allowed=(role in self.core.rows[t]['initial_active_roles'] and t in self.core.gate.startup_held and
                                self.core.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=?',(t,)).fetchone()[0]==0)
                    else:allowed=self.core.membership_fences[t].owns(launch.get('lease'),role)
                    need(allowed and (t,role) in self.core.roles.held,
                         'DYNTEAM_BOOTSTRAP_CANNOT_ADMIT_UNPLANNED_OR_LATENT_SCIENTIFIC_AGENT')
                    ids=self.docker.list_scope_ids(scope_labels(self.core.contract,self.core.rows[t],role,component))
                    need(len(ids)<=1,'DYNTEAM_NATIVE_NO_PARALLEL_CONTAINER_GENERATIONS')
                    if not ids:counts['pending_components']+=1;continue
                    snapshot=self.docker.inspect(ids[0])
                    if not snapshot['running'] or snapshot['pid']<=0:
                        counts['pending_components']+=1;continue
                    need(snapshot['image']==self.image_ids[component],'DYNTEAM_NATIVE_BOOTSTRAP_PINNED_IMAGE_CHANGED')
                    plan=ContainerBootPlan(t,role,component,ids[0],self.image_ids[component],process_birth(snapshot['pid']))
                    self.register_boot_plan_from_launcher(plan);counts['plans_registered']+=1
            return counts

    def register_boot_plan_from_launcher(self,plan):
        need(type(plan) is ContainerBootPlan and sha64(plan.cid) and plan.image_id.startswith('sha256:') and
             sha64(plan.image_id[7:]) and type(plan.init_birth) is ProcessBirth,
             'DYNTEAM_TYPED_NATIVE_CONTAINER_BOOT_PLAN')
        key=plan.trajectory,plan.role,plan.component
        need((plan.trajectory,plan.role) in self.core.roles.held,
             'DYNTEAM_PLAN_MUST_PRECEDE_NATIVE_MODEL_ROLE_RELEASE')
        need(self.image_ids is None or plan.image_id==self.image_ids[plan.component],
             'DYNTEAM_BOOT_PLAN_MATCHES_FROZEN_NATIVE_IMAGE')
        provisional=ContainerBinding(plan.trajectory,plan.role,plan.component,plan.cid,plan.image_id,
                                     plan.init_birth,plan.init_birth)
        self.validate(provisional,self.docker.inspect(plan.cid),running=True)
        with self.bootstrap_lock:
            need(key not in self.records and key not in self.boot_plans and
                 all(p.cid!=plan.cid for p in (*self.boot_plans.values(),*self.records.values())),
                 'DYNTEAM_NATIVE_BOOT_PLAN_REGISTER_ONCE')
            self.boot_plans[key]=plan

    def admit_initial_peer(self,envelope,peercred):
        if envelope.get('source_commit')!='70e2ca54c078597e3314755064d2ef1a83344c8e':return False
        schema=envelope.get('schema')
        if schema=='count14-native-bridge-lifecycle-v1':component,purpose='agent','bridge'
        elif schema in ('count14-dynteam-native-session-ready-v1','count14-native-phase-physical-proof-v1'):
            component,purpose='router','router'
        else:return False # launcher is explicitly registered, never self-bootstrapped
        t,role=envelope.get('trajectory_id'),envelope.get('role_slot');key=t,role,component
        with self.bootstrap_lock:
            plan=self.boot_plans.get(key)
            if plan is None or key in self.bootstrap_busy:return False
            self.bootstrap_busy.add(key)
        try:
            # Every /proc/Docker read is OUTSIDE this and all scientific locks.
            peer=process_birth(peercred[0])
            expected_uid=plan.init_birth.uid if self.core.qualification_only else (0 if component=='agent' else 10000)
            need(peercred==(peer.pid,peer.uid,peer.gid) and peer.uid==expected_uid and
                 descendant_in_container(plan.init_birth,peer),
                 'DYNTEAM_NATIVE_INITIAL_PEER_EXACT_KERNEL_DESCENDANT_UID')
            binding=ContainerBinding(t,role,component,plan.cid,plan.image_id,plan.init_birth,peer)
            self.validate(binding,self.docker.inspect(plan.cid),running=True)
            self.core.peers.register_from_launcher(t,role,peer,expected_birth=peer,purpose=purpose)
            with self.bootstrap_lock:
                need(self.boot_plans.get(key)==plan and key not in self.records,
                     'DYNTEAM_NATIVE_BOOT_PLAN_NOT_REPLACED_DURING_INITIAL_RECEIPT')
                self.records[key]=binding;del self.boot_plans[key]
            return self.core.peers.validate(envelope,peercred)
        except Exception as error:
            with self.bootstrap_lock:self.bootstrap_failures[key]=type(error).__name__
            return False
        finally:
            with self.bootstrap_lock:self.bootstrap_busy.discard(key)

    def validate(self,binding,snapshot,*,running):
        need(type(binding) is ContainerBinding and binding.trajectory in self.core.rows,
             'DYNTEAM_NATIVE_CONTAINER_TRUSTED_BINDING')
        row=self.core.rows[binding.trajectory]
        labels=scope_labels(self.core.contract,row,binding.role,binding.component)
        short={'root':'count14.root','trajectory':'count14.trajectory-sha256','contract':'count14.contract-sha256',
               'role':'count14.role','component':'count14.component'}
        need(snapshot['id']==binding.cid and snapshot['image']==binding.image_id and
             snapshot['labels']=={k:labels[v] for k,v in short.items()} and
             snapshot['stop_signal'] in ('','SIGTERM','15') and not snapshot['paused'] and not snapshot['restarting'],
             'DYNTEAM_NATIVE_CONTAINER_SCOPE_IMAGE_OR_SIGNAL_CHANGED')
        root=Path(row['root']);need(root.is_dir() and root.resolve()==root,'DYNTEAM_EXACT_NATIVE_CONTAINER_DATA_ROOT')
        writable=[]
        for mount in snapshot['mounts']:
            need(type(mount) is dict and type(mount.get('RW')) is bool,'DYNTEAM_NATIVE_MOUNT_CONTROL_FIELDS')
            if not mount['RW']:continue
            if mount.get('Type')=='tmpfs':continue
            need(mount.get('Type')=='bind' and type(mount.get('Source')) is str,
                 'DYNTEAM_NATIVE_NO_SHARED_WRITABLE_VOLUME')
            path=Path(mount['Source'])
            need(path.is_absolute() and path.resolve()==path and path.is_relative_to(root),
                 'DYNTEAM_NATIVE_WRITABLE_MOUNTS_ONLY_EXACT_EXPERIMENT_ROOT')
            writable.append(path)
        need(writable,'DYNTEAM_NATIVE_CONTAINER_MUST_HAVE_OWN_ROOT_BIND')
        if running:
            need(snapshot['running'] and not snapshot['dead'] and snapshot['pid']==binding.init_birth.pid and
                 alive(binding.init_birth),'DYNTEAM_NATIVE_EXACT_LIVE_CONTAINER_PID_START_BOOT')
            init=binding.init_birth;peer=binding.peer_birth
            need((init.pid_namespace,init.mount_namespace,init.network_namespace)==
                 (peer.pid_namespace,peer.mount_namespace,peer.network_namespace),
                 'DYNTEAM_NATIVE_PEER_MUST_BE_IN_EXACT_CONTAINER_NAMESPACES')
        else:
            need(not snapshot['running'] and snapshot['pid']==0 and not alive(binding.init_birth) and
                 not alive(binding.peer_birth),'DYNTEAM_NATIVE_STOPPED_AND_ORIGINAL_PROCESSES_ABSENT')
        return True

    def register_from_launcher(self,binding):
        need(type(binding) is ContainerBinding and sha64(binding.cid) and
             binding.image_id.startswith('sha256:') and sha64(binding.image_id[7:]) and
             type(binding.init_birth) is ProcessBirth and type(binding.peer_birth) is ProcessBirth,
             'DYNTEAM_FULL_NATIVE_CONTAINER_AND_IMAGE_ID')
        need(self.image_ids is None or binding.image_id==self.image_ids[binding.component],
             'DYNTEAM_NATIVE_REGISTERED_CONTAINER_IMAGE_PIN')
        key=binding.trajectory,binding.role,binding.component
        need(key not in self.records and all(b.cid!=binding.cid for b in self.records.values()),
             'DYNTEAM_NATIVE_CONTAINER_REGISTER_ONCE_NO_PARALLEL_REPLACEMENT')
        purpose='bridge' if binding.component=='agent' else 'router'
        need(self.core.peers._peers.get((binding.trajectory,binding.role,purpose))==binding.peer_birth and
             alive(binding.peer_birth),'DYNTEAM_ORIGINAL_REGISTERED_NATIVE_PEER_BINDING')
        self.validate(binding,self.docker.inspect(binding.cid),running=True)
        self.records[key]=binding

    def new_job(self,t,role,operation_id,cids,home):
        selected=[self.records.get((t,role,k)) for k in ('router','agent')]
        need(all(type(b) is ContainerBinding for b in selected) and type(cids) is list and len(cids)==2 and
             len(set(cids))==2 and set(cids)=={b.cid for b in selected},
             'DYNTEAM_RETIRE_EXACT_TWO_ORIGINAL_REGISTERED_CONTAINERS')
        return RetirementJob(self,t,role,operation_id,selected,home)


class RetirementJob:
    def __init__(self,registry,t,role,operation_id,bindings,home):
        self.registry,self.core,self.docker=registry,registry.core,registry.docker
        self.t,self.role,self.operation_id=t,role,operation_id
        self.bindings=tuple(bindings);self.index=0;self.phase='CHECK';self.child=None
        self.started_ns=None;self.failure_type=None;self.observation_deadline_exceeded=False
        self.home=Path(home)
        need(self.home.parent.resolve()==self.home.parent and not self.home.exists(),
             'DYNTEAM_NEW_EXACT_RETIRE_RECEIPT_DIRECTORY')
        self.home.mkdir(mode=0o700);self.sequence=0
        self._eligible()
        self._receipt('REGISTERED')

    def _eligible(self):
        key=self.t,self.role;core=self.core
        launch=core.pending_native_launches.get(key);cli=core.bridge_owner.clis.get(key)
        need(launch is not None and launch['reuse'] and launch['lease'].operation_id==self.operation_id and
             core.membership_fences[self.t].owns(launch['lease'],self.role) and key in core.roles.held and
             cli is not None and cli['archived'] and key not in core.bridge_owner.logical and not alive(cli['birth']),
             'DYNTEAM_RETIRE_ORIGINAL_ARCHIVED_ENDED_ROLE_AND_ACTIVE_REUSE_LEASE')
        proof=core.native_physical_projection(self.t,self.role)
        need(proof=={'models_clear':True,'tools_clear':True},'DYNTEAM_RETIRE_KEEP_UNPROVEN_PAID_MODEL_TOOL_CUSTODY')

    def _receipt(self,kind,**extra):
        self.sequence+=1
        value=dict(schema='count14-native-exact-retirement-public-v1',sequence=self.sequence,
            trajectory_id=self.t,role_slot=self.role,operation_id=self.operation_id,kind=kind,
            phase=self.phase,at_mono_ns=time.monotonic_ns(),models_replayed=0,fees_changed=0,**extra)
        path=self.home/(str(self.sequence).zfill(4)+'-'+kind+'.json')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        try:
            with os.fdopen(fd,'wb',closefd=False) as out:
                out.write((json.dumps(value,sort_keys=True)+'\n').encode());out.flush();os.fsync(fd)
        finally:os.close(fd)

    def _start(self,action,binding):
        self._eligible()
        self._receipt('ACTION_INTENT',action=action,container_id=binding.cid,
            init_pid=binding.init_birth.pid,init_start_ticks=binding.init_birth.start_ticks,
            init_boot_id=binding.init_birth.boot_id)
        self.child=self.docker.mutate_once(action,binding.cid)
        self.started_ns=time.monotonic_ns()
        self._receipt('ACTION_STARTED',action=action,container_id=binding.cid,own_control_pid=self.child.pid)

    def step(self):
        if self.phase=='DONE':return 'DONE'
        if self.failure_type is not None:return 'RETAINED'
        try:return self._step()
        except Exception as error:
            self.failure_type=type(error).__name__
            self._receipt('FAILED_RETAINED',exception_type=self.failure_type)
            return 'RETAINED'

    def _step(self):
        # Called by original owner's finite metadata job, never under any
        # scientific lock. No subprocess wait, cancellation or repeated Popen.
        self._eligible();binding=self.bindings[self.index]
        if self.child is not None:
            code=self.child.poll()
            if code is None:
                if time.monotonic_ns()-self.started_ns>=120*10**9 and not self.observation_deadline_exceeded:
                    self.observation_deadline_exceeded=True
                    self._receipt('CONTROL120_OBSERVATION_RETAIN_SAME_CHILD',own_control_pid=self.child.pid,
                        physical_terminal_NOT_claimed=True)
                return 'RETAINED'
            self._receipt('ACTION_EXIT',exit_code=code,own_control_pid=self.child.pid)
            need(code==0,'DYNTEAM_NATIVE_CONTROL_CHILD_FAILED_RETAIN_NO_RETRY')
            self.child=None
            self.phase={'UPDATE_PENDING':'STOP','STOP_PENDING':'REMOVE','REMOVE_PENDING':'REMOVED'}[self.phase]
        if self.phase=='CHECK':
            snapshot=self.docker.inspect(binding.cid)
            if not snapshot['running']:
                self.registry.validate(binding,snapshot,running=False)
                self.phase='REMOVE'
                self._receipt('ALREADY_STOPPED_VERIFIED_NO_NEW_TERM',container_id=binding.cid)
                return 'RETAINED'
            self.registry.validate(binding,snapshot,running=True)
            # Per-container only. Prevent restart-policy races before stopping;
            # fresh PID/start/boot is checked again after this normal update.
            self.phase='UPDATE_PENDING';self._start('DISABLE_RESTART',binding);return 'RETAINED'
        if self.phase=='STOP':
            snapshot=self.docker.inspect(binding.cid);self.registry.validate(binding,snapshot,running=True)
            need(snapshot['restart_policy']=='no','DYNTEAM_NATIVE_RETIRING_CONTAINER_RESTART_DISABLED')
            self.phase='STOP_PENDING';self._start('NORMAL_STOP',binding);return 'RETAINED'
        if self.phase=='REMOVE':
            snapshot=self.docker.inspect(binding.cid);self.registry.validate(binding,snapshot,running=False)
            self.phase='REMOVE_PENDING';self._start('REMOVE_STOPPED',binding);return 'RETAINED'
        if self.phase=='REMOVED':
            need(not self.docker.exists(binding.cid),'DYNTEAM_NATIVE_REMOVE_NOT_PHYSICALLY_CONFIRMED')
            purpose='router' if binding.component=='router' else 'bridge'
            self.core.peers.retire_after_exit(self.t,self.role,binding.peer_birth,
                original_physical_clear=True,purpose=purpose)
            del self.registry.records[self.t,self.role,binding.component]
            self.registry.retired.append(binding)
            self._receipt('EXACT_CONTAINER_REMOVED',container_id=binding.cid)
            self.index+=1;self.phase='CHECK'
            if self.index==len(self.bindings):
                self.phase='DONE';self._receipt('DONE',containers=2,normal_TERM_only=True,
                    experiment_root_or_checkpoint_or_archive_or_ledger_deleted=False)
                return 'DONE'
        return 'RETAINED'
