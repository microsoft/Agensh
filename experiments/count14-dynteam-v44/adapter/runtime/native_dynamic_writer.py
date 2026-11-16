"""Dynamic native topology -> ORIGINAL whole-domain writer/capture primitives.

No fabricated worker/MCP processes: the immutable per-cut inventory is all real
agent/router/backend containers launched in this exact new scope. Docker init
identities and mount roots are rechecked before and throughout original cgroup
freeze. Membership effects close first; accepted models drain naturally. This
module neither starts a model nor supplies a FINAL executor/activation shortcut.
"""
from contextlib import ExitStack
from pathlib import Path
from types import FunctionType, MethodType
import copy
import os
import json
import subprocess

from common import need, digest, wire, private_dir, publish
from bridge import process_identity
from native_docker_scope import scope_labels
from native_host_environment import INFRA, infra_labels
from native_writer_fence import NativeWriterFence, CgroupV2Domain, process_cgroup_v2
from native_whole_team import NativeWholeTeamRegistration, root_identity
from native_service_cut import NativeServiceCut


def _function(function, **bindings):
    result=FunctionType(function.__code__,dict(function.__globals__,**bindings),
        function.__name__,function.__defaults__,function.__closure__)
    result.__kwdefaults__=function.__kwdefaults__
    return result


def _no_legacy_sdk(owner):
    # Every actual writer, including the native CLI descendants, is represented
    # by its real container init below whole_team.current(). No pretend SDKs.
    need(type(owner) is DynamicCutWriter and owner.core.ledger is owner.ledger,
         'DYNTEAM_WRITER_EXACT_DYNAMIC_NATIVE_OWNER')
    owner.current_inventory()
    return {}


def _native_services_current(registration):
    # Original registration.current, except the old nonempty-roots condition:
    # an actually stateless proxy has no persistent writable mounts to archive.
    # The complete exact Docker census independently proves that empty set.
    from native_whole_team import NativeWholeTeamRegistration
    import ast, inspect, textwrap
    source=textwrap.dedent(inspect.getsource(NativeWholeTeamRegistration.current))
    tree=ast.parse(source);found=0
    class EmptyNativeMounts(ast.NodeTransformer):
        def visit_BoolOp(self,node):
            nonlocal found
            wanted=ast.parse("row['roots']",mode='eval').body
            if isinstance(node.op,ast.And) and any(ast.dump(v)==ast.dump(wanted) for v in node.values):
                kept=[v for v in node.values if ast.dump(v)!=ast.dump(wanted)]
                if len(kept)==len(node.values)-1:node.values=kept;found+=1
            return self.generic_visit(node)
    tree=EmptyNativeMounts().visit(tree)
    need(found==1,'DYNTEAM_WRITER_ONE_STATELESS_ROOTS_SCOPE_SITE')
    namespace={};exec(compile(ast.fix_missing_locations(tree),__file__+':native-mounts','exec'),
                      NativeWholeTeamRegistration.current.__globals__,namespace)
    registration.owner.current_inventory()
    return namespace['current'](registration)


class DynamicCutWriter:
    """One immutable per-cut inventory, never reuse stale domains after growth.

    The original NativeWriterFence methods operate on this explicit topology
    facade. Only their legacy participant lookup is privately rebound; global
    classes/functions, SQL, drain checks and kernel freeze protocol stay intact.
    """
    def __init__(self,core,trajectory):
        need(trajectory in core.rows and hasattr(core,'native_containers') and
             hasattr(core,'native_layout') and hasattr(core,'membership_fences'),
             'DYNTEAM_WRITER_ONLY_BOUND_ORIGINAL_CORE')
        self.core,self.ledger,self.t=core,core.ledger,trajectory
        self.row=copy.deepcopy(core.rows[trajectory]);self.contract_sha=digest(core.contract)
        self.roles=sorted(self.row['roles']);self._stage_registry=()
        self.started=True;self.closed=False;self.bridge_backup=None;self.writer_fence=None
        self.owner_identity=process_identity(os.getpid())
        self.membership=core.membership_fences[trajectory]
        with self.ledger.mutex:
            f=self.ledger.frontier(trajectory)
            need(f['state']=='DRAINING' and not self.ledger.admission_fault(trajectory),
                 'DYNTEAM_WRITER_ORIGINAL_DRAINING_REQUIRED')
            generation=f['generation']
        epochs=getattr(core,'native_sdk_startup_epochs',None)
        need(epochs is None or not epochs.reconnect.pending_trajectory(trajectory),
             'DYNTEAM_WRITER_NO_CAPTURE_MID_NORMAL_SESSION_RECONNECT')
        need(not core.bridge_owner.prepark_pending(trajectory),
             'DYNTEAM_WRITER_WAIT_NATIVE_END_TRANSITION')
        need(self.membership.public_counts()['pending_native_effects']==0,
             'DYNTEAM_WRITER_WAIT_EXISTING_MEMBERSHIP_BEFORE_CUT')
        self.membership.request_cut(generation)
        need(self.membership.public_counts()['pending_native_effects']==0,
             'DYNTEAM_WRITER_NATIVE_MEMBERSHIP_MUST_NATURALLY_DRAIN')
        with self.ledger.mutex:
            f=self.ledger.frontier(trajectory)
            need(f['unresolved']==f['reserved']==f['active_operations']==0,
                 'DYNTEAM_WRITER_ACCEPTED_WORK_MUST_NATURALLY_DRAIN')
        http=core.servers[trajectory]
        need(http.trajectory_park_ready(trajectory)['safe_to_park_writers'] and
             not http.lifecycle_storage_unknown,
             'DYNTEAM_WRITER_ORIGINAL_PHYSICAL_HTTP_TAIL_MUST_DRAIN_BEFORE_FREEZE')
        self.generation=generation
        self.containers=self._inventory()
        need(self.containers,'DYNTEAM_WRITER_NONEMPTY_ACTUAL_CONTAINER_INVENTORY')
        self.inventory_sha=digest(self.containers)
        layout=core.native_layout.current(trajectory)
        self.role_sources={r:{'workspace':Path(layout['roles'][r]['workspace']),
                              'session':Path(layout['roles'][r]['archive_root'])} for r in self.roles}
        self.gb={'workspace_roots':{r:{'path':str(v['workspace'])} for r,v in self.role_sources.items()}}
        self.root=Path(self.row['root'])/'native-writer-control'
        services={name:{'process':copy.deepcopy(row['process']),
                       'roots':copy.deepcopy(row['roots'])} for name,row in self.containers.items()}
        need({'gitea','mattermost'} < set(services),
             'DYNTEAM_WRITER_ALL_REAL_BACKENDS_REQUIRED')
        # A fresh per-cut instance is essential: native births can change the
        # inventory between cuts. Do not mutate an old registration/receipt or
        # claim this was the legacy fixed-roster pre-first-model registration.
        whole=NativeWholeTeamRegistration.__new__(NativeWholeTeamRegistration)
        whole.owner=self;whole.ledger=self.ledger;whole.t=trajectory
        whole.services=services;whole.backends=tuple(sorted(set(services)-{'gitea','mattermost'}))
        whole.inventory_sha=digest(services)
        whole.current=MethodType(_native_services_current,whole);whole.current()
        self.whole_team=whole
        with self.ledger.tx():
            self.ledger.event(trajectory,'DYNTEAM_NATIVE_CUT_EXECUTION_INVENTORY_BOUND',
                {'generation':generation,'inventory_sha256':self.inventory_sha,
                 'whole_team_inventory_sha256':whole.inventory_sha,
                 'containers':len(services),'registered_roles':len(self.roles),
                 'legacy_fixed_sdk_topology_claimed':False})
        self.domains=tuple(self._domain(name,row) for name,row in sorted(self.containers.items()))
        fence=NativeWriterFence.__new__(NativeWriterFence)
        # __init__ itself calls _coverage: bind the same real-topology lookup
        # BEFORE construction, not after its first strict check.
        fence._coverage=MethodType(_function(NativeWriterFence._coverage,
                                             registered_participants=_no_legacy_sdk),fence)
        init=_function(NativeWriterFence.__init__,registered_participants=_no_legacy_sdk)
        init(fence,self,self.domains,expected_domains_sha256=digest(sorted(d.binding_sha for d in self.domains)),
             whole_team=whole)
        fence._coverage=MethodType(_function(NativeWriterFence._coverage,
                                             registered_participants=_no_legacy_sdk),fence)
        self.writer_fence=fence
        self.membership_token=None;self.cut=None

    def _inventory(self):
        core=self.core;docker=core.native_containers.docker
        expected=[]
        for role in self.roles:
            for component in ('agent','router'):
                expected.append(('backend-'+component+'-'+role,scope_labels(core.contract,self.row,role,component),False))
        for name in INFRA:
            expected.append((name if name in ('gitea','mattermost') else 'backend-'+name,
                             infra_labels(core,self.t,name),True))
        # A single exact root+trajectory+contract census avoids one Docker ps
        # subprocess per dormant catalogue slot at EVERY original proof step.
        docker.verify_daemon()
        argv=docker.argv('ps','-aq','--no-trunc')
        for key,value in (('count14.root',self.row['root']),
                          ('count14.trajectory-sha256',digest(self.t)),
                          ('count14.contract-sha256',digest(core.contract))):
            argv+=['--filter','label='+key+'='+value]
        observed=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},cwd='/',timeout=2.5)
        need(observed.returncode==0 and len(observed.stdout)<=32768,
             'DYNTEAM_WRITER_EXACT_EXPERIMENT_CONTAINER_CENSUS')
        ids=observed.stdout.decode('ascii').splitlines()
        need(len(ids)==len(set(ids)) and len(ids)<=len(expected),
             'DYNTEAM_WRITER_BOUNDED_UNIQUE_COMPLETE_CIDS')
        byscope={};result={}
        for cid in ids:
            row=docker.inspect(cid)
            key=(row['labels']['role'],row['labels']['component'])
            need(key not in byscope,'DYNTEAM_WRITER_NO_PARALLEL_CONTAINER_GENERATIONS')
            byscope[key]=row
        consumed=set()
        for name,labels,infrastructure in expected:
            key=(labels['count14.role'],labels['count14.component'])
            row=byscope.get(key)
            if row is None:
                need(not infrastructure,'DYNTEAM_WRITER_ALL_EXPECTED_INFRA_MUST_EXIST')
                continue
            consumed.add(key)
            projection={k:labels[v] for k,v in {'root':'count14.root','trajectory':'count14.trajectory-sha256',
                'contract':'count14.contract-sha256','role':'count14.role','component':'count14.component'}.items()}
            need(row['labels']==projection and not row['restarting'] and not row['dead'],
                 'DYNTEAM_WRITER_EXACT_CONTAINER_SCOPE_STABLE')
            if not row['running']:
                need(row['pid']==0,'DYNTEAM_WRITER_STOPPED_CONTAINER_NO_INIT')
                continue
            need(row['pid']>0 and not row['paused'],'DYNTEAM_WRITER_NOT_PREPAUSED_CONTAINER')
            from native_peer_registry import process_birth
            if infrastructure:
                original_name=name if name in ('gitea','mattermost') else name.removeprefix('backend-')
                launch=core.cold_bootstrap.infra_birth_records.get((self.t,original_name))
                need(launch is not None and (launch['cid'],launch['image_id'],launch['init_birth'])==
                     (row['id'],row['image'],process_birth(row['pid'])),
                     'DYNTEAM_WRITER_INFRA_EXACT_ORIGINAL_ZERO_MODEL_LAUNCH_RECORD')
                launch_binding={'kind':'ORIGINAL_ZERO_MODEL_INFRA_BOOTSTRAP',
                    'control_births':copy.deepcopy(core.cold_bootstrap.records[self.t]['control_births'])}
            else:
                key=self.t,labels['count14.role'],labels['count14.component']
                launch=core.native_containers.records.get(key) or core.native_containers.boot_plans.get(key)
                need(launch is not None and (launch.cid,launch.image_id,launch.init_birth)==
                     (row['id'],row['image'],process_birth(row['pid'])),
                     'DYNTEAM_WRITER_NATIVE_EXACT_ORIGINAL_ROLE_LAUNCH_REGISTRY')
                launch_binding={'kind':'ORIGINAL_NATIVE_ROLE_BOOT_PLAN_OR_PEER_REGISTRY'}
            process=process_identity(row['pid'])
            roots={}
            for index,mount in enumerate(row['mounts']):
                need(type(mount) is dict and type(mount.get('RW')) is bool,
                     'DYNTEAM_WRITER_DOCKER_MOUNT_METADATA')
                if not mount['RW']:continue
                source=Path(mount['Source'])
                need(source.is_relative_to(Path(self.row['root'])) and source.resolve()==source,
                     'DYNTEAM_WRITER_PERSISTENT_WRITES_ONLY_EXACT_NEW_ROOT')
                # All writable bind/volume roots must be captured. A writable
                # file or external mount is not silently discarded.
                roots['mount-'+str(index)]=root_identity(source)
            result[name]={'cid':row['id'],'image':row['image'],'process':process,'roots':roots,
                          'domain':str(process_cgroup_v2(process)),
                          'labels':copy.deepcopy(row['labels']),'launch_binding':launch_binding}
        need(consumed==set(byscope),'DYNTEAM_WRITER_NO_UNREGISTERED_EXPERIMENT_CONTAINERS')
        return result

    def current_inventory(self):
        """Original fence lock-safe lookup: NO Docker/subprocess/SQL/wait.

        Original _coverage can run under ledger.tx. Full daemon census belongs
        at the outer phase boundary; original whole.current separately verifies
        every exact live process/root and original domains verify containment.
        """
        need(process_identity(os.getpid())==self.owner_identity and
             digest(self.core.contract)==self.contract_sha and self.core.rows[self.t]==self.row and
             digest(self.containers)==self.inventory_sha,
             'DYNTEAM_WRITER_SAME_OWNER_CONTRACT_AND_ROW')
        return self.containers

    def refresh_inventory(self):
        """Fresh complete Docker census, strictly OUTSIDE scientific locks."""
        need(not self.ledger.mutex._is_owned(),
             'DYNTEAM_WRITER_DAEMON_CENSUS_FORBIDDEN_UNDER_LEDGER_LOCK')
        self.current_inventory()
        need(self._inventory()==self.containers,
             'DYNTEAM_WRITER_CONTAINER_INIT_MOUNT_OR_GENERATION_CHANGED')
        return self.containers

    def _domain(self,name,row):
        directory=Path('/sys/fs/cgroup')/row['domain'].lstrip('/')
        s=directory.stat()
        receipt={'schema':'count14-native-docker-execution-domain-v1',
            'contract_sha256':self.contract_sha,'trajectory':self.t,
            'daemon_id':self.core.native_containers.docker.route.daemon_id,
            'container':name, 'container_binding':row,
            'provenance':'ORIGINAL_REGISTERED_DOCKER_LAUNCH_AND_RUNTIME_CGROUP_CONTRACT',
            'pre_exec_assignment_directly_observed_by_this_checkpoint':False}
        reference=self.core.cas.store_bytes(wire(receipt))
        binding={'schema':'agensh-native-owned-writer-cgroup-v1','relative':row['domain'],
            'device':s.st_dev,'inode':s.st_ino,'owner_uid':s.st_uid,
            'launch_receipt_sha256':reference['sha256']}
        return CgroupV2Domain(directory,launch_receipt_sha256=reference['sha256'],
                              expected_binding_sha256=digest(binding))

    def request_park(self,graph):
        need(self.cut is None,'DYNTEAM_WRITER_ONE_CUT_NO_REPLAY')
        self.refresh_inventory()
        self.cut=NativeServiceCut(self.ledger,self.core.cas,self.t,graph,digest(graph),writer_owner=self)
        return self.writer_fence.request_park(self.cut)

    def poll_park(self):
        self.refresh_inventory()
        parked=self.writer_fence.poll_park()
        if not parked:return False
        # tools_quiescent means all writers are physically FROZEN in this
        # whole-domain protocol, not an assertion that shell tools completed.
        token=self.membership.ready(original_models_quiescent=True,original_tools_quiescent=True)
        need(token is not None,'DYNTEAM_WRITER_MEMBERSHIP_EFFECT_DURING_FREEZE')
        self.membership_token=token
        return True

    def capture(self,*,scope,pins,parent=None):
        need(self.membership_token is not None and self.writer_fence.state=='PARKED',
             'DYNTEAM_WRITER_ACTUAL_ALL_PARKED_BEFORE_CAPTURE')
        self.refresh_inventory()
        control=scope.seal_writer_evidence(self.core,self.writer_fence,
            roles=self.role_sources,membership_token=self.membership_token)
        reference=self.cut.capture(roles=self.role_sources,
            pins={**pins,'native_writer_fence':self.writer_fence.receipt['sha256'],
                  'native_writer_control':control['sha256']},parent=parent)
        self.membership.note_original_snapshot(self.membership_token,
            original_snapshot_sha256=reference['sha256'])
        self.refresh_inventory()
        self.reference=reference
        return reference

    def request_same_live_resume(self):
        """Native dynamic clients bind each HTTP request to current ledger gen.

        No legacy MCP identity exists to advance. Verify original committed CAS
        first, then original gate.resume_next, then thaw exactly the same domains.
        Last budget point has no successor and refuses before any thaw.
        """
        need(hasattr(self,'reference') and self.writer_fence.state=='PARKED',
             'DYNTEAM_WRITER_RELEASE_ONLY_AFTER_ORIGINAL_CAPTURE')
        self.refresh_inventory()
        self.core.cas.verify_snapshot(self.reference,expected=self.ledger.frontier(self.t))
        self.writer_fence.verify_capture(self.cut,self.role_sources)
        generation=self.core.gate.resume_next(self.t,
            verified_snapshot_sha256=self.reference['sha256'])
        from native_checkpoint_clock_rearm import rearm_before_native_thaw
        rearm_before_native_thaw(self,final_retirement=False)
        self.writer_fence.state='RELEASE_REQUESTED'
        with self.ledger.tx():self.ledger.event(self.t,'DYNTEAM_NATIVE_SAME_LIVE_RELEASE_REQUESTED',
            {'snapshot_sha256':self.reference['sha256'],'original_generation':self.generation})
        for domain in self.domains:domain.request(False)
        return generation

    def poll_same_live_resume(self):
        self.refresh_inventory()
        if not self.writer_fence.poll_release():return False
        f=self.ledger.frontier(self.t)
        self.membership.after_original_resume(previous_snapshot_sha256=self.reference['sha256'],
                                             new_ledger_generation=f['generation'])
        return True
