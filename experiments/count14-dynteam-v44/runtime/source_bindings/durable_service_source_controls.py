"""Append-only retired-service control supplement bound to original INERT T.

Source is the exact sealed same-birth live control cap, never a caller dict.
Receiver needs original typed T + actual metadata pair/new birth/three original
locks + fixed financial equations. This is control metadata, not writer/TERM/
model authority; no constructors, request cancellation, replay or schema edits.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import importlib
import os

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth

SCHEMA='count14-retired-services-durable-source-control-v1'
COMMITTED='count14-retired-services-durable-source-ISSUED-v1'
LEAF='normal-retired-services-source-control-v1'
OWN_LEAF='OWN-normal-retired-services-source-control-v1'
PINS=dict(
    financial_runtime_source_control='5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906',
    source_services_retirement='084a59c44b0bfe49cca9c138472bda76575cd52a24fbed569f0b8f765aaa1887',
    source_services_controls='f7c72e41dc7df2940917ad664d582308ab936387c0b5190a21e2c07bac2d55db',
    normal_inert_cut='aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',
    metadata_inert_pair='83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da')
_SEAL=object()
_PUBLICATIONS={}
COMPONENTS=frozenset(('SYSTEM','resource','membership_fences'))


def verify_sources():
    for name,pin in PINS.items():
        p=Path(importlib.import_module(name).__file__)
        M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and
               hashlib.sha256(p.read_bytes()).hexdigest()==pin,
               'DURABLE_SERVICES_EXACT_FROZEN_SOURCE_COMPONENTS')
    return dict(PINS)


def _self_pin():
    p=Path(__file__)
    M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and
           p.name=='durable_service_source_controls.py','DURABLE_SERVICES_FIXED_SOURCE_IMPLEMENTATION')
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _budget(value):
    M.need(type(value)is ReadBudget,'DURABLE_SERVICES_FINITE_METADATA_BUDGET')
    value.check()


def _save(path,body):
    from normal_cold_sealer import save_candidate
    return save_candidate(path,body)


def _complete(leaf,body,*,final_guard):
    leaf.mkdir(mode=0o700,parents=False,exist_ok=False)
    body=dict(body,source_directory=M.descriptor(leaf),source_module_sha256=_self_pin(),
        source_pins=verify_sources(),inert_only=True,safe_to_TERM=False,
        paid_activation_authorized=False,whole_runnable_ready=False)
    reference=_save(leaf/'SOURCE.json',body)
    final_guard() # a changed source leaves a non-consumable partial, never retry/overwrite
    marker=dict(schema=COMMITTED,OWN=body['OWN'],source_identity=reference['identity'],
        source_sha256=reference['sha256'],source_module_sha256=body['source_module_sha256'],
        old_owner_birth=body['old_owner_birth'],inert_only=True,safe_to_TERM=False,
        paid_activation_authorized=False,whole_runnable_ready=False)
    issued=_save(leaf/'ISSUED.json',marker)
    fd=os.open(leaf.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(path=reference['identity']['path'],sha256=reference['sha256'],
        issued_identity=issued['identity'],issued_sha256=issued['sha256'],
        inert_only=True,safe_to_TERM=False,paid_activation_authorized=False,whole_runnable_ready=False)


def _live_source_cap(source_cap,core,*,budget,own):
    import source_services_controls as S
    M.need(type(source_cap)is S.RetiredServiceSourceControls and source_cap.OWN is own,
           'DURABLE_SERVICES_SOURCE_ONLY_EXACT_SEALED_RETIRED_SERVICE_CAPABILITY')
    S.verify_registered_source(source_cap,core=core,read_budget=budget)
    M.need(source_cap.source_birth==process_birth(os.getpid()),
           'DURABLE_SERVICES_SOURCE_CAP_EXACT_CURRENT_SOURCE_BIRTH')
    return source_cap.snapshot()


def publish_source(owner,*,source_cap,read_budget):
    """True production source, once AFTER normal services retired + T issued."""
    import financial_runtime_source_control as F
    _budget(read_budget);verify_sources()
    issuer,ticket_body,storage,locks,retirement=F._source(owner,read_budget)
    core=owner.core
    M.need(id(owner)not in _PUBLICATIONS,'DURABLE_SERVICES_SINGLE_SOURCE_PUBLICATION_NO_RETRY')
    before=_live_source_cap(source_cap,core,budget=read_budget,own=False)
    db=F._db_controls(Path(storage['ledger_database']['path']),Path(storage['queue_database']['path']),read_budget)
    after=_live_source_cap(source_cap,core,budget=read_budget,own=False)
    M.need(before==after,'DURABLE_SERVICES_SOURCE_FIELDS_CHANGED_WAIT')
    body=dict(schema=SCHEMA,OWN=False,old_owner_birth=asdict(source_cap.source_birth),
        contract_sha256=issuer.source.source_binding,storage=storage,locks=[[k,r]for k,r in locks],
        original_ticket=dict(path=issuer.ticket.path,sha256=issuer.ticket.sha256,identity=M.descriptor(issuer.ticket.path)),
        original_financial_metadata=copy.deepcopy(ticket_body['financial_metadata']),
        original_transport_retirement=retirement,current_fixed_db_controls=db,
        stable_before_after_controls=True,source_controls=before,source_controls_sha256=M.digest(before),
        source_capability_type='source_services_controls.RetiredServiceSourceControls',
        actual_production_issued_T_and_registered_live_service_cap=True)
    def guard():
        current,tb,ss,ll,rr=F._source(owner,read_budget)
        M.need(current is issuer and tb==ticket_body and ss==storage and ll==locks and rr==retirement and
               _live_source_cap(source_cap,core,budget=read_budget,own=False)==before and
               F._db_controls(Path(storage['ledger_database']['path']),Path(storage['queue_database']['path']),read_budget)==db,
               'DURABLE_SERVICES_POST_SOURCE_WRITE_CHANGED_RETAIN_PARTIAL')
    _PUBLICATIONS[id(owner)]=dict(owner=owner,publication_started=True)
    result=_complete(core.home/LEAF,body,final_guard=guard)
    _PUBLICATIONS[id(owner)]['reference']=copy.deepcopy(result)
    return result


class NativeServiceSourceReference:
    """Unverified reference. Cannot authorize any receiver action."""
    __slots__=('_path','_pin','_seal')
    def __init__(self,*args,**kwargs):raise M.PaidColdWait('DURABLE_SERVICES_ONLY_FIXED_REFERENCE_LOADER')
    def __setattr__(self,name,value):
        M.need(not hasattr(self,'_seal'),'DURABLE_SERVICES_REFERENCE_IMMUTABLE')
        object.__setattr__(self,name,value)
    @property
    def path(self):return self._path
    @property
    def sha256(self):return self._pin


class OWNServiceSourceReference(NativeServiceSourceReference):
    __slots__=()


def _reference(path,pin,*,own):
    p=Path(path)
    M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and p.name=='SOURCE.json'and
           p.parent.name==(OWN_LEAF if own else LEAF),
           'DURABLE_SERVICES_FIXED_REFERENCE_PATH_BEFORE_ANY_READ')
    value=object.__new__(OWNServiceSourceReference if own else NativeServiceSourceReference)
    value._path,value._pin,value._seal=str(p),M.sha(pin),_SEAL
    return value


def load_reference(path,sha256):return _reference(path,sha256,own=False)
def load_OWN_reference(path,sha256):return _reference(path,sha256,own=True)


def _read_complete(reference,home,*,own,budget):
    _budget(budget);verify_sources()
    M.need(type(reference)is(OWNServiceSourceReference if own else NativeServiceSourceReference)and
           reference._seal is _SEAL and Path(reference.path)==home/(OWN_LEAF if own else LEAF)/'SOURCE.json',
           'DURABLE_SERVICES_EXACT_REFERENCE_NAMESPACE_AND_T_DERIVED_HOME')
    M.existing(M.descriptor(home),directory=True,private=True)
    leaf=home/(OWN_LEAF if own else LEAF)
    try:
        M.existing(M.descriptor(leaf),directory=True,private=True)
        marker,marker_pin=M.private_read(leaf/'ISSUED.json',limit=262144)
    except FileNotFoundError:
        raise M.PaidColdWait('DURABLE_SERVICES_WAIT_COMPLETE_SOURCE_AND_ISSUED')from None
    M.need(type(marker)is dict and set(marker)=={'schema','OWN','source_identity','source_sha256',
        'source_module_sha256','old_owner_birth','inert_only','safe_to_TERM','paid_activation_authorized','whole_runnable_ready'}and
        marker['schema']==COMMITTED and marker['OWN']is own and marker['source_module_sha256']==_self_pin()and
        marker['source_identity']['path']==reference.path and marker['source_sha256']==reference.sha256 and
        marker['inert_only']is True and marker['safe_to_TERM']is marker['paid_activation_authorized']is marker['whole_runnable_ready']is False,
        'DURABLE_SERVICES_FIXED_O_EXCL_COMPLETE_MARKER_NOT_AUTHORITY')
    path=M.existing(marker['source_identity'],private=True)
    body,pin=M.private_read(path,reference.sha256,limit=8*1024*1024)
    M.need(type(body)is dict and body['schema']==SCHEMA and body['OWN']is own and
        body['source_module_sha256']==_self_pin()and body['source_pins']==PINS and
        body['source_directory']==M.descriptor(leaf)and body['storage']['owner_home']==M.descriptor(home)and
        body['old_owner_birth']==marker['old_owner_birth']and body['stable_before_after_controls']is True and
        body['source_controls_sha256']==M.digest(body['source_controls'])and
        body['source_capability_type']=='source_services_controls.RetiredServiceSourceControls'and
        body['inert_only']is True and body['safe_to_TERM']is body['paid_activation_authorized']is body['whole_runnable_ready']is False,
        'DURABLE_SERVICES_HASHED_COMPLETE_CONTROL_ENVELOPE')
    _validate_controls(body['source_controls'],body,own=own)
    return body,dict(path=str(path),sha256=pin,identity=M.descriptor(path),
        issued_identity=M.descriptor(leaf/'ISSUED.json'),issued_sha256=marker_pin)


def _validate_controls(controls,body,*,own):
    M.need(type(controls)is dict and controls['schema']=='count14-retired-native-service-and-fence-source-controls-v1'and
        controls['OWN']is own and controls['source_owner_birth']==body['old_owner_birth']and
        controls['receiver_or_new_owner_verified']is False and controls['raw_request_session_key_and_body_excluded']is True and
        controls['safe_to_TERM']is controls['paid_activation_authorized']is controls['whole_runnable_ready']is False,
        'DURABLE_SERVICES_FIXED_SAME_SOURCE_CONTROL_NAMESPACE')
    physical=controls['physical_service_retirement']
    M.need(physical['schema']=='count14-normal-source-services-retired-subset-v1'and physical['OWN']is own and
        physical['owner_birth']==body['old_owner_birth']and physical['native_control_listener_and_handlers_ended']is True and
        physical['original_control_close_calls']==1 and physical['control_close_job_alive']is False and
        physical['publisher_synchronous']is True and physical['publisher_instance_retained']is True and
        physical['journal_connections_retained_for_post_capture']is True and
        physical['CLI_retired']is physical['SDK_retired']is physical['safe_to_TERM']is physical['whole_runnable_ready']is False and
        all(r['pending']==0 and r.get('unresolved',0)==0 for r in physical['inbox_counts'].values())and
        all(r['closed']is True and r['stop_set']is True and r['thread_alive']is False
            and type(r['sequence'])is int and r['sequence']>=0 for r in physical['clocks'].values()),
        'DURABLE_SERVICES_SOURCE_PHYSICAL_SERVICE_SUBSET_TRULY_RETIRED_NOT_WHOLE')
    for name in ('SYSTEM','resource'):
        row=controls[name];ph=physical[name]
        M.need(type(row['registered'])is bool and row['registered']is ph['registered'],
               'DURABLE_SERVICES_ORIGINAL_SERVICE_PRESENCE_NOT_DEFAULT_ZERO')
        if not row['registered']:
            M.need(row==dict(registered=False,configuration=None,records=None)and
                ph['original_public']is ph['records']is ph['child_handles']is ph['live_children']is ph['physical_clear']is None,
                'DURABLE_SERVICES_ABSENT_COMPONENT_EXPLICIT_UNKNOWN_NOT_EMPTY')
            continue
        M.need(row['source_owner_birth']==body['old_owner_birth']and row['configuration']['accepting']is False and
            row['configuration']['contract_sha256']==body['contract_sha256']and
            row['original_public']==ph['original_public']and len(row['records'])==ph['records']and
            ph['live_children']==0 and ph['physical_clear']is True and row['constructor_restarted']is False,
            'DURABLE_SERVICES_REGISTERED_ORIGINAL_CONFIG_COUNTERS_AND_PHYSICAL_CLEAR')
    M.need(type(controls['membership_fences'])is dict and
        set(controls['membership_fences'])==set(physical['clocks']),
        'DURABLE_SERVICES_COMPLETE_ORIGINAL_FENCE_AND_CLOCK_ROLE_DOMAINS')


class VerifiedRetiredServiceControls:
    __slots__=('_body','_reference','_controls','_seal','OWN','old_owner_birth','new_owner_birth',
               'contract_sha256','lock_fds')
    def __init__(self,*args,**kwargs):raise M.PaidColdWait('DURABLE_SERVICES_ONLY_FIXED_NEW_BIRTH_VERIFIER')
    def __setattr__(self,name,value):
        M.need(not hasattr(self,'_seal'),'DURABLE_SERVICES_VERIFIED_CONTROL_CAPABILITY_IMMUTABLE')
        object.__setattr__(self,name,value)
    def snapshot(self):
        M.need(self._seal is _SEAL,'DURABLE_SERVICES_FIXED_VERIFIED_CONTROL_SEAL')
        return copy.deepcopy(self._controls)
    def component(self,name):
        M.need(name in COMPONENTS,'DURABLE_SERVICES_FIXED_CONTROL_COMPONENT_NAME')
        return self.snapshot()[name]
    @property
    def safe_to_TERM(self):return False
    @property
    def paid_activation_authorized(self):return False
    @property
    def whole_runnable_ready(self):return False


def _verified(body,reference,proof,*,own):
    value=object.__new__(VerifiedRetiredServiceControls)
    value._body,value._reference=copy.deepcopy(body),copy.deepcopy(reference)
    value._controls=copy.deepcopy(body['source_controls'])
    value.OWN,value.old_owner_birth,value.new_owner_birth=own,proof.source_birth,proof.new_owner_birth
    value.contract_sha256,value.lock_fds=body['contract_sha256'],tuple(proof.lock_fds)
    value._seal=_SEAL;return value


def _verify_common(reference,owner,ticket,*,read_budget,own):
    import normal_inert_cut as T
    import metadata_inert_pair as P
    import financial_runtime_source_control as F
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    _budget(read_budget);verify_sources()
    M.need(type(reference)is(OWNServiceSourceReference if own else NativeServiceSourceReference)and
        reference._seal is _SEAL and type(ticket)is(T.OWNNormalInertTicket if own else T.NormalInertTicket)and
        type(owner)is NativeColdOwner and type(owner.core)is OriginalRelayCore,
        'DURABLE_SERVICES_FIXED_TYPED_T_PAIR_AND_REFERENCE_NAMESPACE')
    M.need(not owner.core.ledger.mutex._is_owned()and not owner.core.queue.mutex._is_owned(),
        'DURABLE_SERVICES_RECEIVER_METADATA_IO_OUTSIDE_SCIENCE_LOCKS')
    cap=(T.verify_OWN_inert_ticket if own else T.verify_inert_ticket)(ticket,owner=owner,read_budget=read_budget)
    proof=(P.verify_OWN_registered_pair(owner,read_budget=read_budget)if own else
        P.verify_registered_pair(owner,ticket=ticket,read_budget=read_budget))
    M.need(type(cap)is T.VerifiedNormalInertCut and type(proof)is P.VerifiedMetadataPair and cap.OWN is own and
        proof.qualification_only is own and cap.old_owner_birth==proof.source_birth and
        cap.new_owner_birth==proof.new_owner_birth==process_birth(os.getpid())and
        cap.old_owner_birth!=cap.new_owner_birth,
        'DURABLE_SERVICES_TRUE_NEW_BIRTH_AND_SOURCE_BOUND_ORIGINAL_PAIR')
    pair=owner.core.metadata_inert_pair;material=proof.material
    home=M.existing(cap.owner_home,directory=True,private=True)
    if own:M.need(home.name.startswith('OWN-'),'DURABLE_SERVICES_OWN_ONLY_SANDBOX_HOME')
    else:M.need(home==owner.core.home==Path(material['contract']['arms'][0]['root'])/'owner'and
        home.is_relative_to((_C14_SCRATCH)),'DURABLE_SERVICES_FIXED_REGISTERED_HOME_NOT_CALLER_PATH')
    body,record=_read_complete(reference,home,own=own,budget=read_budget)
    original=T._read_reference(ticket,own=own,read_budget=read_budget)
    M.need(body['actual_production_issued_T_and_registered_live_service_cap']is(not own)and
        body['old_owner_birth']==asdict(cap.old_owner_birth)and body['contract_sha256']==cap.contract_sha256 and
        body['original_ticket']==dict(path=ticket.path,sha256=ticket.sha256,identity=M.descriptor(ticket.path))and
        body['original_financial_metadata']==material['financial_metadata']==original['financial_metadata']and
        body['locks']==[[kind,row]for kind,row in pair.control_lock_records]and
        all(body['storage'][key]==material[key]for key in
            ('owner_home','ledger_home','ledger_database','queue_home','queue_database','full_used_directory')),
        'DURABLE_SERVICES_ORIGINAL_T_RAW_BIRTH_THREE_LOCKS_STORAGE_FINANCIAL_BINDING')
    if not own:M.need(body['original_transport_retirement']==original['transport_retirement'],
        'DURABLE_SERVICES_ORIGINAL_T_RETIRED_HTTP_BINDING')
    else:M.need(body['original_transport_retirement']is None,
        'DURABLE_SERVICES_OWN_NEVER_PRETEND_PRODUCTION_SIX_HTTP_RETIREMENT')
    T._validate_owned_locks(pair.lock_fds,[row for kind,row in pair.control_lock_records])
    db=F._db_controls(Path(material['ledger_database']['path']),Path(material['queue_database']['path']),read_budget)
    M.need(db==body['current_fixed_db_controls'],
        'DURABLE_SERVICES_CURRENT_FIXED_FINANCIAL_SCHEMA_QUEUE_MODEL_EQUATIONS_EQUAL')
    again=(T.verify_OWN_inert_ticket if own else T.verify_inert_ticket)(ticket,owner=owner,read_budget=read_budget)
    M.need(again.old_owner_birth==cap.old_owner_birth and again.new_owner_birth==cap.new_owner_birth and
        _read_complete(reference,home,own=own,budget=read_budget)==(body,record),
        'DURABLE_SERVICES_FIXED_SOURCE_FILE_AND_PAIR_RECHECK_STILL_EQUAL')
    return _verified(body,record,proof,own=own)


def verify_reference(reference,*,owner,ticket,read_budget):
    return _verify_common(reference,owner,ticket,read_budget=read_budget,own=False)


def verify_OWN_reference(reference,*,owner,ticket,read_budget):
    return _verify_common(reference,owner,ticket,read_budget=read_budget,own=True)


def publish_OWN_source(core,*,source_cap,ticket,full_used_directory,full_used_fd,read_budget):
    """Actual OWN source/control cap + issued OWN T; never production source."""
    import financial_runtime_source_control as F
    import normal_inert_cut as T
    from original_relay_core import OriginalRelayCore
    _budget(read_budget);verify_sources()
    M.need(type(core)is OriginalRelayCore and core.qualification_only is True and
        core.home.name.startswith('OWN-')and type(ticket)is T.OWNNormalInertTicket and
        id(core)not in _PUBLICATIONS,'DURABLE_SERVICES_EXPLICIT_OWN_SOURCE_NAMESPACE_NO_RETRY')
    tb=T._read_reference(ticket,own=True,read_budget=read_budget)
    storage,locks=F._source_storage(core,core.queue,full_used_directory,full_used_fd)
    before=_live_source_cap(source_cap,core,budget=read_budget,own=True)
    M.need(tb['old_owner_birth']==asdict(source_cap.source_birth)and tb['contract_sha256']==M.digest(core.contract)and
        all(tb[key]==value for key,value in storage.items())and
        tb['locks']==[[kind,row]for kind,row in locks],
        'DURABLE_SERVICES_OWN_REAL_ISSUED_T_SAME_SOURCE_STORAGE_THREE_LOCKS')
    db=F._db_controls(Path(storage['ledger_database']['path']),Path(storage['queue_database']['path']),read_budget)
    body=dict(schema=SCHEMA,OWN=True,old_owner_birth=asdict(source_cap.source_birth),
        contract_sha256=M.digest(core.contract),storage=storage,locks=[[k,r]for k,r in locks],
        original_ticket=dict(path=ticket.path,sha256=ticket.sha256,identity=M.descriptor(ticket.path)),
        original_financial_metadata=copy.deepcopy(tb['financial_metadata']),original_transport_retirement=None,
        current_fixed_db_controls=db,stable_before_after_controls=True,source_controls=before,
        source_controls_sha256=M.digest(before),source_capability_type='source_services_controls.RetiredServiceSourceControls',
        actual_production_issued_T_and_registered_live_service_cap=False)
    def guard():
        ss,ll=F._source_storage(core,core.queue,full_used_directory,full_used_fd)
        M.need(ss==storage and ll==locks and T._read_reference(ticket,own=True,read_budget=read_budget)==tb and
            _live_source_cap(source_cap,core,budget=read_budget,own=True)==before and
            F._db_controls(Path(storage['ledger_database']['path']),Path(storage['queue_database']['path']),read_budget)==db,
            'DURABLE_SERVICES_OWN_SOURCE_CHANGED_RETAIN_PARTIAL')
    _PUBLICATIONS[id(core)]=dict(core=core,publication_started=True)
    result=_complete(core.home/OWN_LEAF,body,final_guard=guard)
    _PUBLICATIONS[id(core)]['reference']=copy.deepcopy(result)
    return result
