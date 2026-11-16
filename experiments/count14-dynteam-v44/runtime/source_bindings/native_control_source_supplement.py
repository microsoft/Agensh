"""Append-only original native spawn/logical control supplement, not science.

Source must still be the real old owner after its existing T/services durable
publication. Receiver reuses the original typed cross-birth services/T/three-
lock/fixed financial verifier. Source absent/missing state is WAIT, never a
ledger-derived spawn ordinal or empty-map guess. No model or SDK invocation.
"""
from dataclasses import asdict,dataclass
from pathlib import Path
from types import CodeType
import copy
import hashlib
import importlib
import os
import re

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
from original_relay_core import OriginalRelayCore
from native_spawn_owner import NativeSpawnOwner
from native_bridge_owner import NativeBridgeLifecycleOwner
from native_container_retirement import RetirementJob
from dynteam_membership_fence import Lease
import financial_runtime_source_control as F
import durable_service_source_controls as D
import native_control_whitelist_source as W
import native_infra_source_state as I

SCHEMA='count14-native-spawn-and-logical-source-supplement-v2'
CONTROL='count14-original-native-spawn-and-logical-controls-v2'
ISSUED='count14-native-spawn-and-logical-source-ISSUED-v2'
LEAF='normal-native-spawn-logical-source-control-v1'
OWN_LEAF='OWN-native-spawn-logical-control-component-v1'
PINS=dict(native_infra_source_state='65c49b23a1589ff0d14ca700eac9c4da45453bb2d8407e55f3d4545487e9e568',native_control_whitelist_source='9cbf5f9efe1719578c19b1749f19fc411561b9613c2430388272e226f2e7ea4f',financial_runtime_source_control='5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906',
 durable_service_source_controls='fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83',
 native_spawn_owner='352095fdfc7e1291e27ab86ab1a7ec8ba43304738d035041e66b7610f688c38a',
 native_bridge_owner='e3e2c6b41ee109a1483ee92e8820fda1ad3e186e82263968299bd848bedac346',
 native_container_retirement='9cba289507f8fe65da64b75d737595585e08a58241d1badda88effc9f43926a3')
_SEAL=object()
_CAPTURES={}
_PUBLICATIONS={}
_VERIFIED={}
_SOURCE_WHITELIST_OWNERS={}


def budget(value):
 M.need(type(value)is ReadBudget,'NATIVE_SUPPLEMENT_FINITE_CONTROL_READ_BUDGET');value.check()


def verify_sources():
 for name,pin in PINS.items():
  p=Path(importlib.import_module(name).__file__)
  M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and
   hashlib.sha256(p.read_bytes()).hexdigest()==pin,'NATIVE_SUPPLEMENT_EXACT_FROZEN_ORIGINAL_PINS')
 p=Path(importlib.import_module('native_spawn_owner').__file__)
 code=compile(p.read_bytes(),str(p),'exec',dont_inherit=True)
 cls=next(v for v in code.co_consts if type(v)is CodeType and v.co_name=='NativeSpawnOwner')
 original=next(v for v in cls.co_consts if type(v)is CodeType and v.co_name=='checkpoint_control_state')
 M.need(NativeSpawnOwner.checkpoint_control_state.__code__==original and
  NativeSpawnOwner.checkpoint_control_state.__globals__ is vars(importlib.import_module('native_spawn_owner')),
  'NATIVE_SUPPLEMENT_ORIGINAL_FIXED_PUBLIC_CHECKPOINT_CONTROL_METHOD_UNCHANGED')
 I.verify_sources();D.verify_sources();return dict(PINS)


def _unlocked(core):
 M.need(not core.ledger.mutex._is_owned()and not core.queue.mutex._is_owned(),
  'NATIVE_SUPPLEMENT_NO_CONTROL_IO_WHILE_HOLDING_SCIENCE_LOCK')


def _sha(value):
 M.need(type(value)is str and re.fullmatch('[0-9a-f]{64}',value),'NATIVE_SUPPLEMENT_FIXED_CONTROL_DIGEST')
 return value


def _token(value,rows):
 M.need(type(value)is tuple and len(value)==4 and type(value[0])is tuple and len(value[0])==2 and
  value[0][0]in rows and value[0][1]in rows[value[0][0]]['roles']and
  type(value[1])is int and value[1]>0 and type(value[2])is int and value[2]>0,
  'NATIVE_SUPPLEMENT_ORIGINAL_TYPED_NATIVE_CLI_TOKEN_ONLY')
 return dict(key=list(value[0]),namespace_pid=value[1],start_ticks=value[2],native_turn_sha256=_sha(value[3]))


def unpack_token(row):
 return (tuple(row['key']),row['namespace_pid'],row['start_ticks'],row['native_turn_sha256'])


def _controls(core,*,read_budget,own):
 budget(read_budget);_unlocked(core);verify_sources()
 M.need(type(core)is OriginalRelayCore and core.qualification_only is own and
  type(core.spawn_owner)is NativeSpawnOwner and core.spawn_owner.core is core and
  type(core.bridge_owner)is NativeBridgeLifecycleOwner and core.bridge_owner.core is core,
  'NATIVE_SUPPLEMENT_ACTUAL_ORIGINAL_SOURCE_NATIVE_COMPONENTS_NOT_CALLER_FLAGS')
 M.need((own and any(x.startswith('OWN-')for x in core.home.parts))or
  (not own and core.home==Path(core.contract['arms'][0]['root'])/'owner'),
  'NATIVE_SUPPLEMENT_ORIGINAL_SCOPE_HOME')
 spawn=core.spawn_owner;bridge=core.bridge_owner
 M.need(type(spawn.history)is dict and not spawn.history and not core.pending_native_launches,
  'NATIVE_SUPPLEMENT_WAIT_UNKNOWN_HISTORY_OR_PENDING_NATIVE_EFFECTS')
 public=spawn.checkpoint_control_state() # original fixed framework-control API
 M.need(type(public)is dict and set(public)=={'next_ordinals','used_slots','effects'}and
  set(public['next_ordinals'])==set(public['used_slots'])==set(core.rows),
  'NATIVE_SUPPLEMENT_ALL_ORIGINAL_TRAJECTORY_COUNTERS_NO_DEFAULTS')
 effects=[]
 for (t,n),value in sorted(spawn.operations.items()):
  read_budget.check()
  M.need(type(value)is dict and set(value)=={'lease','slot','reuse','committed','birth_observed','native_cli_token_sha256'}and
   type(value['lease'])is Lease and value['committed']is value['birth_observed']is True and
   value['lease'].role=='worker-'+str(value['slot']-1).zfill(2)and value['lease'].action=='BIRTH',
   'NATIVE_SUPPLEMENT_ONLY_ORIGINAL_COMMITTED_EFFECTS_AND_EXACT_LEASE_CONTROL')
  effects.append(dict(trajectory=t,ordinal=n,lease=asdict(value['lease']),slot=value['slot'],reuse=value['reuse'],
   committed=True,birth_observed=True,native_cli_token_sha256=_sha(value['native_cli_token_sha256'])))
 terminal=[]
 for operation_id,job in sorted(spawn.retirement_jobs.items()):
  read_budget.check()
  M.need(type(job)is RetirementJob and job.core is core and job.operation_id==operation_id and
   job.phase=='DONE'and job.index==2 and (job.child is None or job.child.poll()==0),
   'NATIVE_SUPPLEMENT_WAIT_UNPROVEN_NATIVE_RETIREMENT_JOB')
  terminal.append(dict(operation_id=operation_id,phase='DONE',index=2,child_terminal=True))
 logical=[]
 for (t,r),raw in sorted(bridge.logical.items()):
  M.need(t in core.rows and r in core.rows[t]['roles'],'NATIVE_SUPPLEMENT_EXACT_REGISTERED_LOGICAL_ROLE')
  logical.append(dict(trajectory=t,role=r,logical_birth_sha256=_sha(raw)))
 clis=[]
 for key,row in sorted(bridge.clis.items()):
  M.need(type(row)is dict and set(row)=={'token','birth','raw_birth','archived','end_lease'}and
   row['end_lease']is None and type(row['archived'])is bool,
   'NATIVE_SUPPLEMENT_ONLY_REGISTERED_CLI_CONTROL_AND_NO_PENDING_END_LEASE')
  clis.append(dict(key=list(key),token=_token(row['token'],core.rows),birth=asdict(row['birth']),
   logical_birth_sha256=_sha(row['raw_birth']),archived=row['archived']))
 value=dict(schema=CONTROL,OWN=own,source_owner_birth=asdict(process_birth(os.getpid())),
  contract_sha256=M.digest(core.contract),catalogues={t:list(r['roles'])for t,r in core.rows.items()},
  original_spawn_public_control=copy.deepcopy(public),original_spawn_completed_operations=effects,
  original_spawn_history_empty_verified=True,original_spawn_terminal_retirement_jobs=terminal,
  original_bridge_logical_map=logical,original_bridge_cli_controls=clis,
  original_bridge_finished_tokens=[_token(v,core.rows)for v in sorted(bridge.finished)],
  source_spawn_pending_empty_verified=True,logical_membership_not_inferred_from_archived=True,
  financial_or_scientific_contents_read=False,safe_to_TERM=False,paid_activation_authorized=False,whole_runnable_ready=False)
 value['original_frozen_control_whitelist']=W.source_fields(core,owner=_SOURCE_WHITELIST_OWNERS.get(id(core)),own=own,read_budget=read_budget)
 # Explicit absent marker is permitted ONLY for a legacy OWN control-codec
 # fixture with none of the three native domains. Production never falls back.
 absent_OWN=(own and not any(hasattr(core,n)for n in('cold_bootstrap','native_host_environment','native_layout')))
 value['original_native_infrastructure_controls']=(None if absent_OWN else I.source_fields(core,
  owner=_SOURCE_WHITELIST_OWNERS.get(id(core)),own=own,read_budget=read_budget))
 _validate_controls(value);return value


def _validate_controls(value):
 M.need(type(value)is dict and value['schema']==CONTROL and type(value['OWN'])is bool and
  value['source_spawn_pending_empty_verified']is value['original_spawn_history_empty_verified']is
  value['logical_membership_not_inferred_from_archived']is True and
  value['financial_or_scientific_contents_read']is value['safe_to_TERM']is value['paid_activation_authorized']is value['whole_runnable_ready']is False,
  'NATIVE_SUPPLEMENT_FIXED_CONTROL_SCHEMA_NO_AUTHORITY')
 rows=value['catalogues'];public=value['original_spawn_public_control']
 M.need(set(public)=={'next_ordinals','used_slots','effects'}and
  set(public['next_ordinals'])==set(public['used_slots'])==set(rows),
  'NATIVE_SUPPLEMENT_LOSSLESS_ORIGINAL_COUNTER_DOMAINS')
 for t,n in public['next_ordinals'].items():
  used=public['used_slots'][t]
  M.need(type(n)is int and n>=1 and type(used)is list and used==sorted(set(used))and
   1 in used and all(type(v)is int and 1<=v<=32 for v in used),
   'NATIVE_SUPPLEMENT_REAL_ORDINAL_AND_USED_SLOT_CONTROL_NOT_AGENT_CAP')
 operations=value['original_spawn_completed_operations'];seen=set();expected=[]
 for row in operations:
  t,n=row['trajectory'],row['ordinal'];key=t,n;lease=Lease(**row['lease'])
  M.need(t in rows and type(n)is int and 1<=n<public['next_ordinals'][t]and key not in seen and
   type(row['slot'])is int and row['slot']in public['used_slots'][t]and type(row['reuse'])is bool and
   row['committed']is row['birth_observed']is True and lease.role=='worker-'+str(row['slot']-1).zfill(2)and
   lease.action=='BIRTH'and type(lease.epoch_before)is int and lease.epoch_before>=0 and
   type(lease.operation_id)is str and re.fullmatch('[0-9a-f]{32}',lease.operation_id),
   'NATIVE_SUPPLEMENT_COMPLETE_ORIGINAL_OPERATION_AND_LEASE_CONTROL')
  _sha(row['native_cli_token_sha256']);seen.add(key)
  expected.append(dict(trajectory_id=t,spawn_ordinal=n,worker_slot=row['slot'],reuse=row['reuse'],
   operation_id=lease.operation_id,committed=True,birth_observed=True))
 M.need(expected==public['effects']and all({n for tt,n in seen if tt==t}==set(range(1,public['next_ordinals'][t]))for t in rows),
  'NATIVE_SUPPLEMENT_ALL_ORIGINAL_EFFECTS_KEPT_NO_MISSING_OR_REPLAYABLE_ORDINAL')
 clis={tuple(row['key']):row for row in value['original_bridge_cli_controls']}
 M.need(len(clis)==len(value['original_bridge_cli_controls']),'NATIVE_SUPPLEMENT_UNAMBIGUOUS_ORIGINAL_CLI_CONTROLS')
 shape={t:dict(roles=r)for t,r in rows.items()}
 for key,row in clis.items():
  M.need(set(row)=={'key','token','birth','logical_birth_sha256','archived'}and len(key)==2 and
   key[0]in rows and key[1]in rows[key[0]]and type(row['archived'])is bool and
   _token(unpack_token(row['token']),shape)==row['token']and tuple(row['token']['key'])==key,
   'NATIVE_SUPPLEMENT_EXACT_TYPED_CLI_CONTROL_SCHEMA')
  M.birth(row['birth']);_sha(row['logical_birth_sha256'])
 for token in value['original_bridge_finished_tokens']:
  M.need(_token(unpack_token(token),shape)==token,'NATIVE_SUPPLEMENT_EXACT_ORIGINAL_FINISHED_TOKEN_CONTROL')
 logical=set()
 for row in value['original_bridge_logical_map']:
  key=row['trajectory'],row['role'];raw=_sha(row['logical_birth_sha256'])
  M.need(key not in logical and key in clis and clis[key]['logical_birth_sha256']==raw,
   'NATIVE_SUPPLEMENT_TRUE_LOGICAL_MAP_MATCHES_ORIGINAL_CLI_NOT_ARCHIVED_HEURISTIC')
  logical.add(key)
 W.validate_section(value['original_frozen_control_whitelist'],own=value['OWN'],source_birth=value['source_owner_birth'],contract_sha256=value['contract_sha256'],catalogues=value['catalogues'])
 section=value['original_native_infrastructure_controls']
 if section is None:
  M.need(value['OWN']is True,'NATIVE_SUPPLEMENT_PRODUCTION_REQUIRES_ORIGINAL_NATIVE_INFRA_SOURCE_NOT_OWN_ABSENCE')
 else:
  I.validate_section(section,own=value['OWN'],source_birth=value['source_owner_birth'],
   contract_sha256=value['contract_sha256'],rows=section['row_controls'])
  M.need({t:list(r['roles'])for t,r in section['row_controls'].items()}==value['catalogues'],
   'NATIVE_SUPPLEMENT_ORIGINAL_NATIVE_INFRA_SAME_ROSTER')
 return value


@dataclass(frozen=True,repr=False)
class CapturedNativeSourceControls:
 core:object
 OWN:bool
 source_owner_birth:object
 controls:dict
 _seal:object
 def snapshot(self):
  M.need(self._seal is _SEAL and _CAPTURES.get(id(self.core))is self,'NATIVE_SUPPLEMENT_REGISTERED_SOURCE_CAPTURE')
  return copy.deepcopy(self.controls)


def _capture(core,*,read_budget,own):
 M.need(id(core)not in _CAPTURES,'NATIVE_SUPPLEMENT_ONE_SOURCE_CAPTURE')
 before=_controls(core,read_budget=read_budget,own=own)
 M.need(_controls(core,read_budget=read_budget,own=own)==before,'NATIVE_SUPPLEMENT_SOURCE_FIELDS_NOT_STABLE_WAIT')
 cap=CapturedNativeSourceControls(core,own,process_birth(os.getpid()),before,_SEAL);_CAPTURES[id(core)]=cap
 return cap


def capture_OWN_components(core,*,read_budget):return _capture(core,read_budget=read_budget,own=True)


def _self_pin():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _complete(home,body,*,own,final_guard):
 leaf=Path(home)/(OWN_LEAF if own else LEAF);leaf.mkdir(mode=0o700)
 body=dict(body,schema=SCHEMA,OWN=own,source_module_sha256=_self_pin(),source_pins=verify_sources(),
  source_directory=M.descriptor(leaf),inert_only=True,safe_to_TERM=False,paid_activation_authorized=False,whole_runnable_ready=False)
 source=F._save(leaf/'SOURCE.json',body)
 final_guard()
 issued=F._save(leaf/'ISSUED.json',dict(schema=ISSUED,OWN=own,source_identity=source['identity'],
  source_sha256=source['sha256'],source_module_sha256=_self_pin(),source_owner_birth=body['source_owner_birth']))
 fd=os.open(leaf,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
 return dict(path=source['identity']['path'],sha256=source['sha256'],issued_sha256=issued['sha256'])


class NativeSourceReference:
 __slots__=('_path','_pin','_seal')
 def __init__(self,*a,**k):raise M.PaidColdWait('NATIVE_SUPPLEMENT_FIXED_REFERENCE_LOADER_ONLY')
 def __setattr__(self,n,v):
  M.need(not hasattr(self,'_seal'),'NATIVE_SUPPLEMENT_IMMUTABLE_REFERENCE');object.__setattr__(self,n,v)
 @property
 def path(self):return self._path
 @property
 def sha256(self):return self._pin


class OWNComponentReference(NativeSourceReference):__slots__=()


def _reference(path,pin,*,own):
 p=Path(path)
 M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and p.name=='SOURCE.json'and
  p.parent.name==(OWN_LEAF if own else LEAF),'NATIVE_SUPPLEMENT_FIXED_REFERENCE_NAMESPACE')
 ref=object.__new__(OWNComponentReference if own else NativeSourceReference)
 ref._path,ref._pin,ref._seal=str(p),M.sha(pin),_SEAL;return ref


def load_reference(path,sha256):return _reference(path,sha256,own=False)
def load_OWN_component_reference(path,sha256):return _reference(path,sha256,own=True)


def _read_complete(reference,home,*,read_budget,own):
 budget(read_budget);verify_sources();home=Path(home)
 M.need(type(reference)is(OWNComponentReference if own else NativeSourceReference)and reference._seal is _SEAL and
  Path(reference.path)==home/(OWN_LEAF if own else LEAF)/'SOURCE.json','NATIVE_SUPPLEMENT_TYPED_FIXED_HOME_REFERENCE')
 leaf=home/(OWN_LEAF if own else LEAF);M.existing(M.descriptor(leaf),directory=True,private=True)
 try:marker,marker_pin=M.private_read(leaf/'ISSUED.json',limit=262144)
 except FileNotFoundError:raise M.PaidColdWait('NATIVE_SUPPLEMENT_INCOMPLETE_SOURCE_NO_ISSUED_WAIT')from None
 M.need(type(marker)is dict and set(marker)=={'schema','OWN','source_identity','source_sha256','source_module_sha256','source_owner_birth'}and
  marker['schema']==ISSUED and marker['OWN']is own and marker['source_module_sha256']==_self_pin()and
  marker['source_sha256']==reference.sha256 and marker['source_identity']['path']==reference.path,
  'NATIVE_SUPPLEMENT_EXACT_O_EXCL_ISSUED_BEFORE_SOURCE_READ')
 M.existing(marker['source_identity'],private=True)
 body,pin=M.private_read(Path(reference.path),reference.sha256,limit=8*1024*1024)
 M.need(body['schema']==SCHEMA and body['OWN']is own and body['source_module_sha256']==_self_pin()and
  body['source_pins']==PINS and body['source_directory']==M.descriptor(leaf)and
  body['source_owner_birth']==marker['source_owner_birth']==body['controls']['source_owner_birth']and
  body['controls_sha256']==M.digest(body['controls'])and body['controls']['OWN']is own and
  body['contract_sha256']==body['controls']['contract_sha256']and body['inert_only']is True and
  body['safe_to_TERM']is body['paid_activation_authorized']is body['whole_runnable_ready']is False,
  'NATIVE_SUPPLEMENT_COMPLETE_SOURCE_METADATA_NOT_AUTHORITY')
 _validate_controls(body['controls']);read_budget.check()
 return body,dict(path=reference.path,sha256=pin,issued_identity=M.descriptor(leaf/'ISSUED.json'),issued_sha256=marker_pin)


def publish_registered(owner,*,read_budget):
 """Live SOURCE only, after existing original T and retired-services sidecar."""
 budget(read_budget)
 issuer,ticket_body,storage,locks,retirement=F._source(owner,read_budget);core=owner.core
 _unlocked(core);verify_sources()
 registered=D._PUBLICATIONS.get(id(owner))
 M.need(type(registered)is dict and registered.get('owner')is owner and registered.get('reference')is not None and
  id(owner)not in _PUBLICATIONS,'NATIVE_SUPPLEMENT_EXISTING_SAME_SOURCE_SERVICE_PUBLICATION_NO_RETRY')
 saved=registered['reference'];services_ref=D.load_reference(saved['path'],saved['sha256'])
 service_body,_=D._read_complete(services_ref,core.home,own=False,budget=read_budget)
 M.need(service_body['old_owner_birth']==asdict(process_birth(os.getpid()))and
  service_body['original_ticket']==dict(path=issuer.ticket.path,sha256=issuer.ticket.sha256,identity=M.descriptor(issuer.ticket.path))and
  service_body['storage']==storage and service_body['locks']==[[k,v]for k,v in locks]and
  service_body['original_financial_metadata']==ticket_body['financial_metadata']and
  service_body['original_transport_retirement']==retirement,
  'NATIVE_SUPPLEMENT_ORIGINAL_T_SERVICES_STORAGE_LOCKS_AND_FINANCIAL_BINDING')
 M.need(core.control.thread.is_alive()is False and core.control.server.socket.fileno()==-1 and
  core.gate.closed and not core.gate.waiters, 'NATIVE_SUPPLEMENT_SOURCE_CONTROL_CLOSED_AND_ORIGINAL_GATE_SHUTDOWN')
 for name in('inbox','spawn_inbox','bridge_inbox','phase_proof_inbox'):
  inbox=getattr(core,name);read_budget.check()
  M.need(inbox.lock.acquire(timeout=min(.2,read_budget.remaining())),'NATIVE_SUPPLEMENT_INBOX_CONTROL_LOCK_FINITE')
  try:M.need(not inbox.pending and (name!='inbox'or inbox.unresolved==0),'NATIVE_SUPPLEMENT_SOURCE_NO_PENDING_CONTROL_HANDLERS')
  finally:inbox.lock.release()
 M.need(id(core)not in _SOURCE_WHITELIST_OWNERS,'NATIVE_SUPPLEMENT_ONE_ORIGINAL_SOURCE_WHITELIST_CONTEXT_NO_RETRY')
 _SOURCE_WHITELIST_OWNERS[id(core)]=owner
 capture=_capture(core,read_budget=read_budget,own=False);controls=capture.snapshot()
 db=F._db_controls(core.ledger.home/'ledger.sqlite',core.queue.home/'queue.sqlite',read_budget)
 M.need(db==service_body['current_fixed_db_controls'],'NATIVE_SUPPLEMENT_SOURCE_FIXED_FINANCIAL_EQUATIONS_UNCHANGED')
 body=dict(source_owner_birth=asdict(capture.source_owner_birth),contract_sha256=M.digest(core.contract),
  controls=controls,controls_sha256=M.digest(controls),services_reference=dict(path=services_ref.path,sha256=services_ref.sha256),
  original_ticket=copy.deepcopy(service_body['original_ticket']),storage=storage,locks=[[k,v]for k,v in locks],
  original_financial_metadata=copy.deepcopy(ticket_body['financial_metadata']),current_fixed_db_controls=db,
  production_source_binding=True,qualification_scope='ORIGINAL_LIVE_SOURCE_AFTER_RETIRED_SERVICES_AND_T')
 def final():
  current,tb,ss,ll,rr=F._source(owner,read_budget)
  M.need(current is issuer and tb==ticket_body and ss==storage and ll==locks and rr==retirement and
   _controls(core,read_budget=read_budget,own=False)==controls and
   F._db_controls(core.ledger.home/'ledger.sqlite',core.queue.home/'queue.sqlite',read_budget)==db and
   D._read_complete(services_ref,core.home,own=False,budget=read_budget)[0]==service_body,
   'NATIVE_SUPPLEMENT_SOURCE_CHANGED_RETAIN_UNISSUED_PARTIAL')
 _PUBLICATIONS[id(owner)]=dict(owner=owner,capture=capture)
 result=_complete(core.home,body,own=False,final_guard=final);_PUBLICATIONS[id(owner)]['reference']=copy.deepcopy(result)
 return result


class VerifiedNativeSourceControls:
 __slots__=('_body','_reference','_controls','_seal','source_owner','source_ticket','services','old_owner_birth',
  'new_owner_birth','contract_sha256','lock_fds')
 def __init__(self,*a,**k):raise M.PaidColdWait('NATIVE_SUPPLEMENT_ONLY_TYPED_NEW_RECEIVER_VERIFIER')
 def __setattr__(self,n,v):
  M.need(not hasattr(self,'_seal'),'NATIVE_SUPPLEMENT_IMMUTABLE_VERIFIED_CAP');object.__setattr__(self,n,v)
 def snapshot(self):
  M.need(self._seal is _SEAL and _VERIFIED.get(id(self))is self,'NATIVE_SUPPLEMENT_EXACT_VERIFIED_CAP_SEAL')
  return copy.deepcopy(self._controls)
 @property
 def safe_to_TERM(self):return False
 @property
 def paid_activation_authorized(self):return False
 @property
 def whole_runnable_ready(self):return False


def verify_reference(reference,*,owner,ticket,read_budget):
 """Typed T/services verifier owns original cross-birth/three-lock proof."""
 import normal_inert_cut as T
 from native_cold_owner import NativeColdOwner
 budget(read_budget)
 M.need(type(reference)is NativeSourceReference and reference._seal is _SEAL and
  type(owner)is NativeColdOwner and type(owner.core)is OriginalRelayCore and type(ticket)is T.NormalInertTicket,
  'NATIVE_SUPPLEMENT_PRODUCTION_TYPED_SOURCE_REFERENCE_NOT_OWN_OR_BOOL')
 _unlocked(owner.core);verify_sources()
 original_cap=T.verify_inert_ticket(ticket,owner=owner,read_budget=read_budget)
 M.need(type(original_cap)is T.VerifiedNormalInertCut and original_cap.OWN is False,
  'NATIVE_SUPPLEMENT_ORIGINAL_T_VERIFIED_BEFORE_NEW_SOURCE_BODY_READ')
 home=M.existing(original_cap.owner_home,directory=True,private=True)
 M.need(home==owner.core.home,'NATIVE_SUPPLEMENT_HOME_DERIVED_FROM_ORIGINAL_T_NOT_CALLER_PATH')
 body,record=_read_complete(reference,home,read_budget=read_budget,own=False)
 services=D.verify_reference(D.load_reference(**body['services_reference']),owner=owner,ticket=ticket,read_budget=read_budget)
 M.need(type(services)is D.VerifiedRetiredServiceControls and services.OWN is False and
  services.old_owner_birth!=services.new_owner_birth==process_birth(os.getpid()),
  'NATIVE_SUPPLEMENT_ORIGINAL_TYPED_CROSS_BIRTH_SERVICES_T_PROOF')
 original=services._body
 M.need(body['production_source_binding']is True and body['qualification_scope']=='ORIGINAL_LIVE_SOURCE_AFTER_RETIRED_SERVICES_AND_T'and
  body['source_owner_birth']==asdict(services.old_owner_birth)and body['contract_sha256']==services.contract_sha256 and
  all(body[n]==original[n]for n in('original_ticket','storage','locks','original_financial_metadata','current_fixed_db_controls'))and
  body['controls']['catalogues']=={t:list(r['roles'])for t,r in owner.core.rows.items()},
  'NATIVE_SUPPLEMENT_SAME_ORIGINAL_T_SOURCE_BIRTH_STORAGE_LOCKS_FINANCIAL_AND_ROSTER')
 M.need(_read_complete(reference,owner.core.home,read_budget=read_budget,own=False)==(body,record),
  'NATIVE_SUPPLEMENT_STABLE_APPEND_ONLY_SOURCE_AND_MARKER')
 value=object.__new__(VerifiedNativeSourceControls)
 value._body,value._reference,value._controls=copy.deepcopy(body),copy.deepcopy(record),copy.deepcopy(body['controls'])
 value.source_owner,value.source_ticket,value.services=owner,ticket,services
 value.old_owner_birth,value.new_owner_birth=services.old_owner_birth,services.new_owner_birth
 value.contract_sha256,value.lock_fds=services.contract_sha256,tuple(services.lock_fds)
 value._seal=_SEAL;_VERIFIED[id(value)]=value;return value


def publish_OWN_component(capture,*,read_budget):
 """OWN codec only: never an issued-T/new-owner transfer qualification."""
 budget(read_budget)
 M.need(type(capture)is CapturedNativeSourceControls and capture.OWN is True and
  capture._seal is _SEAL and _CAPTURES.get(id(capture.core))is capture and
  capture.source_owner_birth==process_birth(os.getpid()),'NATIVE_SUPPLEMENT_EXPLICIT_OWN_CONTROL_COMPONENT_ONLY')
 _unlocked(capture.core)
 controls=capture.snapshot();core=capture.core
 body=dict(source_owner_birth=asdict(capture.source_owner_birth),contract_sha256=M.digest(core.contract),
  controls=controls,controls_sha256=M.digest(controls),production_source_binding=False,
  qualification_scope='OWN_CONTROL_CODEC_ONLY_NO_T_OR_CROSS_BIRTH')
 return _complete(core.home,body,own=True,final_guard=lambda:M.need(
  _controls(core,read_budget=read_budget,own=True)==controls,'NATIVE_SUPPLEMENT_OWN_SOURCE_NOT_STABLE'))


def read_OWN_component(reference,*,home,read_budget):
 body,_=_read_complete(reference,home,read_budget=read_budget,own=True)
 M.need(body['production_source_binding']is False and body['qualification_scope']=='OWN_CONTROL_CODEC_ONLY_NO_T_OR_CROSS_BIRTH',
  'NATIVE_SUPPLEMENT_OWN_NOT_PRODUCTION_TRANSFER')
 return copy.deepcopy(body['controls'])
