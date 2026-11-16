"""Original native Epoch/CLI CONTROL capture, not SDK or NEW-owner adoption.

Only registered dataclass/RAM control and original protected FULL_USED history.
No SDK state/path/archive/log/body load, new SID, fee write, CLI action or normal
seal issuer. SID values never enter this section: original-domain locators only.
"""
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace
import copy
import hashlib
import importlib
import json
import os
import stat
import threading

from native_sdk_startup_epochs import NativeSdkStartupEpochs, Epoch, Component, Pending
from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
from budget import Ledger
from native_bridge_owner import NativeBridgeLifecycleOwner
from native_peer_registry import ProcessBirth, process_birth
from dynteam_membership_fence import Lease
from formal_full_used_domain import FullUsedDomainProducer, digest, wire
import full_used_paid_adopt as U
import bounded_metadata_ro as B
from smoke_racing_tools_native_control import checked_control

SCHEMA = 'count14-native-sdk-epoch-cli-control-candidate-v1'
PINS = dict(bounded_metadata_ro='621cd0db6da2d1e6422537f6ae2188ac8466627efe803d8b4d39f260bfb7c249',
    budget='a05ca90afffb7c149766cf4b74126eb94ba79910afd72049a1ff54d2bc50df8f',
    smoke_racing_tools_kernel_custody='5ff1cb87ca0cd1f09b6ef972edb3d4ab3c945618012ee10d8849468333f841ab',
    native_sdk_startup_epochs='a935f4406c159d3ef2067d0dc21aee9df76da1a8189fdd175b73dff9f49814af',
    native_bridge_owner='e3e2c6b41ee109a1483ee92e8820fda1ad3e186e82263968299bd848bedac346',
    native_peer_registry='0986b61a7c71b6745442b9c71dfc67d79eebf960a50523ea1e2b5ee0f37d019d',
    dynteam_membership_fence='2f6e13e919778c4dcfc985ca3338ddbb89b77cac98437f7adb19ff02bf192a51',
    formal_full_used_domain='cd980946aa14ad3105372c65a1d76a04a1ba1cca6be5b93d376b4a173b839dee',
    full_used_paid_adopt='94c70cf848ca25c49bb32ff34feef1673e61ef737caa6fa6c5f20d289e04e8c6',
    normal_cold_barrier='a778d6cde3bdb8840919231bb8336b4635762be9923cf1315d067461654f753e',
    original_relay_core='89ac900e66caa67887504522c574c1870f7a8faf51542fe248ca7f35b1541556',
    smoke_racing_tools_native_control='9c385bc46f8b0905159249b4e539bd75955899aefcb2e83001fc3dd128f58727')


class EpochControlWait(RuntimeError): pass


def need(ok, code):
    if not ok: raise EpochControlWait(code)


def file_sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_sources():
    for name, pin in PINS.items():
        module = importlib.import_module(name); p = Path(module.__file__)
        need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and file_sha(p) == pin,
             'SDK_EPOCH_CONTROL_EXACT_FRAMEWORK_SOURCE_PIN')
    for module_name, cls_name, methods in (
        ('native_sdk_startup_epochs','NativeSdkStartupEpochs',('_owner','_count','_requests_all','_session')),
        ('normal_cold_barrier','NormalCheckpointBarrier',('_current','public'))):
        module = importlib.import_module(module_name)
        top = compile(Path(module.__file__).read_bytes(), module.__file__, 'exec', dont_inherit=True)
        cls = next(c for c in top.co_consts if isinstance(c, CodeType) and c.co_name == cls_name)
        codes = {c.co_name:c for c in cls.co_consts if isinstance(c,CodeType)}
        for name in methods:
            fn = getattr(getattr(module,cls_name),name)
            need(fn.__code__ == codes[name] and fn.__globals__ is vars(module),
                 'SDK_EPOCH_CONTROL_ORIGINAL_METADATA_METHOD_CODE')
    U.verify_sources();B.verify_sources()
    return dict(PINS)


def _check_budget(budget, core):
    need(not core.ledger.mutex._is_owned(), 'SDK_EPOCH_CONTROL_NO_SCIENCE_LOCK_FOR_METADATA_IO')
    need(callable(getattr(budget,'check',None)), 'SDK_EPOCH_CONTROL_FINITE_READ_BUDGET_REQUIRED')
    budget.check()


def _history(producer, budget):
    """Original fixed history reader with only deadline checks at IO seams.

    Original function/class/global code is unchanged. No arbitrary path input:
    only registered producer.directory/FD and original FULL_USED fixed reader.
    """
    _check_budget(budget,producer._epoch_control_capture_core)
    original = U.private_read
    def read(*args, **kwargs):
        _check_budget(budget,producer._epoch_control_capture_core)
        result = original(*args, **kwargs)
        _check_budget(budget,producer._epoch_control_capture_core)
        return result
    def clone(fn, delta):
        value = FunctionType(fn.__code__,dict(fn.__globals__,**delta),fn.__name__,fn.__defaults__,fn.__closure__)
        value.__kwdefaults__=fn.__kwdefaults__;return value
    cut=clone(U.check_cut,dict(private_read=read))
    reader=clone(U.verify_history,dict(private_read=read,check_cut=cut))
    need(reader.__code__ is U.verify_history.__code__, 'SDK_EPOCH_CONTROL_ORIGINAL_HISTORY_READER_CODE')
    result=reader(producer.directory,producer.fd)
    _check_budget(budget,producer._epoch_control_capture_core)
    return result


def _sha(value):
    need(type(value)is str and len(value)==64 and all(c in '0123456789abcdef'for c in value),
         'SDK_EPOCH_CONTROL_TYPED_SHA256');return value


def _key(value,catalogues):
    need(type(value)is tuple and len(value)==2 and value[0]in catalogues and value[1]in catalogues[value[0]],
         'SDK_EPOCH_CONTROL_REGISTERED_ROLE_KEY');return list(value)


def _birth(value):
    need(type(value)is ProcessBirth,'SDK_EPOCH_CONTROL_EXACT_ORIGINAL_PROCESS_BIRTH')
    row=asdict(value);need(U.birth(row)==value,'SDK_EPOCH_CONTROL_TYPED_PROCESS_BIRTH');return row


def _token(value,catalogues):
    need(type(value)is tuple and len(value)==4 and type(value[1])is int and value[1]>=1 and
         type(value[2])is int and value[2]>=1,'SDK_EPOCH_CONTROL_TYPED_NATIVE_TOKEN')
    return [_key(value[0],catalogues),value[1],value[2],_sha(value[3])]


def _registered(epochs,bridge,producer,budget):
    core=epochs.core;_check_budget(budget,core)
    need(type(epochs)is NativeSdkStartupEpochs and type(bridge)is NativeBridgeLifecycleOwner and
         type(producer)is FullUsedDomainProducer and bridge is core.bridge_owner and bridge.core is core and
         core.native_sdk_startup_epochs is epochs and epochs.custody.core is core and
         epochs.custody.sdk_startup_epochs is epochs and type(epochs.custody)is NativeKernelToolCustody and
         type(core.ledger)is Ledger and type(core.ledger.mutex)is type(threading.RLock()) and
         producer.sessions is core.sessions and
         producer.science_mutex is core.ledger.mutex and core.formal_full_used_domain is producer and
         epochs.owner==process_birth(os.getpid()) and epochs.sha==digest(core.contract),
         'SDK_EPOCH_CONTROL_EXACT_ALREADY_REGISTERED_SAME_OWNER_GRAPH')
    epochs._owner();producer._outside_locks()
    need(all(type(getattr(epochs,n))is dict for n in ('current','pending','session_prepared','session_bound')) and
         type(epochs.history)is list and type(epochs.partial)is set and
         type(bridge.clis)is dict and type(bridge.logical)is dict and type(bridge.finished)is set and
         type(bridge.uid)is int and bridge.uid>=0,'SDK_EPOCH_CONTROL_EXACT_TYPED_RAM_CONTAINERS')
    need(not hasattr(producer,'_epoch_control_capture_core'), 'SDK_EPOCH_CONTROL_NO_EXISTING_CAPTURE_SIDE_EFFECT')
    # No foreign-source data traversal: exact original field lists only.
    need({f.name for f in fields(Epoch)}=={'trajectory','role','ordinal','owner_birth','contract_sha256',
        'child','token','request_anchor','session_before','components','stage','archived','first_session'} and
        {f.name for f in fields(Component)}=={'component','cid','image_id','init_birth','domain','device','inode','controls','sdk'},
        'SDK_EPOCH_CONTROL_ORIGINAL_DATACLASS_FIELDS')
    return core


def _capture(epochs,bridge,producer,*,read_budget):
    verify_sources();core=_registered(epochs,bridge,producer,read_budget)
    catalogues={t:list(row['roles'])for t,row in core.rows.items()}
    # This operation guards original domain/session mutations on the SAME owner
    # loop. It is not a science/session lock and never grants runtime authority.
    with producer._operation():
        producer._require_saved(producer._domain_values())
        # A temporary source-core pointer is NOT installed on original objects;
        # keep it only in this explicit local reader adapter.
        original_proxy=type('RegisteredFullUsedReadView',(),{})()
        original_proxy.directory,original_proxy.fd=producer.directory,producer.fd
        original_proxy._epoch_control_capture_core=core
        history=_history(original_proxy,read_budget)
        need(history.sequence==producer.sequence and history.record_sha256==producer.record_sha256 and
             history.values==producer.saved and history.binding==producer.binding,
             'SDK_EPOCH_CONTROL_ORIGINAL_DURABLE_SESSION_DOMAIN_TIP')
        values=history.values;indices={sid:i for i,sid in enumerate(values)};unresolved=[]
        def sid_ref(sid):
            need(type(sid)is str,'SDK_EPOCH_CONTROL_SESSION_DOMAIN_VALUE_TYPE')
            pin=hashlib.sha256(sid.encode()).hexdigest()
            if sid not in indices:
                unresolved.append(pin)
                return dict(state='UNRESOLVED_NOT_IN_ORIGINAL_FULL_USED_DOMAIN',session_sha256=pin)
            return dict(state='ORIGINAL_FULL_USED_DOMAIN_LOCATOR',index=indices[sid],session_sha256=pin)
        def session_before(value):
            if value is None:return dict(state='ORIGINAL_ABSENT')
            if type(value)is not tuple or len(value)!=2:
                unresolved.append('UNREGISTERED_SESSION_BEFORE_CONTROL_TYPE')
                return dict(state='UNRESOLVED_UNREGISTERED_SESSION_BEFORE',present=True)
            return dict(state='ORIGINAL_SESSION_PAIR',anonymous_birth_sha256=_sha(value[0]),session=sid_ref(value[1]))
        epoch_objects=[];ids={}
        def epoch_ref(epoch):
            _check_budget(read_budget,core)
            if epoch is None:return None
            need(type(epoch)is Epoch,'SDK_EPOCH_CONTROL_EXACT_EPOCH_NOT_OPAQUE_VALUE')
            existing=ids.get(id(epoch))
            if existing is not None:return existing
            number=len(epoch_objects);ids[id(epoch)]=number;epoch_objects.append(None)
            key=epoch.trajectory,epoch.role;_key(key,catalogues)
            need(type(epoch.ordinal)is int and epoch.ordinal>=1 and type(epoch.request_anchor)is int and
                 epoch.request_anchor>=0 and type(epoch.stage)is str and 0<len(epoch.stage)<=128 and
                 epoch.stage in ('PENDING_PRE_FORWARD','CLI_COMMITTED_BEFORE_FORWARD','FIRST_SESSION_BEFORE_BIND',
                    'ORIGINAL_ARCHIVED_END','COLD_RESTORED_CLI_WAIT_STRICT_SESSION','COLD_ORIGINAL_SESSION_PREPARED') and
                 type(epoch.archived)is bool and type(epoch.first_session)is bool and
                 type(epoch.components)is tuple,'SDK_EPOCH_CONTROL_TYPED_EPOCH_FIELDS')
            components=[]
            for c in epoch.components:
                need(type(c)is Component and c.component in ('agent','router') and
                     all(type(v)is str and 0<len(v)<=4096 for v in(c.cid,c.image_id,c.domain)) and
                     type(c.device)is int and c.device>=0 and type(c.inode)is int and c.inode>=0 and
                     type(c.controls)is tuple and type(c.sdk)is tuple,'SDK_EPOCH_CONTROL_TYPED_COMPONENT_FIELDS')
                components.append(dict(component=c.component,cid=c.cid,image_id=c.image_id,
                    init_birth=_birth(c.init_birth),domain=c.domain,device=c.device,inode=c.inode,
                    controls=[_birth(v)for v in c.controls],sdk=[_birth(v)for v in c.sdk]))
            epoch_objects[number]=dict(trajectory=epoch.trajectory,role=epoch.role,ordinal=epoch.ordinal,
                owner_birth=_birth(epoch.owner_birth),contract_sha256=_sha(epoch.contract_sha256),
                child=_birth(epoch.child),token=_token(epoch.token,catalogues),request_anchor=epoch.request_anchor,
                session_before=session_before(epoch.session_before),components=components,stage=epoch.stage,
                archived=epoch.archived,first_session=epoch.first_session)
            return number
        current=[dict(key=_key(k,catalogues),epoch=epoch_ref(v))for k,v in sorted(epochs.current.items())]
        history_refs=[epoch_ref(v)for v in epochs.history]
        pending=[]
        for key,p in sorted(epochs.pending.items()):
            _check_budget(read_budget,core)
            need(type(p)is Pending,'SDK_EPOCH_CONTROL_EXACT_PENDING_DATACLASS')
            pending.append(dict(key=_key(key,catalogues),epoch=epoch_ref(p.epoch),previous=epoch_ref(p.previous),
                control=copy.deepcopy(checked_control(p.control))))
        def session_map(mapping):
            result=[]
            for key,epoch in mapping.items():
                _check_budget(read_budget,core)
                need(type(key)is tuple and len(key)==2,'SDK_EPOCH_CONTROL_SESSION_SLOT_KEY')
                result.append(dict(key=_key(key[0],catalogues),session=sid_ref(key[1]),epoch=epoch_ref(epoch)))
            return sorted(result,key=lambda r:(r['key'],r['session']['session_sha256']))
        prepared,bound=session_map(epochs.session_prepared),session_map(epochs.session_bound)
        clis=[]
        for key,cli in sorted(bridge.clis.items()):
            _check_budget(read_budget,core)
            need(type(cli)is dict and set(cli)=={'token','birth','raw_birth','archived','end_lease'} and
                 type(cli['archived'])is bool,'SDK_EPOCH_CONTROL_ORIGINAL_CLI_RECORD_FIELDS')
            lease=cli['end_lease'];need(lease is None or type(lease)is Lease,'SDK_EPOCH_CONTROL_ORIGINAL_LEASE_ONLY')
            if lease is not None:
                need(type(lease.operation_id)is str and len(lease.operation_id)==32 and lease.role==key[1] and
                     lease.action in ('BIRTH','SESSION_REPLACE','NATIVE_END') and type(lease.epoch_before)is int and
                     lease.epoch_before>=0,'SDK_EPOCH_CONTROL_TYPED_ORIGINAL_LEASE_CONTROL')
            clis.append(dict(key=_key(key,catalogues),token=_token(cli['token'],catalogues),birth=_birth(cli['birth']),
                raw_birth=_sha(cli['raw_birth']),archived=cli['archived'],end_lease=None if lease is None else asdict(lease),
                source_cli_record_ordinal=len(clis),source_owner_birth=_birth(epochs.owner),
                original_object_identity_transfer_implemented=False))
        logical=[dict(key=_key(k,catalogues),raw_birth=_sha(v))for k,v in sorted(bridge.logical.items())]
        finished=[_token(v,catalogues)for v in sorted(bridge.finished)]
        # Original COUNT code on independent bounded RO metadata view, never SQL
        # under the live scientific RLock or configuration of its connection.
        with B.readonly(core.ledger.home/'ledger.sqlite',read_budget,
                lambda:_check_budget(read_budget,core))as readonly:
            lv=Ledger.__new__(Ledger);lv.db,lv.mutex=readonly,threading.RLock()
            ev=NativeSdkStartupEpochs.__new__(NativeSdkStartupEpochs);ev.core=SimpleNamespace(ledger=lv)
            counts=dict(all_original_request_rows=ev._requests_all(),
                by_registered_epoch_role=[dict(key=_key(k,catalogues),original_request_rows=ev._count(k))
                    for k in sorted(set(epochs.current)|set(epochs.pending))])
        _check_budget(read_budget,core)
        need(history.values==producer._domain_values() and producer.saved==values,
             'SDK_EPOCH_CONTROL_SESSION_DOMAIN_CHANGED_DURING_CAPTURE')
        section=dict(schema=SCHEMA,component_source_sha256=file_sha(__file__),source_pins=dict(PINS),
            source_owner_birth=_birth(epochs.owner),contract_sha256=epochs.sha,catalogues=catalogues,
            full_used_domain=dict(directory=dict(path=str(producer.directory),**U.identity(producer.directory.lstat())),
                source_binding_sha256=digest(history.binding),record_sequence=history.sequence,
                record_sha256=history.record_sha256,full_used_sha256=digest(list(values)),used_count=len(values)),
            epoch_objects=epoch_objects,current=current,history=history_refs,pending=pending,
            partial=[_key(k,catalogues)for k in sorted(epochs.partial)],
            session_prepared=prepared,session_bound=bound,
            current_original_session_pairs=[dict(key=_key(k,catalogues),session=session_before(epochs._session(k)))
                for k in sorted(epochs.current)],
            bridge=dict(uid=bridge.uid,clis=clis,logical=logical,finished=finished),counts=counts,
            unresolved_session_references=sorted(set(unresolved)),raw_SID_exported=False,
            science_SDK_body_or_archive_read=False,new_SID_or_session_allocated=False,
            whole_normal_seal_issuer_or_verifier_present=False,NEW_owner_registration_implemented=False,
            runtime_ready=False,actual_strict_SDK_load_qualified=False)
    _check_budget(read_budget,core);return section


def capture_OWN_components(epochs,bridge,producer,*,read_budget):
    need(epochs.core.qualification_only is True and all(t.startswith('OWN-')for t in epochs.core.rows),
         'SDK_EPOCH_CONTROL_EXPLICIT_OWN_METADATA_PORT_ONLY')
    section=_capture(epochs,bridge,producer,read_budget=read_budget)
    section['normal_six_cut_observation']=dict(actual_six_graph_qualified=False,scope='OWN_CONTROL_COMPONENT_ONLY')
    return section


def _normal_observation(owner):
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from normal_cold_barrier import NormalCheckpointBarrier,HELD_PHASES
    from native_dynamic_checkpoint import DynamicCheckpointPorts
    core=owner.core;barrier=core.normal_cold_barrier
    need(type(owner)is NativeColdOwner and type(core)is OriginalRelayCore and
         type(barrier)is NormalCheckpointBarrier and barrier.owner is owner and
         barrier.core is core and owner.normal_cold_barrier is barrier and not core.qualification_only,
         'SDK_EPOCH_CONTROL_ORIGINAL_NORMAL_SIX_SOURCE_GRAPH')
    barrier._current()
    need(barrier.state=='SIX_FROZEN_CUTS_OBSERVED_NO_WHOLE_SEAL_AUTHORITY' and
         barrier.last_static_observation is True and barrier.requested and barrier.failure is None and
         len(core.rows)==len(barrier.checkpoints)==len(barrier.observed)==6,
         'SDK_EPOCH_CONTROL_PRIOR_ORIGINAL_NORMAL_SIX_OBSERVATION_REQUIRED')
    result={}
    for t,(cp,_,_)in sorted(barrier.checkpoints.items()):
        need(type(cp)is DynamicCheckpointPorts and cp.core is core and cp.t==t and cp.state in HELD_PHASES and
             cp.writer is not None and cp.writer.writer_fence.state=='PARKED' and cp.reference==cp.writer.reference,
             'SDK_EPOCH_CONTROL_ALL_ORIGINAL_NORMAL_WRITERS_STILL_HELD')
        # Already-observed original control values only. No new CAS/archive,
        # scientific graph traversal, physical projection or snapshot capture.
        obs=barrier.observed[t]
        need(obs['original_frozen_checkpoint_verified']is True and obs['snapshot_sha256']==cp.reference['sha256'],
             'SDK_EPOCH_CONTROL_SAME_OBSERVED_ORIGINAL_REFERENCE')
        result[t]=dict(phase=cp.state,snapshot_sha256=cp.reference['sha256'],generation=obs['generation'],target=obs['target'])
    return result


def capture_registered(owner,*,read_budget):
    """Fixed production prospective capture API; not whole-seal consumption.

    Caller must already be on the sole original owner loop AFTER six-cut barrier
    observation. We never re-read SDK/private/science archives to invent proof.
    """
    verify_sources();_check_budget(read_budget,owner.core)
    before=_normal_observation(owner);core=owner.core
    section=_capture(core.native_sdk_startup_epochs,core.bridge_owner,core.formal_full_used_domain,read_budget=read_budget)
    need(before==_normal_observation(owner),'SDK_EPOCH_CONTROL_NORMAL_HELD_SOURCE_CHANGED_WAIT')
    section['normal_six_cut_observation']=dict(actual_six_graph_qualified=False,
        scope='CAPTURE_OF_EXISTING_ORIGINAL_OBSERVATION_NOT_NEW_PHYSICAL_OR_WHOLE_SEAL_PROOF',tracks=before)
    return section


@dataclass(frozen=True,repr=False)
class CapturedCliControl:
    key:tuple
    token:tuple
    birth:ProcessBirth
    raw_birth:str
    archived:bool
    end_lease:object
    source_owner_birth:ProcessBirth
    source_cli_record_ordinal:int


@dataclass(frozen=True,repr=False)
class OriginalEpochMetadataTransfer:
    source_section_sha256:str
    source_owner_birth:ProcessBirth
    reconstructed_in_birth:ProcessBirth
    epochs:tuple
    current:dict
    history:tuple
    pending:dict
    partial:frozenset
    session_prepared:dict
    session_bound:dict
    current_original_session_pairs:dict
    clis:tuple
    logical:dict
    finished:frozenset

    def public(self):
        return dict(schema='count14-native-sdk-epoch-cli-control-transfer-PUBLIC-v1',
            source_section_sha256=self.source_section_sha256,epoch_objects=len(self.epochs),
            current_roles=len(self.current),history_references=len(self.history),pending_controls=len(self.pending),
            CLI_controls=len(self.clis),original_dataclass_control_graph_reconstructed=True,
            raw_SID_exported=False,source_CLI_object_identity_transferred=False,
            NEW_owner_runtime_registration=False,actual_strict_SDK_load_qualified=False,runtime_ready=False)


def reconstruct_metadata(section,*,full_used_producer,read_budget):
    """Detached original control dataclasses ONLY, resolved by original history.

    Never rewrites owner_birth/provenance or installs epochs/CLI/session state.
    Returning these values is NOT permission for NEW-owner SDK consumption.
    """
    verify_sources();producer=full_used_producer
    need(type(producer)is FullUsedDomainProducer and section['schema']==SCHEMA and
         section['source_pins']==PINS and section['component_source_sha256']==file_sha(__file__),
         'SDK_EPOCH_CONTROL_FIXED_COMPONENT_SCHEMA_AND_SOURCE')
    # Use registered producer's same-science-mutex graph solely for IO guard;
    # no new runtime/source object gets a back-reference or changed field.
    class ReadGraph: pass
    view=ReadGraph();view.directory,view.fd=producer.directory,producer.fd
    core=ReadGraph();core.ledger=ReadGraph();core.ledger.mutex=producer.science_mutex
    view._epoch_control_capture_core=core
    with producer._operation():
        producer._require_saved(producer._domain_values())
        h=_history(view,read_budget);saved=section['full_used_domain']
        need(saved==dict(directory=dict(path=str(producer.directory),**U.identity(producer.directory.lstat())),
             source_binding_sha256=digest(h.binding),record_sequence=h.sequence,record_sha256=h.record_sha256,
             full_used_sha256=digest(list(h.values)),used_count=len(h.values)),
             'SDK_EPOCH_CONTROL_EXACT_ORIGINAL_REGISTERED_SESSION_HISTORY_LOCATOR')
        def sid(ref):
            need(ref['state']=='ORIGINAL_FULL_USED_DOMAIN_LOCATOR',
                 'SDK_EPOCH_CONTROL_UNRESOLVED_SESSION_DOMAIN_REFERENCE_WAIT')
            i=ref['index'];need(type(i)is int and 0<=i<len(h.values),'SDK_EPOCH_CONTROL_SESSION_DOMAIN_INDEX')
            value=h.values[i]
            need(hashlib.sha256(value.encode()).hexdigest()==ref['session_sha256'],
                 'SDK_EPOCH_CONTROL_SESSION_DOMAIN_HASH');return value
        def pair(ref):
            if ref['state']=='ORIGINAL_ABSENT':return None
            need(ref['state']=='ORIGINAL_SESSION_PAIR','SDK_EPOCH_CONTROL_UNRESOLVED_SESSION_BEFORE_WAIT')
            return _sha(ref['anonymous_birth_sha256']),sid(ref['session'])
        def token(value):return tuple(value[0]),value[1],value[2],value[3]
        epochs=[]
        for r in section['epoch_objects']:
            components=tuple(Component(c['component'],c['cid'],c['image_id'],U.birth(c['init_birth']),c['domain'],
                c['device'],c['inode'],tuple(U.birth(b)for b in c['controls']),tuple(U.birth(b)for b in c['sdk']))
                for c in r['components'])
            epochs.append(Epoch(r['trajectory'],r['role'],r['ordinal'],U.birth(r['owner_birth']),r['contract_sha256'],
                U.birth(r['child']),token(r['token']),r['request_anchor'],pair(r['session_before']),components,
                r['stage'],r['archived'],r['first_session']))
        def at(index):
            if index is None:return None
            need(type(index)is int and 0<=index<len(epochs),'SDK_EPOCH_CONTROL_EPOCH_REFERENCE');return epochs[index]
        current={tuple(r['key']):at(r['epoch'])for r in section['current']}
        history=tuple(at(i)for i in section['history'])
        pending={tuple(r['key']):Pending(at(r['epoch']),at(r['previous']),copy.deepcopy(checked_control(r['control'])))
            for r in section['pending']}
        def slots(rows):return {(tuple(r['key']),sid(r['session'])):at(r['epoch'])for r in rows}
        prepared,bound=slots(section['session_prepared']),slots(section['session_bound'])
        pairs={tuple(r['key']):pair(r['session'])for r in section['current_original_session_pairs']}
        clis=tuple(CapturedCliControl(tuple(r['key']),token(r['token']),U.birth(r['birth']),r['raw_birth'],r['archived'],
            None if r['end_lease']is None else Lease(**r['end_lease']),U.birth(r['source_owner_birth']),
            r['source_cli_record_ordinal'])for r in section['bridge']['clis'])
        result=OriginalEpochMetadataTransfer(digest(section),U.birth(section['source_owner_birth']),process_birth(os.getpid()),
            tuple(epochs),current,history,pending,frozenset(tuple(k)for k in section['partial']),prepared,bound,pairs,clis,
            {tuple(r['key']):r['raw_birth']for r in section['bridge']['logical']},
            frozenset(token(v)for v in section['bridge']['finished']))
    return result


def write_candidate(path,section):
    path=Path(path);s=path.parent.lstat()
    need(path.name=='NATIVE_SDK_EPOCH_CONTROL.json' and path.is_absolute() and path.parent.resolve()==path.parent and
         not path.exists() and not path.is_symlink() and s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o700 and
         section['schema']==SCHEMA,'SDK_EPOCH_CONTROL_NEW_PRIVATE_REGISTERED_CONTROL_ONLY')
    raw=wire(section);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(directory)
    finally:os.close(directory)
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest())


def read_candidate(path,pin):
    need(Path(path).name=='NATIVE_SDK_EPOCH_CONTROL.json','SDK_EPOCH_CONTROL_FIXED_REGISTERED_CANDIDATE_BASENAME')
    value,_=U.private_read(path,pin)
    need(value['schema']==SCHEMA,'SDK_EPOCH_CONTROL_FIXED_CANDIDATE_SCHEMA');return value


def consume_into_NEW_owner(*args,trusted_normal_seal=None,**kwargs):
    if trusted_normal_seal is None:raise EpochControlWait('SDK_EPOCH_CONTROL_MISSING_NORMAL_WHOLE_SEAL_WAIT')
    raise EpochControlWait('SDK_EPOCH_CONTROL_NO_REGISTERED_NORMAL_ISSUER_VERIFIER_OR_NEW_OWNER_TRANSFER_API_WAIT')
