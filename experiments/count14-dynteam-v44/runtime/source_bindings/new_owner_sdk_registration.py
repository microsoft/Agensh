"""Typed INERT-only NEW-owner original SDK control registration.

No original SDK same-owner guard is removed, no old candidate owner or CLI
identity is rewritten. Source Epochs remain retained; only a verified receiving
registration creates separately owned Epoch values. No load/ACK/prompt/peer IO.
"""
from dataclasses import dataclass,replace
from pathlib import Path
from types import MethodType,SimpleNamespace
import ast
import copy
import hashlib
import importlib
import os
import stat
import threading

from budget import Ledger
from dynteam_sessions import CohortSessions,AffinityDomain,DynamicSessions
from native_sdk_startup_epochs import NativeSdkStartupEpochs,Epoch,Component,Pending
from native_container_retirement import ContainerBinding,ContainerBootPlan
from native_peer_registry import ProcessBirth,process_birth
from formal_full_used_domain import digest,wire
import full_used_paid_adopt as U
import native_sdk_epoch_control as C
import native_sdk_epoch_control_v2 as V
import bounded_metadata_ro as B
import normal_inert_cut as T
import metadata_inert_pair as M

PINS=dict(native_sdk_epoch_control='6a813f5a8726c1d60a54411da8f7a0e477ec9f96a52022235db24b0f3a39bd44',
 native_sdk_epoch_control_v2='2f7ab34a1a1a89b39bba94ee0c8801b0cac48d811b95dc51e5961b755e9bb417',
 normal_inert_cut='aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',metadata_inert_pair='83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da')
SCHEMA='count14-new-owner-native-sdk-INERT-registration-v1'


class SdkRegistrationWait(RuntimeError):pass


def need(ok,code):
    if not ok:raise SdkRegistrationWait(code)


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_sources():
    for name,pin in PINS.items():
        path=Path(importlib.import_module(name).__file__)
        need(path.is_absolute()and path.resolve()==path and not path.is_symlink()and file_sha(path)==pin,
             'NEW_OWNER_SDK_FIXED_TICKET_PAIR_AND_ORIGINAL_SOURCE_PIN')
    V.verify_sources();return dict(PINS)


def _birth(value):return value if type(value)is ProcessBirth else U.birth(value)


def _metadata_codec(section,history):
    """Reuse ONLY the frozen original pure CONTROL dataclass codec block.

    This is not an SDK lifecycle guard bypass: every original source-control,
    locator, old/new-owner and receiving ticket guard is performed by this NEW
    registration API before invoking the unchanged pure metadata decode block.
    No FormalSdkRestoreControl/SDK runtime function is cloned or weakened.
    """
    tree=ast.parse(Path(C.__file__).read_bytes())
    original=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='reconstruct_metadata')
    block=next(n for n in original.body if isinstance(n,ast.With))
    start=next(i for i,n in enumerate(block.body)if isinstance(n,ast.FunctionDef)and n.name=='sid')
    body=copy.deepcopy(block.body[start:])
    need(isinstance(body[-1],ast.Assign)and any(isinstance(v,ast.Name)and v.id=='result'for v in body[-1].targets),
         'NEW_OWNER_SDK_EXACT_ORIGINAL_METADATA_CODEC_BLOCK')
    fn=ast.FunctionDef(name='_original_control_decode',args=ast.arguments(posonlyargs=[],
        args=[ast.arg(arg='section'),ast.arg(arg='h')],kwonlyargs=[],kw_defaults=[],defaults=[]),
        body=body+[ast.Return(value=ast.Name(id='result',ctx=ast.Load()))],decorator_list=[])
    code=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]));namespace={}
    exec(compile(code,str(Path(__file__))+':original_control_codec','exec'),dict(vars(C)),namespace)
    return namespace['_original_control_decode'](section,history)


def _full_used_history(owner,cap,section,budget):
    core=owner.core;pair=core.metadata_inert_pair;directory=Path(section['full_used_domain']['directory']['path'])
    fd=cap.full_used_fd
    need(type(pair)is M.MetadataInertPair and type(fd)is int and fd in pair.lock_fds and
         U.identity(directory.lstat())=={k:section['full_used_domain']['directory'][k]for k in
             ('device','inode','uid','gid','mode')} and
         (os.fstat(fd).st_dev,os.fstat(fd).st_ino)==(directory.stat().st_dev,directory.stat().st_ino),
         'NEW_OWNER_SDK_REGISTERED_TICKET_FULLUSED_FD_NOT_CALLER_FD')
    # Kernel control metadata only, never process argv/SDK/private bodies.
    rows=[line.split()for line in Path('/proc/self/fdinfo',str(fd)).read_text().splitlines()if line.startswith('lock:')]
    need(any(len(r)>=7 and r[2:5]==['FLOCK','ADVISORY','WRITE']and r[5]==str(os.getpid())for r in rows),
         'NEW_OWNER_SDK_ORIGINAL_EXCLUSIVE_FULLUSED_OFD_CUSTODY')
    view=SimpleNamespace(directory=directory,fd=fd,_epoch_control_capture_core=core)
    h=C._history(view,budget);saved=section['full_used_domain']
    need(saved==dict(directory=dict(path=str(directory),**U.identity(directory.lstat())),
         source_binding_sha256=digest(h.binding),record_sequence=h.sequence,record_sha256=h.record_sha256,
         full_used_sha256=digest(list(h.values)),used_count=len(h.values)),
         'NEW_OWNER_SDK_EXACT_ORIGINAL_SESSION_LOCATOR_HISTORY_TIP')
    return h


def _new_sessions(core,section,decoded,history):
    need(getattr(core,'sessions',None)is None,'NEW_OWNER_SDK_ONLY_NEW_UNHYDRATED_SESSION_GRAPH')
    racing=[t for t,row in core.rows.items()if row['arm']=='DYNTEAM_RACING']
    sessions=CohortSessions(list(core.rows),racing_trajectories=racing)
    need({t:list(v.roles)for t,v in sessions.tracks.items()}==section['catalogues'],
         'NEW_OWNER_SDK_ORIGINAL_COMPLETE_SESSION_ROLE_CATALOGUE')
    domain=next(iter(sessions.tracks.values())).domain
    need(type(domain)is AffinityDomain and not domain.used and
         all(t.domain is domain and not t._current for t in sessions.tracks.values()),
         'NEW_OWNER_SDK_NEW_EMPTY_RAM_ONLY_NO_EXISTING_DOMAIN_MUTATION')
    # The original paid-control restoration operation on NEW RAM only: not
    # DynamicSessions.bind/claim, not new SID allocation or source reset.
    domain.used.update(history.values)
    for key,pair in decoded.current_original_session_pairs.items():
        if pair is None:continue
        need(key[0]in sessions.tracks and key[1]in sessions.tracks[key[0]].roles and pair[1]in domain.used,
             'NEW_OWNER_SDK_EXACT_ORIGINAL_SESSION_PAIR_FROM_VERIFIED_DOMAIN')
        sessions.tracks[key[0]]._current[key]=pair
    return sessions


def _inert_runtime(*args,**kwargs):
    raise SdkRegistrationWait('NEW_OWNER_SDK_INERT_TICKET_NO_NATIVE_LOAD_PEER_OR_RUNTIME_AUTHORITY_WAIT')


def _first_quarantine(instance,cls,metadata=()):
    for name in vars(cls):
        if not name.startswith('__')and callable(getattr(cls,name,None))and name not in metadata:
            setattr(instance,name,MethodType(_inert_runtime,instance))


@dataclass(frozen=True,repr=False)
class RetainedCliRegistration:
    source_control:C.CapturedCliControl
    receiving_owner_birth:ProcessBirth
    retained_original_shape_record:dict


@dataclass(frozen=True,repr=False)
class RetainedContainerRegistration:
    key:tuple
    source_component:Component
    source_epoch:Epoch
    original_binding:object
    original_boot_plan:ContainerBootPlan
    peer_metadata_resolved:bool


@dataclass(frozen=True,repr=False)
class InertSdkRegistration:
    owner:object
    source_control_sha256:str
    source_component_sha256:str
    old_owner_birth:ProcessBirth
    new_owner_birth:ProcessBirth
    source_transfer:C.OriginalEpochMetadataTransfer
    source_section:dict
    epochs:NativeSdkStartupEpochs
    sessions:CohortSessions
    received_epochs:tuple
    retained_clis:dict
    retained_containers:tuple
    unresolved_native_peer_components:tuple

    def public(self):
        return dict(schema=SCHEMA,source_control_sha256=self.source_control_sha256,
            source_component_sha256=self.source_component_sha256,
            old_owner_birth_sha256=digest(C._birth(self.old_owner_birth)),
            new_owner_birth_sha256=digest(C._birth(self.new_owner_birth)),
            registered_original_Epoch_objects=len(self.received_epochs),registered_original_epoch_roles=len(self.epochs.current),
            retained_original_CLI_controls=len(self.retained_clis),retained_container_controls=len(self.retained_containers),
            unresolved_native_peer_components=len(self.unresolved_native_peer_components),
            same_original_SID_domain_and_request_anchors=True,source_old_Epochs_and_owner_provenance_preserved=True,
            original_CLI_Python_identity_claimed=False,new_owner_truthfully_registered=True,
            original_metadata_owner_count_session_methods_available=True,
            registered_native_peer_or_container_runtime=False,strict_path_runtime_bound=False,
            actual_SDK_strict_load_ACK_once_recovery_qualified=False,runtime_ready=False,
            safe_to_TERM=False,paid_normal_activation=False,whole_paid_restore_qualified=False)

    def require_original_strict_runtime(self):
        # INERT receiving registration intentionally grants no host/guest load,
        # original controller lifecycle/peer authority or prompt permission.
        raise SdkRegistrationWait('NEW_OWNER_SDK_ORIGINAL_STRICT_LOAD_ACK_ONCE_PATH_REQUIRES_REAL_NATIVE_BINDINGS_AND_AUTHORITY_WAIT')


def _install_metadata_methods(registration):
    epochs=registration.epochs;core=registration.owner.core
    def current():
        need(process_birth(os.getpid())==registration.new_owner_birth and
             core.inert_sdk_transfer_registration is registration and core.native_sdk_startup_epochs is epochs,
             'NEW_OWNER_SDK_EXACT_REGISTERED_RECEIVING_PROCESS_AND_CORE')
        NativeSdkStartupEpochs._owner(epochs)
    def counts(all_rows,key=None):
        current();budget=B.ReadBudget(25)
        with B.readonly(core.ledger.home/'ledger.sqlite',budget,lambda:C._check_budget(budget,core))as db:
            l=Ledger.__new__(Ledger);l.db,l.mutex=db,threading.RLock()
            view=NativeSdkStartupEpochs.__new__(NativeSdkStartupEpochs);view.core=SimpleNamespace(ledger=l)
            return NativeSdkStartupEpochs._requests_all(view)if all_rows else NativeSdkStartupEpochs._count(view,key)
    def count(_epochs,key):return counts(False,key)
    def all_count(_epochs):return counts(True)
    def session(_epochs,key):
        current();return V._EpochReadPort(epochs,B.ReadBudget(25))._session(key)
    epochs._count=MethodType(count,epochs);epochs._requests_all=MethodType(all_count,epochs)
    epochs._session=MethodType(session,epochs)


def _register(owner,cap,*,read_budget):
    core=owner.core;C._check_budget(read_budget,core)
    old,new=_birth(cap.old_owner_birth),_birth(cap.new_owner_birth)
    need(old!=new and new==process_birth(os.getpid()) and digest(core.contract)==cap.contract_sha256 and
         getattr(core,'native_sdk_startup_epochs',None)is None and
         not hasattr(core,'inert_sdk_transfer_registration') and core.sessions is None,
         'NEW_OWNER_SDK_ONLY_NEW_UNPUBLISHED_UNHYDRATED_TYPED_RECEIVER')
    section=cap.component('native_SDK_epoch_controls')
    need(section['schema']==C.SCHEMA and section['source_pins']==C.PINS and
         section['component_source_sha256']==PINS['native_sdk_epoch_control'] and
         section['bounded_source_metadata_read']['adapter_source_sha256']==PINS['native_sdk_epoch_control_v2'] and
         section['bounded_source_metadata_read']['schema']==V.SCHEMA and
         _birth(section['source_owner_birth'])==old and section['contract_sha256']==cap.contract_sha256 and
         section['catalogues']=={t:list(r['roles'])for t,r in core.rows.items()} and
         not section['unresolved_session_references'],
         'NEW_OWNER_SDK_UNMODIFIED_SOURCE_OWNER_CONTROL_AND_COMPLETE_SESSION_LOCATORS')
    history=_full_used_history(owner,cap,section,read_budget)
    need(history.writer==old or history.writer is None and history.binding['owner_sha256']==digest(C._birth(old)),
         'NEW_OWNER_SDK_ORIGINAL_FULLUSED_CURRENT_WRITER_LINEAGE')
    decoded=_metadata_codec(section,history)
    need(type(decoded)is C.OriginalEpochMetadataTransfer and decoded.source_owner_birth==old and
         all(type(e)is Epoch and e.owner_birth==old and e.contract_sha256==cap.contract_sha256 for e in decoded.epochs),
         'NEW_OWNER_SDK_ALL_OLD_EPOCH_OWNER_LINEAGE_RETAINED_NOT_REWRITTEN')
    sessions=_new_sessions(core,section,decoded,history)
    received=tuple(replace(e,owner_birth=new,stage='INERT_NEW_OWNER_CONTROL_REGISTERED')for e in decoded.epochs)
    remap={id(old_epoch):new_epoch for old_epoch,new_epoch in zip(decoded.epochs,received)}
    def moved(epoch):return None if epoch is None else remap[id(epoch)]
    epochs=NativeSdkStartupEpochs.__new__(NativeSdkStartupEpochs)
    epochs.core,epochs.owner,epochs.sha,epochs.custody=core,new,cap.contract_sha256,None
    epochs.current={k:moved(v)for k,v in decoded.current.items()}
    epochs.history=[moved(v)for v in decoded.history]
    epochs.pending={k:Pending(moved(v.epoch),moved(v.previous),copy.deepcopy(v.control))for k,v in decoded.pending.items()}
    epochs.partial=set(decoded.partial)
    epochs.session_prepared={k:moved(v)for k,v in decoded.session_prepared.items()}
    epochs.session_bound={k:moved(v)for k,v in decoded.session_bound.items()}
    clis={r.key:RetainedCliRegistration(r,new,dict(token=r.token,birth=r.birth,raw_birth=r.raw_birth,
        archived=r.archived,end_lease=r.end_lease))for r in decoded.clis}
    peers={}
    source_peer_rows=cap.component('native_peer_birth_controls')if cap.has_component('native_peer_birth_controls')else []
    for row in source_peer_rows:
        k=row['trajectory'],row['role'],row['purpose']
        need(k not in peers,'NEW_OWNER_SDK_NO_AMBIGUOUS_SOURCE_PEER_CONTROL')
        peers[k]=_birth(row['birth'])
    containers=[];unresolved=[]
    for key,epoch in sorted(decoded.current.items()):
        for c in epoch.components:
            peer=peers.get((*key,'bridge'if c.component=='agent'else 'router'))
            plan=ContainerBootPlan(*key,c.component,c.cid,c.image_id,c.init_birth)
            binding=None if peer is None else ContainerBinding(*key,c.component,c.cid,c.image_id,c.init_birth,peer)
            containers.append(RetainedContainerRegistration((*key,c.component),c,epoch,binding,plan,peer is not None))
            if peer is None:unresolved.append((*key,c.component))
    # First quarantine is installed BEFORE any new objects become reachable
    # from the real receiver core. No previous object quarantine is removed.
    _first_quarantine(epochs,NativeSdkStartupEpochs,metadata=('_owner','_count','_requests_all','_session'))
    _first_quarantine(next(iter(sessions.tracks.values())).domain,AffinityDomain)
    for track in sessions.tracks.values():_first_quarantine(track,DynamicSessions)
    registration=InertSdkRegistration(owner,cap.source_control_sha256,digest(section),old,new,decoded,
        copy.deepcopy(section),epochs,sessions,received,clis,tuple(containers),tuple(unresolved))
    _install_metadata_methods(registration)
    C._check_budget(read_budget,core)
    core.sessions=sessions;core.native_sdk_startup_epochs=epochs;core.inert_sdk_transfer_registration=registration
    epochs._owner()
    need(epochs._requests_all()==section['counts']['all_original_request_rows'],
         'NEW_OWNER_SDK_ORIGINAL_PAID_REQUEST_COUNT_NOT_REBASELINED')
    for row in section['counts']['by_registered_epoch_role']:
        need(epochs._count(tuple(row['key']))==row['original_request_rows'],
             'NEW_OWNER_SDK_EVERY_ORIGINAL_ROLE_REQUEST_ANCHOR_UNCHANGED')
    for key,pair in decoded.current_original_session_pairs.items():
        need(epochs._session(key)==pair,'NEW_OWNER_SDK_ORIGINAL_SID_PAIR_UNCHANGED')
    return registration


def register_inert_native_sdk_transfer(owner,*,ticket,read_budget):
    verify_sources()
    cap=T.verify_inert_ticket(ticket,owner=owner,read_budget=read_budget)
    need(type(cap)is T.VerifiedNormalInertCut and cap.OWN is False,'NEW_OWNER_SDK_FIXED_PRODUCTION_TICKET_VERIFIER_ONLY')
    return _register(owner,cap,read_budget=read_budget)


def register_OWN_inert_native_sdk_transfer(owner,*,ticket,read_budget):
    verify_sources()
    cap=T.verify_OWN_inert_ticket(ticket,owner=owner,read_budget=read_budget)
    need(type(cap)is T.VerifiedNormalInertCut and cap.OWN is True,'NEW_OWNER_SDK_FIXED_OWN_TICKET_VERIFIER_ONLY')
    return _register(owner,cap,read_budget=read_budget)
