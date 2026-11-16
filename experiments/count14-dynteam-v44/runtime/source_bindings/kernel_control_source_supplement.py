"""Append-only numeric ordered-ACP controls from the exact live old owner.

Only the existing custody map's checked six-field counters and exact framework
birth/epoch anchors are captured. No protocol bodies, tool IDs/results, SDK
state, financial change, baseline creation or inferred zero is involved.
Receiving authority is the existing typed native/T/services/three-lock chain.
"""
from dataclasses import asdict,dataclass
from pathlib import Path
import copy
import hashlib
import importlib
import os

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import ProcessBirth,process_birth
from original_relay_core import OriginalRelayCore
from native_sdk_startup_epochs import NativeSdkStartupEpochs,Epoch
from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
from smoke_racing_tools_native_control import checked_control
import native_control_source_supplement as N
import financial_runtime_source_control as F

SCHEMA='count14-kernel-ordered-control-source-supplement-v1'
CONTROL='count14-original-kernel-ordered-control-snapshots-v1'
ISSUED='count14-kernel-ordered-control-ISSUED-v1'
LEAF='normal-kernel-ordered-source-control-v1'
OWN_LEAF='OWN-kernel-ordered-control-component-v1'
PINS=dict(native_control_source_supplement='6a05b79f670257c49d29edca6f924c5144fe68ed28517e10b1c6ba250115b049',
 smoke_racing_tools_kernel_custody='5ff1cb87ca0cd1f09b6ef972edb3d4ab3c945618012ee10d8849468333f841ab',
 smoke_racing_tools_native_control='9c385bc46f8b0905159249b4e539bd75955899aefcb2e83001fc3dd128f58727',
 smoke_racing_tools_cold_control_builder='c2c42fd44aae7b22d995127edb387d5547cd1956fcaea583568febd44d287fd8',
 native_sdk_startup_epochs='a935f4406c159d3ef2067d0dc21aee9df76da1a8189fdd175b73dff9f49814af')
_SEAL=object()
_CAPTURES={}
_PUBLICATIONS={}
_VERIFIED={}


def verify_sources():
 for name,pin in PINS.items():
  p=Path(importlib.import_module(name).__file__)
  M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and
   hashlib.sha256(p.read_bytes()).hexdigest()==pin,'KERNEL_CONTROL_EXACT_FROZEN_ORIGINAL_SOURCE_PINS')
 N.verify_sources();return dict(PINS)


def budget(value):
 M.need(type(value)is ReadBudget,'KERNEL_CONTROL_FINITE_CONTROL_READ_BUDGET');value.check()


def epoch_anchor(epoch):
 M.need(type(epoch)is Epoch,'KERNEL_CONTROL_EXACT_ORIGINAL_EPOCH_ANCHOR')
 return dict(key=[epoch.trajectory,epoch.role],ordinal=epoch.ordinal,child=asdict(epoch.child),
  native_token_sha256=M.digest(epoch.token),request_anchor=epoch.request_anchor,
  archived=epoch.archived,first_session=epoch.first_session,contract_sha256=epoch.contract_sha256)


def _validate(controls):
 M.need(type(controls)is dict and set(controls)=={'schema','OWN','source_owner_birth','contract_sha256',
  'catalogues','original_snapshot_map_present','snapshots','current_epoch_presence',
  'original_numeric_control_only','baseline_created_or_extended','models_or_tools_clear_asserted'}and
  controls['schema']==CONTROL and type(controls['OWN'])is bool and
  controls['original_snapshot_map_present']is controls['original_numeric_control_only']is True and
  controls['baseline_created_or_extended']is controls['models_or_tools_clear_asserted']is False,
  'KERNEL_CONTROL_FIXED_NUMERIC_SOURCE_SCHEMA_NOT_CLEAR_AUTHORITY')
 M.birth(controls['source_owner_birth']);M.sha(controls['contract_sha256'])
 rows=controls['catalogues'];M.need(type(rows)is dict,'KERNEL_CONTROL_ORIGINAL_ROSTER_MAP')
 def key(value):
  M.need(type(value)is list and len(value)==2 and value[0]in rows and value[1]in rows[value[0]],
   'KERNEL_CONTROL_REGISTERED_ROLE_ENUMERATION_ONLY');return tuple(value)
 snapshots={}
 for row in controls['snapshots']:
  M.need(type(row)is dict and set(row)=={'key','child','value'},'KERNEL_CONTROL_EXACT_SNAPSHOT_FIELDS')
  k=key(row['key']);M.need(k not in snapshots,'KERNEL_CONTROL_UNIQUE_SNAPSHOT_KEY')
  M.birth(row['child']);checked_control(row['value']);snapshots[k]=row
 seen=set()
 for row in controls['current_epoch_presence']:
  M.need(type(row)is dict and set(row)=={'epoch','present','snapshot_child_matches_epoch'}and
   row['present']is row['snapshot_child_matches_epoch']is True,
   'KERNEL_CONTROL_MISSING_OR_WRONG_CHILD_SNAPSHOT_WAIT_NO_ZERO_INFERENCE')
  e=row['epoch'];M.need(type(e)is dict and set(e)=={'key','ordinal','child','native_token_sha256',
   'request_anchor','archived','first_session','contract_sha256'},'KERNEL_CONTROL_FIXED_EPOCH_CONTROL_ANCHOR')
  k=key(e['key']);M.need(k not in seen and k in snapshots and snapshots[k]['child']==e['child']and
   type(e['ordinal'])is int and e['ordinal']>=1 and type(e['request_anchor'])is int and e['request_anchor']>=0 and
   type(e['archived'])is type(e['first_session'])is bool and e['contract_sha256']==controls['contract_sha256'],
   'KERNEL_CONTROL_REAL_CURRENT_EPOCH_AND_EXACT_SNAPSHOT_CHILD')
  M.birth(e['child']);M.sha(e['native_token_sha256']);seen.add(k)
 return controls


def _controls(core,*,read_budget,own):
 budget(read_budget);N._unlocked(core);verify_sources()
 custody=getattr(core,'native_kernel_tool_custody',None);epochs=getattr(core,'native_sdk_startup_epochs',None)
 M.need(type(core)is OriginalRelayCore and core.qualification_only is own and
  type(custody)is NativeKernelToolCustody and custody.core is core and
  type(epochs)is NativeSdkStartupEpochs and epochs.core is core and epochs.custody is custody and
  custody.sdk_startup_epochs is epochs and epochs.owner==process_birth(os.getpid())and
  epochs.sha==M.digest(core.contract),'KERNEL_CONTROL_REAL_LIVE_SOURCE_CUSTODY_AND_ORIGINAL_EPOCH_GRAPH')
 M.need((own and any(p.startswith('OWN-')for p in core.home.parts))or
  (not own and core.home==Path(core.contract['arms'][0]['root'])/'owner'),
  'KERNEL_CONTROL_EXACT_ORIGINAL_SCOPE_HOME')
 source=getattr(custody,'native_control_snapshots',None)
 M.need(type(source)is dict,'KERNEL_CONTROL_SOURCE_MAP_ABSENT_WAIT_NOT_EMPTY_DEFAULT')
 snapshots=[]
 for key,row in sorted(source.items()):
  read_budget.check()
  M.need(type(key)is tuple and len(key)==2 and type(row)is dict and set(row)=={'child','value'}and
   type(row['child'])is ProcessBirth,'KERNEL_CONTROL_ORIGINAL_CUSTODY_MAP_ROW')
  snapshots.append(dict(key=list(key),child=asdict(row['child']),value=copy.deepcopy(checked_control(row['value']))))
 presence=[]
 for key,epoch in sorted(epochs.current.items()):
  read_budget.check();M.need(type(epoch)is Epoch and key==(epoch.trajectory,epoch.role)and
   epoch.owner_birth==epochs.owner,'KERNEL_CONTROL_SOURCE_CURRENT_EPOCH_OWNER_NOT_NEW_BASELINE')
  row=source.get(key)
  presence.append(dict(epoch=epoch_anchor(epoch),present=row is not None,
   snapshot_child_matches_epoch=row is not None and row['child']==epoch.child))
 value=dict(schema=CONTROL,OWN=own,source_owner_birth=asdict(epochs.owner),contract_sha256=epochs.sha,
  catalogues={t:list(r['roles'])for t,r in core.rows.items()},original_snapshot_map_present=True,
  snapshots=snapshots,current_epoch_presence=presence,original_numeric_control_only=True,
  baseline_created_or_extended=False,models_or_tools_clear_asserted=False)
 read_budget.check();return _validate(value)


@dataclass(frozen=True,repr=False)
class CapturedKernelControls:
 core:object
 OWN:bool
 controls:dict
 _seal:object
 def snapshot(self):
  M.need(self._seal is _SEAL and _CAPTURES.get(id(self.core))is self,'KERNEL_CONTROL_REGISTERED_CAPTURE')
  return copy.deepcopy(self.controls)


def _capture(core,*,read_budget,own):
 M.need(id(core)not in _CAPTURES,'KERNEL_CONTROL_ONE_SOURCE_CAPTURE')
 before=_controls(core,read_budget=read_budget,own=own)
 M.need(_controls(core,read_budget=read_budget,own=own)==before,'KERNEL_CONTROL_SOURCE_CHANGED_WAIT')
 value=CapturedKernelControls(core,own,before,_SEAL);_CAPTURES[id(core)]=value;return value


def capture_OWN_components(core,*,read_budget):return _capture(core,read_budget=read_budget,own=True)
def _self_pin():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class KernelSourceReference:
 __slots__=('_path','_pin','_seal')
 def __init__(self,*a,**k):raise M.PaidColdWait('KERNEL_CONTROL_FIXED_REFERENCE_LOADER_ONLY')
 def __setattr__(self,n,v):
  M.need(not hasattr(self,'_seal'),'KERNEL_CONTROL_IMMUTABLE_REFERENCE');object.__setattr__(self,n,v)
 @property
 def path(self):return self._path
 @property
 def sha256(self):return self._pin


class OWNKernelReference(KernelSourceReference):__slots__=()


def _reference(path,pin,*,own):
 p=Path(path);M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and p.name=='SOURCE.json'and
  p.parent.name==(OWN_LEAF if own else LEAF),'KERNEL_CONTROL_FIXED_SOURCE_REFERENCE_NAMESPACE')
 value=object.__new__(OWNKernelReference if own else KernelSourceReference)
 value._path,value._pin,value._seal=str(p),M.sha(pin),_SEAL;return value


def load_reference(path,sha256):return _reference(path,sha256,own=False)
def load_OWN_reference(path,sha256):return _reference(path,sha256,own=True)


def _complete(core,body,*,own,final_guard):
 leaf=core.home/(OWN_LEAF if own else LEAF);leaf.mkdir(mode=0o700)
 body=dict(body,schema=SCHEMA,OWN=own,source_module_sha256=_self_pin(),source_pins=verify_sources(),
  source_directory=M.descriptor(leaf),inert_only=True,safe_to_TERM=False,paid_activation_authorized=False,
  whole_runnable_ready=False)
 source=F._save(leaf/'SOURCE.json',body);final_guard()
 issued=F._save(leaf/'ISSUED.json',dict(schema=ISSUED,OWN=own,source_identity=source['identity'],
  source_sha256=source['sha256'],source_module_sha256=_self_pin(),source_owner_birth=body['source_owner_birth']))
 for directory in(leaf,core.home):
  fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:os.fsync(fd)
  finally:os.close(fd)
 return dict(path=source['identity']['path'],sha256=source['sha256'],issued_sha256=issued['sha256'])


def _read_complete(reference,home,*,read_budget,own):
 budget(read_budget);verify_sources();leaf=Path(home)/(OWN_LEAF if own else LEAF)
 M.need(type(reference)is(OWNKernelReference if own else KernelSourceReference)and reference._seal is _SEAL and
  Path(reference.path)==leaf/'SOURCE.json','KERNEL_CONTROL_TYPED_FIXED_HOME_REFERENCE')
 M.existing(M.descriptor(leaf),directory=True,private=True)
 try:marker,marker_pin=M.private_read(leaf/'ISSUED.json',limit=262144)
 except FileNotFoundError:raise M.PaidColdWait('KERNEL_CONTROL_INCOMPLETE_SOURCE_UNISSUED_WAIT')from None
 M.need(type(marker)is dict and set(marker)=={'schema','OWN','source_identity','source_sha256',
  'source_module_sha256','source_owner_birth'}and marker['schema']==ISSUED and marker['OWN']is own and
  marker['source_module_sha256']==_self_pin()and marker['source_sha256']==reference.sha256 and
  marker['source_identity']['path']==reference.path,'KERNEL_CONTROL_O_EXCL_ISSUED_BEFORE_SOURCE_READ')
 M.existing(marker['source_identity'],private=True)
 body,pin=M.private_read(reference.path,reference.sha256,limit=8*1024*1024)
 M.need(body['schema']==SCHEMA and body['OWN']is own and body['source_module_sha256']==_self_pin()and
  body['source_pins']==PINS and body['source_directory']==M.descriptor(leaf)and
  body['source_owner_birth']==marker['source_owner_birth']==body['controls']['source_owner_birth']and
  body['controls_sha256']==M.digest(body['controls'])and body['controls']['OWN']is own and
  body['contract_sha256']==body['controls']['contract_sha256']and body['inert_only']is True and
  body['safe_to_TERM']is body['paid_activation_authorized']is body['whole_runnable_ready']is False,
  'KERNEL_CONTROL_COMPLETE_SOURCE_NOT_PHYSICAL_OR_RUNTIME_AUTHORITY')
 _validate(body['controls']);read_budget.check()
 return body,dict(path=reference.path,sha256=pin,issued_identity=M.descriptor(leaf/'ISSUED.json'),issued_sha256=marker_pin)


def publish_registered(owner,*,read_budget):
 """Live old SOURCE only, after its existing native/T/services publication."""
 budget(read_budget);issuer,ticket_body,storage,locks,retirement=F._source(owner,read_budget)
 core=owner.core;N._unlocked(core);verify_sources()
 registered=N._PUBLICATIONS.get(id(owner))
 M.need(type(registered)is dict and registered.get('owner')is owner and registered.get('reference')is not None and
  id(owner)not in _PUBLICATIONS,'KERNEL_CONTROL_ORIGINAL_SOURCE_NATIVE_PUBLICATION_NO_RETRY')
 saved=registered['reference'];native=N.load_reference(saved['path'],saved['sha256'])
 original,_=N._read_complete(native,core.home,read_budget=read_budget,own=False)
 M.need(original['source_owner_birth']==asdict(process_birth(os.getpid()))and
  original['original_ticket']==dict(path=issuer.ticket.path,sha256=issuer.ticket.sha256,identity=M.descriptor(issuer.ticket.path))and
  original['storage']==storage and original['locks']==[[k,v]for k,v in locks]and
  core.control.thread.is_alive()is False and core.control.server.socket.fileno()==-1 and
  core.gate.closed and not core.gate.waiters,
  'KERNEL_CONTROL_LIVE_EXACT_OLD_SOURCE_CLOSED_LISTENER_AND_SHUTDOWN_GATE')
 capture=_capture(core,read_budget=read_budget,own=False);controls=capture.snapshot()
 db=F._db_controls(core.ledger.home/'ledger.sqlite',core.queue.home/'queue.sqlite',read_budget)
 M.need(db==original['current_fixed_db_controls'],'KERNEL_CONTROL_SOURCE_FINANCIAL_EQUALITIES_UNCHANGED')
 body=dict(source_owner_birth=controls['source_owner_birth'],contract_sha256=M.digest(core.contract),
  controls=controls,controls_sha256=M.digest(controls),native_reference=dict(path=native.path,sha256=native.sha256),
  current_fixed_db_controls=db,production_source_binding=True)
 def final():
  again,tb,ss,ll,rr=F._source(owner,read_budget)
  M.need(again is issuer and tb==ticket_body and ss==storage and ll==locks and rr==retirement and
   _controls(core,read_budget=read_budget,own=False)==controls and
   N._read_complete(native,core.home,read_budget=read_budget,own=False)[0]==original and
   F._db_controls(core.ledger.home/'ledger.sqlite',core.queue.home/'queue.sqlite',read_budget)==db,
   'KERNEL_CONTROL_SOURCE_CHANGED_RETAIN_UNISSUED_PARTIAL')
 _PUBLICATIONS[id(owner)]=dict(owner=owner,capture=capture)
 result=_complete(core,body,own=False,final_guard=final);_PUBLICATIONS[id(owner)]['reference']=copy.deepcopy(result)
 return result


class VerifiedKernelControls:
 __slots__=('_body','_controls','_reference','_seal','native_capability','source_owner','source_ticket',
  'old_owner_birth','new_owner_birth','contract_sha256','lock_fds')
 def __init__(self,*a,**k):raise M.PaidColdWait('KERNEL_CONTROL_ONLY_TYPED_CROSS_BIRTH_VERIFIER')
 def __setattr__(self,n,v):
  M.need(not hasattr(self,'_seal'),'KERNEL_CONTROL_IMMUTABLE_VERIFIED_CAP');object.__setattr__(self,n,v)
 def snapshot(self):
  M.need(self._seal is _SEAL and _VERIFIED.get(id(self))is self,'KERNEL_CONTROL_EXACT_VERIFIED_CAP_SEAL')
  return copy.deepcopy(self._controls)


def verify_reference(reference,*,native_reference,owner,ticket,read_budget):
 budget(read_budget);verify_sources()
 M.need(type(reference)is KernelSourceReference and reference._seal is _SEAL,
  'KERNEL_CONTROL_TYPED_PRODUCTION_REFERENCE_NOT_OWN_OR_BOOL')
 native=N.verify_reference(native_reference,owner=owner,ticket=ticket,read_budget=read_budget)
 body,record=_read_complete(reference,owner.core.home,read_budget=read_budget,own=False)
 M.need(type(native)is N.VerifiedNativeSourceControls and body['production_source_binding']is True and
  body['native_reference']==dict(path=native_reference.path,sha256=native_reference.sha256)and
  body['source_owner_birth']==asdict(native.old_owner_birth)and body['contract_sha256']==native.contract_sha256 and
  body['current_fixed_db_controls']==native._body['current_fixed_db_controls']and
  body['controls']['catalogues']=={t:list(r['roles'])for t,r in owner.core.rows.items()},
  'KERNEL_CONTROL_EXACT_ORIGINAL_NATIVE_T_SERVICES_BOTH_BIRTHS_THREE_LOCKS_AND_FINANCIAL_BINDING')
 M.need(_read_complete(reference,owner.core.home,read_budget=read_budget,own=False)==(body,record),
  'KERNEL_CONTROL_STABLE_ORIGINAL_SOURCE_AND_ISSUED')
 cap=object.__new__(VerifiedKernelControls)
 cap._body,cap._controls,cap._reference=copy.deepcopy(body),copy.deepcopy(body['controls']),copy.deepcopy(record)
 cap.native_capability,cap.source_owner,cap.source_ticket=native,owner,ticket
 cap.old_owner_birth,cap.new_owner_birth=native.old_owner_birth,native.new_owner_birth
 cap.contract_sha256,cap.lock_fds=native.contract_sha256,tuple(native.lock_fds)
 cap._seal=_SEAL;_VERIFIED[id(cap)]=cap;return cap


def publish_OWN_component(capture,*,read_budget):
 budget(read_budget)
 M.need(type(capture)is CapturedKernelControls and capture.OWN is True and capture._seal is _SEAL and
  _CAPTURES.get(id(capture.core))is capture,'KERNEL_CONTROL_OWN_CODEC_ONLY_NO_T_OR_CROSS_BIRTH')
 controls=capture.snapshot();core=capture.core
 return _complete(core,dict(source_owner_birth=controls['source_owner_birth'],contract_sha256=controls['contract_sha256'],
  controls=controls,controls_sha256=M.digest(controls),production_source_binding=False),own=True,
  final_guard=lambda:M.need(_controls(core,read_budget=read_budget,own=True)==controls,'KERNEL_CONTROL_OWN_SOURCE_CHANGED'))


def read_OWN_component(reference,*,home,read_budget):
 body,_=_read_complete(reference,home,read_budget=read_budget,own=True)
 M.need(body['production_source_binding']is False,'KERNEL_CONTROL_OWN_NOT_PRODUCTION_TRANSFER')
 return copy.deepcopy(body['controls'])
