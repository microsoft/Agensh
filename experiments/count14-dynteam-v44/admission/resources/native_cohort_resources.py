"""New-cohort instance resource admission; no financial or science changes.

Original v2 own-ledger/health/memory/route/storage predicates are copied as
identical AST nodes, NOT reimplemented with weaker thresholds. Historical
two-owner allocation checks are replaced by this six-trajectory contract's
trusted fixed outside allocation bound and a SAME-ledger atomic admission.
SYSTEM reserves2; SEARCH remains78/13pertrack, AUX<=16, FINAL<=12. Retained
outside UNKNOWN consumes the outside bound; no forgiveness or replay.

Only refresh() reads PUBLIC control metadata. It must run OUTSIDE science
locks. Original reserve/settle paths use immutable cached booleans/TTL only;
no HTTP/filesystem/wait while holding the original ledger RLock. This is not
an observer, probe producer, scientific dispatcher or complete activation.
"""
from dataclasses import dataclass
from pathlib import Path,PurePosixPath
from types import MethodType
import ast
import hashlib
import json
import inspect
import os
import stat
import time
import textwrap

from common import need,digest,Refused
from native_peer_registry import process_birth
GIB=1024**3


def original_mem_available():
    # Keep pure predicate import independent of the scientific m7/ACP graph.
    from native_cold_bootstrap import mem_available
    return mem_available()

ORIGINAL_SHA='349e003f6be40ac19e80c6e639915790e96ff39c7b4c98ae2d65582cb63d3293'
ORIGINAL_AUX_ACQUIRE_SHA='55f8ff04eee537f6bfe7d53d73ac8230df26770d7473e640037bc6ba11026272'
SEARCH_HOST='unix:///mnt/ptb-scratch/cg-count14-search-block456-20261031/docker/docker.sock'
SEARCH_DATA_ROOT='/mnt/ptb-scratch/cg-count14-search-block456-20261031/docker/data'
EVAL_HOST='unix:///mnt/ptb-scratch2/count14-eval-docker-20261030/docker.sock'
SYSTEM_RESERVED=2
NATIVE_PAIR_FORECAST=72*GIB # original native generator: agent64g + router8g


@dataclass(frozen=True)
class CohortAllocation:
    inventory_sha256:str
    other_maximum_FP8_inflight:int

    def checked(self):
        need(type(self.inventory_sha256) is str and len(self.inventory_sha256)==64 and
             all(c in '0123456789abcdef' for c in self.inventory_sha256) and
             type(self.other_maximum_FP8_inflight) is int and 0<=self.other_maximum_FP8_inflight<=94,
             'DYNTEAM_TRUSTED_COMPLETE_OUTSIDE_ALLOCATION_BOUND')
        return self


PREACTIVATE_STORAGE='PREACTIVATE_INCLUDING_ACTIVATE'
RUNTIME_STORAGE='RUNTIME_AFTER_SUCCESSFUL_ACTIVATE'


def storage_lifecycle_phase(core):
    qualified=core.scientific_activation_qualified
    need(type(qualified)is bool,'DYNTEAM_STORAGE_REAL_ACTIVATION_LIFECYCLE_BOOL')
    return RUNTIME_STORAGE if qualified else PREACTIVATE_STORAGE


def validate_storage_retirement_equations(storage):
    from orphan_storage_retirement_reader import MANIFEST_PIN,EXPECTED_ORIGINAL_BYTES,EXPECTED_RECORD_COUNT
    for disk in storage.values():
        proof=disk.get('orphan_storage_retirements')
        need(type(proof)is dict and proof.get('manifest_sha256')==MANIFEST_PIN and
             all(type(proof.get(k))is int and proof[k]>=0 for k in
                 ('raw_original_promised_bytes','retired_orphan_bytes','retired_orphan_records','effective_promised_bytes')) and
             proof['raw_original_promised_bytes']==proof['effective_promised_bytes']+proof['retired_orphan_bytes'] and
             proof['effective_promised_bytes']==disk['existing_reserved_bytes'] and
             proof['retired_orphan_bytes']<=EXPECTED_ORIGINAL_BYTES and proof['retired_orphan_records']<=EXPECTED_RECORD_COUNT and
             proof.get('original_RESERVED_records_unchanged')is True,
             'DYNTEAM_STORAGE_ORPHAN_ORIGINAL_EQUALS_EFFECTIVE_PLUS_AUTHORIZED_RETIRED')


def compiled_original_validator(root):
    path=Path(__file__).resolve().parents[1]/'original-v2-resource-policy-v1/seed46_resources.py'
    raw=path.read_bytes()
    need(path.resolve()==path and not path.is_symlink() and hashlib.sha256(raw).hexdigest()==ORIGINAL_SHA,
         'DYNTEAM_ORIGINAL_RESOURCE_PREDICATES_PIN')
    tree=ast.parse(raw);original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate')
    def assignment(n,name):
        return isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id==name for x in n.targets)
    own=next(i for i,n in enumerate(original.body) if assignment(n,'own'))
    root_guard=next(i for i,n in enumerate(original.body) if isinstance(n,ast.Expr) and
        isinstance(n.value,ast.Call) and any(isinstance(x,ast.Constant) and x.value=='SEED46_RESOURCE_EXACT_NEW_ROOT'
                                          for x in n.value.args))
    # First four statements: schema, now, freshness60s, memory64+16GiB.
    # All own-root count/health nodes and route/storage tail remain IDENTICAL.
    # Exclude only the historical two-owner q/old allocation section; the
    # constructor's frozen outside bound + atomic reserve below replaces it.
    selected=[*original.body[:4],*original.body[own:]]
    need(own==9 and root_guard>own and any(isinstance(n,ast.Constant) and n.value=='SEED46_MEMORY_KEEP_SMOKE16_PLUS64'
                                          for n in ast.walk(original.body[3])),
         'DYNTEAM_EXACT_ORIGINAL_RESOURCE_AST_BOUNDARIES')
    original.body=selected
    # User msg257: only successful ACTIVATE removes the batch deduction.
    # All other original AST nodes, constants, routes and health stay intact.
    target=ast.parse("disk['available_bytes']-disk['existing_reserved_bytes']-disk['new_batch_estimate_bytes']",mode='eval').body
    replacement=ast.parse("disk['available_bytes']-disk['existing_reserved_bytes']-(disk['new_batch_estimate_bytes'] if storage_lifecycle_phase=='PREACTIVATE_INCLUDING_ACTIVATE' else 0)",mode='eval').body
    class PhasePort(ast.NodeTransformer):
        def __init__(self,a,b):self.a=a;self.b=b;self.hits=0
        def visit_BinOp(self,node):
            if ast.dump(node,include_attributes=False)==ast.dump(self.a,include_attributes=False):
                self.hits+=1;return __import__('copy').deepcopy(self.b)
            return self.generic_visit(node)
    original_before=__import__('copy').deepcopy(original)
    forward=PhasePort(target,replacement);original=forward.visit(original)
    inverse=PhasePort(replacement,target);restored=inverse.visit(__import__('copy').deepcopy(original))
    need(forward.hits==inverse.hits==1 and ast.dump(restored,include_attributes=False)==ast.dump(original_before,include_attributes=False),
         'DYNTEAM_STORAGE_PHASE_ONLY_BATCH_NODE_EXACT_INVERSE')
    original.args.kwonlyargs.append(ast.arg(arg='storage_lifecycle_phase'))
    original.args.kw_defaults.append(ast.Constant(value=PREACTIVATE_STORAGE))
    phase_guard=ast.parse("need(storage_lifecycle_phase in ('PREACTIVATE_INCLUDING_ACTIVATE','RUNTIME_AFTER_SUCCESSFUL_ACTIVATE') and value.get('storage_lifecycle_phase')==storage_lifecycle_phase,'DYNTEAM_STORAGE_SAMPLER_VALIDATOR_SAME_REAL_LIFECYCLE')").body[0]
    original.body.insert(0,phase_guard)
    # Validate exactly the credit equation published by the current sampler.
    original.body.insert(1,ast.parse("validate_storage_retirement_equations(value['storage'])").body[0])
    namespace=dict(need=need,time=time,PurePosixPath=PurePosixPath,ROOT=root,GiB=GIB,
                   SEARCH_HOST=SEARCH_HOST,SEARCH_DATA_ROOT=SEARCH_DATA_ROOT,EVAL_HOST=EVAL_HOST,
                   validate_storage_retirement_equations=validate_storage_retirement_equations)
    helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('scratch_path','search_path')]
    code=ast.fix_missing_locations(ast.Module(body=[*helpers,original],type_ignores=[]))
    exec(compile(code,__file__+':original_resource_predicates','exec'),namespace)
    return namespace['validate'],dict(original_source_sha256=ORIGINAL_SHA,
        selected_predicate_AST_sha256=hashlib.sha256(ast.dump(code,include_attributes=False).encode()).hexdigest(),
        historical_seed46_allocation_enum_not_reused=True,numeric_health_memory_storage_thresholds_unchanged=True)


class NativeCohortResources:
    def __init__(self,core,allocation,*,memory_reader=None,wall_ns=None,monotonic_ns=None):
        from original_relay_core import OriginalRelayCore
        need(type(core) is OriginalRelayCore and type(allocation) is CohortAllocation and
             not hasattr(core,'cohort_resources') and set(core.gate.startup_held)==set(core.rows) and
             (core.qualification_only or memory_reader is wall_ns is monotonic_ns is None),
             'DYNTEAM_COHORT_RESOURCE_ONLY_COLD_SAME_ORIGINAL_OWNER')
        allocation.checked()
        self.core,self.ledger,self.allocation=core,core.ledger,allocation
        self.owner=process_birth(os.getpid());self.contract_sha=digest(core.contract)
        self.path=core.home/'resources/COHORT_RESOURCES_PUBLIC.json'
        self.memory=original_mem_available if memory_reader is None else memory_reader
        self.wall=time.time_ns if wall_ns is None else wall_ns
        self.monotonic=time.monotonic_ns if monotonic_ns is None else monotonic_ns
        self.validator,self.predicate_proof=compiled_original_validator(core.contract['arms'][0]['root'])
        self.state=None;self.failures=[];self.launch_reservations={};self.capacities=[]
        self.next_refresh_mono=0
        self.original_paused=self.ledger.model_paused;self.original_reserve=self.ledger.reserve
        with self.ledger.mutex:
            need(not self.ledger.db.in_transaction and
                 self.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0,
                 'DYNTEAM_RESOURCES_INSTALLED_BEFORE_ANY_SCIENTIFIC_REQUEST')
            owner=self
            def paused(_ledger):return owner.original_paused() or not owner.experiment_open()
            def reserve(_ledger,*args,**kwargs):
                with owner.ledger.mutex:
                    # Existing gate uses this fixed refusal as a waitable
                    # capacity HOLD. Direct callers cannot bypass the guard.
                    need(owner.experiment_open() and owner.ledger.global_unresolved()<owner.local_ceiling,
                         'TRAJECTORY_CAPACITY')
                    return owner.original_reserve(*args,**kwargs)
            self.ledger.model_paused=MethodType(paused,self.ledger)
            self.ledger.reserve=MethodType(reserve,self.ledger)
            core.cohort_resources=self

    @property
    def local_ceiling(self):return 96-SYSTEM_RESERVED-self.allocation.other_maximum_FP8_inflight

    def _no_science_lock(self):
        need(not self.ledger.mutex._is_owned(),'DYNTEAM_RESOURCE_IO_OUTSIDE_SCIENCE_LOCK_ONLY')

    def _current(self):
        need(process_birth(os.getpid())==self.owner and digest(self.core.contract)==self.contract_sha,
             'DYNTEAM_RESOURCE_EXACT_OWNER_AND_FROZEN_CONTRACT')

    def _read(self):
        self._no_science_lock();self._current();p=self.path
        need(p.is_absolute() and p.parent.resolve()==p.parent and not p.is_symlink(),
             'DYNTEAM_EXACT_OWN_PUBLIC_RESOURCE_PATH')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_uid in (0,os.geteuid()) and
                 stat.S_IMODE(before.st_mode)==0o444 and before.st_nlink==1 and before.st_size<=131072,
                 'DYNTEAM_BOUNDED_READONLY_PUBLIC_RESOURCE_RECEIPT')
            with os.fdopen(fd,'rb',closefd=False) as source:raw=source.read(131073)
            after=os.fstat(fd);current=p.lstat()
            identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            need(len(raw)==before.st_size and identity(before)==identity(after)==identity(current),
                 'DYNTEAM_PUBLIC_RESOURCE_RECEIPT_STABLE_SAME_INODE')
        finally:os.close(fd)
        return json.loads(raw)

    def refresh(self):
        # All FD/Docker/system resource reads happen BEFORE ledger.condition.
        self._no_science_lock();state=None
        try:
            value=self._read();now=self.wall();mono=self.monotonic()
            need(not value.get('OWN_fixture_host_projection_used',False) or
                 self.core.qualification_only and value.get('qualification_only') is True,
                 'DYNTEAM_RESOURCE_PRODUCTION_REFUSES_OWN_HOST_FIXTURE')
            envelope=value['dynteam_allocation']
            need(type(envelope) is dict and envelope==dict(schema='count14-dynteam-cohort-resource-binding-v1',
                contract_sha256=self.contract_sha,owner_pid=self.owner.pid,owner_start_ticks=self.owner.start_ticks,
                owner_boot_id=self.owner.boot_id,inventory_sha256=self.allocation.inventory_sha256,
                other_maximum_FP8_inflight=self.allocation.other_maximum_FP8_inflight,SYSTEM_reserved_slots=2,
                no_active_unregistered_roots=True,other_bound_is_full_allocations_plus_retained_UNKNOWN=True),
                'DYNTEAM_RESOURCE_COMPLETE_REGISTERED_ALLOCATIONS_EXACT_BINDING')
            predicate_value=value
            if self.core.qualification_only:
                # OWN local test trees are /tmp, not a Dev4 scratch mount.
                # Project ONLY those path strings for the original PURE
                # scratch predicate; retain raw paths for actual same-object
                # membership comparisons below. Never used in production,
                # never written to the source PUBLIC receipt, not a mount
                # or production filesystem qualification.
                from copy import deepcopy
                predicate_value=deepcopy(value)
                for row in predicate_value['own_FP8_relays']['roots']:
                    path=PurePosixPath(row['root'])
                    if not any(path.is_relative_to(base) for base in ('/mnt/ptb-scratch','/mnt/ptb-scratch2')):
                        need(path.is_absolute() and any(part.startswith('OWN-') for part in path.parts),
                             'DYNTEAM_ONLY_EXPLICIT_OWN_FIXTURE_PATH_PROJECTION')
                        row['root']='/mnt/ptb-scratch2/OWN-fixture-'+digest(row['root'])
            phase=storage_lifecycle_phase(self.core)
            self.validator(predicate_value,now_ns=now,for_system_health=True,storage_lifecycle_phase=phase)
            roots=value['own_FP8_relays']['roots'];our={r['root'] for r in self.core.rows.values()}
            if hasattr(self.core,'system_health') or hasattr(self.core,'resource_producer'):
                # This same owner's separately reserved SYSTEM2 is NOT an
                # OTHER-owner allocation. Its exact source root is mandatory;
                # an arbitrary prefix or missing registered source is not0.
                system_root=str(self.core.home/'system-health')
                system_rows=[r for r in roots if r['root']==system_root]
                need(len(system_rows)==1 and system_rows[0]['FP8_inflight']<=2,
                     'DYNTEAM_RESOURCE_SAME_OWNER_EXACT_SYSTEM2_SOURCE_REQUIRED')
                need(hasattr(self.core,'system_health') or system_rows[0]['FP8_inflight']==0,
                     'DYNTEAM_RESOURCE_NEVER_REGISTERED_SYSTEM_CANNOT_HIDE_OTHER_SLOTS')
                our.add(system_root)
            need(our<={r['root'] for r in roots} and
                 sum(r['FP8_inflight'] for r in roots if r['root'] not in our)<=self.allocation.other_maximum_FP8_inflight,
                 'DYNTEAM_OUTSIDE_BOUND_CANNOT_OMIT_REGISTERED_OR_RETAINED_SLOTS')
            healthy=True;reason=None
            try:self.validator(predicate_value,now_ns=now,for_system_health=False,storage_lifecycle_phase=phase)
            except Refused as failure:healthy=False;reason=failure.code
            times=[value['observed_ns'],value['own_FP8_relays']['observed_ns']]
            if healthy:times.append(value['own_admission_health']['observed_ns'])
            ttl=min(60*10**9-(now-observed) for observed in times)
            need(ttl>=0,'DYNTEAM_RESOURCE_NO_EXTENDED_TIMESTAMP_TTL')
            # Exact private daemon must remain the originally bound one; a
            # public receipt's booleans cannot replace this control recheck.
            if hasattr(self.core,'native_containers'):
                route=self.core.native_containers.docker.route
                if not self.core.qualification_only:
                    need('unix://'+str(route.socket_path)==SEARCH_HOST and str(route.data_root)==SEARCH_DATA_ROOT,
                         'DYNTEAM_RESOURCE_SAME_REGISTERED_PRIVATE_SEARCH_DAEMON')
                self.core.native_containers.docker.verify_daemon()
            elif not self.core.qualification_only:need(False,'DYNTEAM_RESOURCE_REAL_NATIVE_DAEMON_REQUIRED')
            state=dict(system=True,experiment=healthy,storage_lifecycle_phase=phase,observed_mono=mono,expires_mono=mono+ttl,
                observed_wall=now,expires_wall=min(times)+60*10**9,reason=reason,
                raw_public_receipt_sha256=digest(value),reported_all_own_FP8=value['own_FP8_relays']['total_FP8_inflight'])
        except Exception as failure:
            self.failures.append(dict(PUBLIC_code='DYNTEAM_RESOURCE_REFRESH_HELD',exception_type=type(failure).__name__))
            self.failures=self.failures[-32:]
        # No filesystem/network work under the original scientific mutex.
        with self.ledger.capacity_changed:
            self.state=state;self.ledger.capacity_changed.notify_all()
        self.next_refresh_mono=self.monotonic()+10**9
        return self.public()

    def maybe_refresh(self):
        self._no_science_lock()
        if self.monotonic()>=self.next_refresh_mono:return self.refresh()
        return None

    def _fresh(self):
        state=self.state
        if state is None:return False
        mono,wall=self.monotonic(),self.wall()
        return (state['storage_lifecycle_phase']==storage_lifecycle_phase(self.core) and
                state['observed_mono']<=mono<=state['expires_mono'] and
                state['observed_wall']<=wall<=state['expires_wall'])

    def experiment_open(self):return self._fresh() and self.state['experiment'] and self.local_ceiling>0
    def system_open(self):return self._fresh() and self.state['system']

    def bootstrap_admission_open(self,forecast):
        # A pre-consumption boolean only. Use the EXACT original conjunct,
        # including REAL pending native forecasts; no estimate/default/credit.
        self._no_science_lock();need(type(forecast) is int and forecast>=0,'DYNTEAM_EXPLICIT_BOOTSTRAP_FORECAST')
        available=self.memory()
        return (self.system_open() and type(available) is int and
                available-forecast-sum(self.launch_reservations.values())>=80*GIB)

    def before_bootstrap(self,forecast,*,_defer_unadmitted=False):
        self._no_science_lock();need(type(forecast) is int and forecast>=0,'DYNTEAM_EXPLICIT_BOOTSTRAP_FORECAST')
        available=self.memory()
        admitted=(self.system_open() and type(available) is int and
             available-forecast-sum(self.launch_reservations.values())>=80*GIB)
        if _defer_unadmitted is True and not admitted:return False
        need(admitted,'DYNTEAM_BOOTSTRAP_KEEP64PLUS16_AND_PENDING_NATIVE_FORECASTS')
        return True

    def reserve_native_launch(self,key):
        self._no_science_lock();need(type(key) is tuple and len(key)==2 and key[0] in self.core.rows and
            key[1] in self.core.rows[key[0]]['roles'],'DYNTEAM_REGISTERED_NEW_NATIVE_LAUNCH')
        if key in self.launch_reservations:return True
        available=self.memory()
        if (not self.experiment_open() or type(available) is not int or
            available-sum(self.launch_reservations.values())-NATIVE_PAIR_FORECAST<80*GIB):return False
        self.launch_reservations[key]=NATIVE_PAIR_FORECAST
        return True

    def finish_native_launch(self,key):
        # Only after the original launch commitment; not a model-slot release,
        # container cleanup, failure retry or claimed physical request end.
        need(key in self.launch_reservations,'DYNTEAM_ORIGINAL_NATIVE_LAUNCH_FORECAST_REQUIRED')
        del self.launch_reservations[key]

    def defer_unadmitted_launch(self,key):
        # Membership was not acquired, so the original shell never received
        # ALLOW. Release only this RAM forecast, never a request/permit/lease.
        need(key not in self.core.pending_native_launches,'DYNTEAM_ONLY_UNADMITTED_FORECAST_CAN_DEFER')
        self.finish_native_launch(key)

    def bind_aux_capacity(self,capacity):
        from model_capacity import ModelCapacity
        need(type(capacity) is ModelCapacity and capacity.ledger is self.ledger and
             capacity.global_cap==96 and capacity.aux_cap==16 and capacity not in self.capacities,
             'DYNTEAM_SAME_ORIGINAL_AUX16_CAPACITY_FOR_RESOURCE_GUARD')
        source=textwrap.dedent(inspect.getsource(ModelCapacity.acquire));tree=ast.parse(source)
        need(hashlib.sha256(source.encode()).hexdigest()==ORIGINAL_AUX_ACQUIRE_SHA,
             'DYNTEAM_ORIGINAL_AUX_ACQUIRE_SOURCE_PIN')
        with self.ledger.mutex:
            need(self.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0 and
                 self.ledger.db.execute('SELECT COUNT(*) FROM aux_permits').fetchone()[0]==0,
                 'DYNTEAM_AUX_RESOURCE_BIND_ONLY_COLD_BEFORE_PAID_REQUESTS')
        sites=[n for n in ast.walk(tree) if isinstance(n,ast.If) and
               ast.dump(n.test,include_attributes=False)==ast.dump(ast.parse('self.ledger.model_paused()',mode='eval').body,include_attributes=False)]
        need(len(sites)==1,'DYNTEAM_ORIGINAL_AUX_SINGLE_NEW_ADMISSION_GUARD')
        # Retain ALL original validation/reused-RESERVED idempotence before
        # this guard. Invalid scopes or replayed permits must still REFUSE.
        sites[0].test=ast.BoolOp(op=ast.Or(),values=[sites[0].test,
            ast.parse('self.ledger.global_unresolved() >= self._dynteam_cohort_resources.local_ceiling',mode='eval').body])
        namespace={};exec(compile(ast.fix_missing_locations(tree),__file__+':original_aux_acquire_with_reserved_SYSTEM',
                                 'exec'),ModelCapacity.acquire.__globals__,namespace)
        capacity._dynteam_cohort_resources=self
        capacity.acquire=MethodType(namespace['acquire'],capacity);self.capacities.append(capacity)
        return capacity

    def public(self):
        state=self.state
        return dict(PUBLIC_code='DYNTEAM_COHORT_RESOURCE_CONTROL',predicate_proof=self.predicate_proof,
            same_original_owner=True,resource_receipt_loaded=state is not None,experiment_admission_open=self.experiment_open(),
            SYSTEM_admission_open=self.system_open(),SYSTEM_reserved_slots=2,
            local_SEARCH_AUX_maximum=self.local_ceiling,pertrack_SEARCH_cap=13,total_SEARCH_cap=78,AUX_cap=16,FINAL_cap=12,
            other_maximum_FP8_inflight=self.allocation.other_maximum_FP8_inflight,
            OWN_only_fixture_public_root_projection=self.core.qualification_only,
            pending_native_launches=len(self.launch_reservations),native_pair_forecast_bytes=NATIVE_PAIR_FORECAST,
            storage_lifecycle_phase=storage_lifecycle_phase(self.core),
            health_hold_code=None if state is None else state['reason'],failures=list(self.failures),
            public_receipt_is_not_producer_or_probe_or_full_activation_proof=True,models_started=0)
