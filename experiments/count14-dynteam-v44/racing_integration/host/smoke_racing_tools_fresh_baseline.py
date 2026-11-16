"""Typed fresh native startup-control census, never paid writer rebaselining.

First hook: original exact CLI_BIRTH, immediate post-Popen BEFORE ACP input is
forwarded. Second/optional hook: FIRST native-session-ready BEFORE binding its
SID/ack/first sendText. Both require role request COUNT=0. Every birth is actual
kernel metadata from the exact Docker/image/init/bridge scope, never guessed.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib
import json
import os
import stat

from common import need,digest
from native_peer_registry import ProcessBirth,process_birth
from native_container_retirement import ContainerBinding
from native_bridge_owner import direct_native_child
from smoke_racing_tools_kernel_custody import NativeKernelToolCustody,kernel_census,_control_chain
from smoke_racing_tools_cold_control_builder import control_snapshot_clear


@dataclass(frozen=True)
class StartupComponent:
    component:str
    container_id:str
    image_id:str
    init_birth:ProcessBirth
    domain:str
    domain_device:int
    domain_inode:int
    members:tuple


@dataclass(frozen=True)
class FreshStartupBaseline:
    trajectory:str
    role:str
    owner_birth:ProcessBirth
    cli_birth:ProcessBirth
    contract_sha256:str
    stage:str
    components:tuple


def _bound(custody):
    need(type(custody) is NativeKernelToolCustody and custody.core is not None,
         'DYNTEAM_TYPED_SAME_OWNER_NATIVE_STARTUP_CUSTODY')
    core=custody.core
    need(not core.ledger.mutex._is_owned(),'DYNTEAM_STARTUP_CENSUS_OUTSIDE_SCIENCE_LOCK')
    return core


def _requests(core,t,role):
    with core.ledger.mutex:
        return core.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=?',(t,role)).fetchone()[0]


def _binding(core,t,role,component):
    registry=core.native_containers;key=t,role,component
    bound=registry.records.get(key);plan=registry.boot_plans.get(key) if bound is None else None
    need(bound is not None or plan is not None,'DYNTEAM_STARTUP_EXACT_CONTAINER_RECORD_OR_PLAN')
    if bound is None:
        bound=ContainerBinding(t,role,component,plan.cid,plan.image_id,plan.init_birth,plan.init_birth)
    snapshot=registry.docker.inspect(bound.cid);registry.validate(bound,snapshot,running=True)
    need(snapshot['image']==registry.image_ids[component] and process_birth(bound.init_birth.pid)==bound.init_birth,
         'DYNTEAM_STARTUP_PINNED_IMAGE_AND_FRESH_INIT')
    return bound


def _census(core,t,role):
    result=[]
    for component in ('agent','router'):
        binding=_binding(core,t,role,component);census=kernel_census(binding.init_birth)
        result.append(StartupComponent(component,binding.cid,binding.image_id,binding.init_birth,census.domain,
            census.domain_device,census.domain_inode,census.members))
    return tuple(result)


def _receipt(custody,baseline):
    core=custody.core;root=Path(core.rows[baseline.trajectory]['root'])/'native-tool-startup-control'
    root.mkdir(mode=0o700,exist_ok=True)
    need(root.resolve()==root and root.is_dir() and not root.is_symlink(),
         'DYNTEAM_STARTUP_PUBLIC_METADATA_EXACT_NEW_ROOT')
    value=dict(schema='count14-native-fresh-startup-control-baseline-v1',trajectory=baseline.trajectory,
        role=baseline.role,stage=baseline.stage,contract_sha256=baseline.contract_sha256,
        role_requests=0,actual_kernel_census=True,paid_writer_rebaseline=False,
        baseline_sha256=digest(asdict(baseline)),
        components=[dict(component=c.component,container_id=c.container_id,image_id=c.image_id,
            init_pid=c.init_birth.pid,init_start_ticks=c.init_birth.start_ticks,init_boot_id=c.init_birth.boot_id,
            actual_startup_processes=len(c.members),domain_device=c.domain_device,domain_inode=c.domain_inode)
            for c in baseline.components])
    path=root/(baseline.role+'-'+baseline.stage+'-PUBLIC.json')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
    try:
        with os.fdopen(fd,'wb',closefd=False) as out:out.write((json.dumps(value,sort_keys=True)+'\n').encode());out.flush();os.fsync(fd)
    finally:os.close(fd)


def _save(custody,baseline):
    if not hasattr(custody,'fresh_startup_baselines'):custody.fresh_startup_baselines={}
    if not hasattr(custody,'pending_startup_baselines'):custody.pending_startup_baselines={}
    key=baseline.trajectory,baseline.role
    # Retain partial proof separately; failed publication is NEVER a ready proof.
    need(key not in custody.pending_startup_baselines,'DYNTEAM_STARTUP_PARTIAL_PROOF_NO_AUTOMATIC_REPLAY')
    custody.pending_startup_baselines[key]=baseline
    _receipt(custody,baseline)
    custody.fresh_startup_baselines[key]=baseline
    del custody.pending_startup_baselines[key]
    return baseline


def capture_cli_startup(custody,t,role,child):
    """Call after exact peer+direct-child proof, before original CLI_BIRTH clear."""
    core=_bound(custody);key=t,role
    need(key not in getattr(custody,'pending_startup_baselines',{}),'DYNTEAM_STARTUP_PARTIAL_NO_REBASELINE')
    need(t in core.rows and role in core.rows[t]['roles'] and type(child) is ProcessBirth and
         key in core.roles.held and _requests(core,t,role)==0,
         'DYNTEAM_ONLY_UNPAID_HELD_NATIVE_STARTUP_BASELINE')
    old=getattr(custody,'fresh_startup_baselines',{}).get(key)
    if old is not None:
        need(old.cli_birth==child and old.contract_sha256==digest(core.contract),
             'DYNTEAM_STARTUP_BASELINE_EXACT_SAME_CLI_NO_REBASELINE')
        return old
    need(key not in core.bridge_owner.clis and key not in core.roles.births,
         'DYNTEAM_STARTUP_NO_PRIOR_LOGICAL_OR_PAID_CLI_BIRTH')
    agent=_binding(core,t,role,'agent')
    namespace=[]
    for line in Path('/proc',str(child.pid),'status').read_bytes().splitlines():
        if line.startswith(b'NSpid:'):namespace=list(map(int,line.split()[1:]))
    need(namespace and direct_native_child(agent.peer_birth.pid,namespace[-1],child.start_ticks,
         expected_uid=child.uid)==child,'DYNTEAM_STARTUP_ORIGINAL_EXACT_DIRECT_CLI_CHILD')
    components=_census(core,t,role)
    need(child in next(c.members for c in components if c.component=='agent') and
         _requests(core,t,role)==0 and key in core.roles.held and key not in core.bridge_owner.clis,
         'DYNTEAM_STARTUP_STILL_ZERO_REQUESTS_BEFORE_FORWARD')
    baseline=FreshStartupBaseline(t,role,process_birth(os.getpid()),child,digest(core.contract),
        'CLI_BEFORE_FORWARD',components)
    return _save(custody,baseline)


def capture_first_session_startup(custody,t,role):
    """FIRST original native-session-ready, before its original bind/ack/prompt.

    This is the only one-time extension: native initialize/newSession may start
    persistent SDK processes after the immediate Popen census. Never called to
    absorb a process created after a model request or an already-bound session.
    """
    core=_bound(custody);key=t,role
    need(key not in getattr(custody,'pending_startup_baselines',{}),'DYNTEAM_STARTUP_PARTIAL_NO_SESSION_REBASELINE')
    old=getattr(custody,'fresh_startup_baselines',{}).get(key)
    need(type(old) is FreshStartupBaseline and old.owner_birth==process_birth(os.getpid()) and
         old.contract_sha256==digest(core.contract),'DYNTEAM_FIRST_SESSION_SAME_TYPED_CLI_STARTUP_BASELINE')
    if old.stage=='FIRST_SESSION_BEFORE_PROMPT':return old # same immutable proof, no new census
    need(old.stage=='CLI_BEFORE_FORWARD' and _requests(core,t,role)==0,
         'DYNTEAM_FIRST_SESSION_NEVER_PAID_STARTUP_REBASELINE')
    cli=core.bridge_owner.clis.get(key)
    need(cli is not None and cli['birth']==old.cli_birth and process_birth(old.cli_birth.pid)==old.cli_birth,
         'DYNTEAM_FIRST_SESSION_EXACT_SAME_FRESH_NATIVE_CLI')
    track=core.sessions.tracks[t]
    with track._lock:need(key not in track._current,'DYNTEAM_STARTUP_ONLY_BEFORE_FIRST_ORIGINAL_SESSION_BIND')
    components=_census(core,t,role)
    need(_requests(core,t,role)==0 and process_birth(old.cli_birth.pid)==old.cli_birth,
         'DYNTEAM_FIRST_SESSION_STILL_ZERO_MODELS_BEFORE_PROMPT')
    baseline=FreshStartupBaseline(t,role,old.owner_birth,old.cli_birth,old.contract_sha256,
        'FIRST_SESSION_BEFORE_PROMPT',components)
    return _save(custody,baseline)


def project_startup_bound_tools(custody,t,role):
    """None: no startup proof, use old strict pre-CLI path. Bool: real proof.

    This is the precise paid replacement: same current child + fresh exact
    lifecycle zero prompt/tool control + no births outside immutable startup
    domains. It never allows counts=0 to erase unregistered background writers.
    """
    core=_bound(custody);key=t,role
    if key in getattr(custody,'pending_startup_baselines',{}):return False
    baseline=getattr(custody,'fresh_startup_baselines',{}).get(key)
    if baseline is None:return None
    try:
        need(type(baseline) is FreshStartupBaseline and baseline.owner_birth==process_birth(os.getpid()) and
             baseline.contract_sha256==digest(core.contract),'DYNTEAM_TOOL_SAME_STARTUP_OWNER_CONTRACT')
        cli=core.bridge_owner.clis.get(key)
        child=baseline.cli_birth if cli is None else cli['birth']
        need(child==baseline.cli_birth,'DYNTEAM_TOOL_NO_OLD_STARTUP_BASELINE_FOR_NEW_CLI')
        try:live=process_birth(child.pid)==child
        except FileNotFoundError:live=False
        paid=_requests(core,t,role)>0
        control_clear=control_snapshot_clear(custody,t,role,child)
        if paid and live and not control_clear:return False
        for component in baseline.components:
            record=_binding(core,t,role,component.component)
            need((record.cid,record.image_id,record.init_birth)==
                 (component.container_id,component.image_id,component.init_birth),
                 'DYNTEAM_TOOL_STARTUP_CONTAINER_GENERATION_STILL_EXACT')
            census=kernel_census(record.init_birth)
            need((census.domain,census.domain_device,census.domain_inode)==
                 (component.domain,component.domain_device,component.domain_inode),
                 'DYNTEAM_TOOL_STARTUP_KERNEL_DOMAIN_STILL_EXACT')
            allowed=set(component.members)
            if paid and not live and not control_clear:
                # A crash is not a terminal callback. Only original framework
                # control ancestry may remain; original startup SDKs must exit.
                allowed=set(_control_chain(record.peer_birth,record.init_birth))
            if component.component=='agent':
                from smoke_racing_tools_game_manager import registered_game_controls
                allowed |= registered_game_controls(core,t,role)
            need(set(census.members)<=allowed,'DYNTEAM_TOOL_BACKGROUND_OR_NEW_WRITER_NOT_STARTUP_CONTROL')
        return True
    except Exception:return False


def prove_pre_forward_birth(guarded_bridge_source):
    """Cold static proof: actual born hook precedes all original ACP forwarding.

    This complements (does not replace) the control builder's inverse-AST proof
    of unchanged original forwarding/body operations. It never opens runtime
    protocol data, source workspaces or a scientific executable.
    """
    import ast
    tree=ast.parse(guarded_bridge_source)
    server=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='serve_connection')
    def call(node,object_name,method):
        return (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and
            isinstance(node.func.value,ast.Name) and node.func.value.id==object_name and node.func.attr==method)
    births=[(i,n) for i,n in enumerate(server.body) if isinstance(n,ast.Expr) and call(n.value,'_count14_lifecycle','born')]
    need(len(births)==1,'DYNTEAM_EXACT_SINGLE_ORIGINAL_NATIVE_BIRTH_HOOK')
    at= births[0][0];forwarding=[];thread_starts=[]
    for i,top in enumerate(server.body):
        for node in ast.walk(top):
            if call(node,'t1','start') or call(node,'t2','start'):thread_starts.append(i)
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                value=node.func.value
                stdin=(isinstance(value,ast.Attribute) and isinstance(value.value,ast.Name) and
                       value.value.id=='proc' and value.attr=='stdin')
                if stdin and node.func.attr in ('write','flush'):forwarding.append(i)
                if isinstance(value,ast.Name) and value.id=='client_sock' and node.func.attr=='sendall':forwarding.append(i)
    need(thread_starts and forwarding and all(at<i for i in (*thread_starts,*forwarding)),
         'DYNTEAM_NATIVE_BIRTH_BEFORE_ALL_THREAD_STARTS_AND_ACP_FORWARDING')
    return dict(schema='count14-native-pre-forward-birth-static-proof-v1',
        born_before_original_ACP_forwarding=True,born_before_original_reader_thread_starts=True,
        one_exact_birth_hook=True,original_forward_operations_observed=len(forwarding))
