"""Lossless retired SYSTEM metadata, behind the original typed cold verifier.

No live health object, START, poll, HTTP, key read, constructor or authority is
created here. Actual new-birth T/pair/three-lock verification remains original.
The immutable result is a SOURCE ingredient for a later qualified receiver.
"""
from pathlib import Path
import copy,datetime,hashlib,importlib,json,math,os,re,stat,uuid

PINS={
 'durable_service_source_controls':'fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83',
 'source_services_controls':'f7c72e41dc7df2940917ad664d582308ab936387c0b5190a21e2c07bac2d55db',
 'native_system_health':'9786f682727d02392ef53431b793df030525c4bac7ba5b0555ee75c5ecb37163',
 'native_system_probe_child':'0b0435eaabc7bf65419c05e0ea33a4139e1978360c63b94bff74915bc56d4ebe'}
CONTRACTS=frozenset(('9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391',
 '3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937'))
_SEAL=object()
LEAF_NAME='retired-system-history-source-v1'
OWN_LEAF_NAME='OWN-retired-system-history-source-v1'
LEAF=re.compile(r'[0-9]{8}-count14-dynteam-system-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

def need(ok,code):
 if not ok:raise ValueError(code)
def stamp(s):return(s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def private_directory(p):
 p=Path(p);s=p.lstat()
 need(p.is_absolute()and p.resolve()==p and stat.S_ISDIR(s.st_mode)and s.st_uid==os.geteuid()and
      stat.S_IMODE(s.st_mode)==0o700,'SYSTEM_HISTORY_EXACT_CANONICAL_PRIVATE_DIRECTORY')
 return(s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode)
def control(p,budget):
 budget.check();p=Path(p);s=p.lstat()
 need(p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_uid==os.geteuid()and s.st_nlink==1 and
      stat.S_IMODE(s.st_mode)==0o600 and 0<s.st_size<=32768,'SYSTEM_HISTORY_PRIVATE_BOUNDED_PUBLIC_CONTROL')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  a=os.fstat(fd);raw=os.read(fd,32769);b=os.fstat(fd)
  need(stamp(s)==stamp(a)==stamp(b)==stamp(p.lstat())and len(raw)==s.st_size,
       'SYSTEM_HISTORY_STABLE_NOFOLLOW_CONTROL_FD')
 finally:os.close(fd)
 def pairs(items):
  v={}
  for k,x in items:
   need(k not in v,'SYSTEM_HISTORY_DUPLICATE_CONTROL_FIELD');v[k]=x
  return v
 v=json.loads(raw,object_pairs_hook=pairs);need(type(v)is dict,'SYSTEM_HISTORY_PUBLIC_OBJECT_ONLY')
 budget.check();return v,dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),identity=list(stamp(s)))
def verify_sources():
 for name,pin in PINS.items():
  p=Path(importlib.import_module(name).__file__);s=p.lstat()
  need(p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and not s.st_mode&0o022 and
       s.st_uid in(0,os.geteuid())and hashlib.sha256(p.read_bytes()).hexdigest()==pin,
       'SYSTEM_HISTORY_EXACT_ORIGINAL_SOURCE_MODULES')

def _read_bound(home,row,old_birth,contract,*,own,budget):
 """Internal metadata parser; caller data alone never creates a sealed result."""
 need(type(row)is dict and type(row['registered'])is bool,'SYSTEM_HISTORY_EXPLICIT_REGISTERED_SERVICE')
 if not row['registered']:
  need(row==dict(registered=False,configuration=None,records=None),'SYSTEM_HISTORY_ABSENT_IS_UNKNOWN_NOT_ZERO')
  return dict(registered=False,records=None,session_id=None,public=dict(registered=False,sequence=None,
      reported_SYSTEM_tokens=None,unmeasured_SYSTEM_upper=None,source_history_complete=None)),[]
 from native_system_probe_child import ORIGINAL_SHA
 cfg=row['configuration'];records=row['records'];original_public=row['original_public']
 need(row['source_owner_birth']==old_birth and cfg['contract_sha256']==contract and cfg['home']==str(home)and
      cfg['accepting']is False and type(cfg['sequence'])is int and cfg['sequence']>=0 and
      type(cfg['started'])is bool and type(records)is list and len(records)==cfg['sequence']and
      original_public['SYSTEM_occupied_slots']==original_public['running']==original_public['physical_unknown']==0 and
      original_public['period_seconds']==600 and original_public['SYSTEM_reserved_slots']==2 and
      original_public['original_probe_source_sha256']==ORIGINAL_SHA,
      'SYSTEM_HISTORY_COMPLETE_ORIGINAL_STOPPED_CONFIGURATION_AND_COUNTERS')
 home=Path(home);identity=private_directory(home)
 def leaves():
  budget.check();v=[];maximum=len(records)+(1 if cfg['started']else 0)
  for p in home.iterdir():
   budget.check();name=p.name
   need(name=='EXPLICIT_START_PUBLIC.json'or LEAF.fullmatch(name)is not None,
        'SYSTEM_HISTORY_UNKNOWN_LEAF_REFUSED')
   need(len(v)<maximum,'SYSTEM_HISTORY_MORE_LEAVES_THAN_ORIGINAL_SOURCE_CAP')
   v.append(name)
  return sorted(v)
 def probe_files(p):
  names=[]
  for x in p.iterdir():
   budget.check();need(len(names)<3,'SYSTEM_HISTORY_UNEXPECTED_PROBE_FILE_COUNT')
   names.append(x.name)
  return sorted(names)
 before=leaves();refs=[];output=[]
 if not cfg['started']:
  need(cfg['sequence']==0 and records==[]and before==[]and cfg['last_intent_wall']is cfg['last_intent_mono']is None and
       original_public['explicitly_started']is False,'SYSTEM_HISTORY_UNSTARTED_NOT_A_SYNTHETIC_START')
  session=None
 else:
  start,sref=control(home/'EXPLICIT_START_PUBLIC.json',budget);refs.append(sref)
  need(set(start)=={'schema','owner_pid','owner_start_ticks','owner_boot_id','contract_sha256','system_reserved_slots','experiment_permits_used'}and
       start['schema']=='count14-dynteam-system-probe-start-v1'and start['contract_sha256']==contract and
       start['owner_boot_id']==old_birth['boot_id']and type(start['owner_pid'])is int and start['owner_pid']>0 and
       type(start['owner_start_ticks'])is int and start['owner_start_ticks']>0 and
       start['system_reserved_slots']==2 and start['experiment_permits_used']==0 and
       original_public['explicitly_started']is True,'SYSTEM_HISTORY_ORIGINAL_EXPLICIT_START_AND_BOOT_NOT_RESTART')
  session=str(uuid.uuid5(uuid.NAMESPACE_URL,'count14-dynteam-system:'+contract+':'+start['owner_boot_id']))
  directories=[home/n for n in before if n!='EXPLICIT_START_PUBLIC.json']
  need(len(directories)==len(records),'SYSTEM_HISTORY_NO_UNREGISTERED_OR_MISSING_PROBE')
  for seq,(p,r)in enumerate(zip(directories,records),1):
   budget.check();dstat=private_directory(p)
   need(int(p.name[:8])==seq==r['sequence']and type(r['intent_wall_ns'])is int and r['intent_wall_ns']>0,
        'SYSTEM_HISTORY_CONTIGUOUS_ORIGINAL_SEQUENCE_AND_INTENT_CLOCK')
   intent,iref=control(p/'INTENT_PUBLIC.json',budget);refs.append(iref)
   need(set(intent)=={'schema','sequence','request_id','session_id','owner_pid','owner_start_ticks','owner_boot_id','contract_sha256','key_path','qualification_only','OWN_endpoint'}and
        intent['schema']=='count14-dynteam-system-probe-intent-v1'and intent['sequence']==seq and
        intent['request_id']==p.name[9:]and intent['session_id']==session and intent['contract_sha256']==contract and
        intent['owner_boot_id']==old_birth['boot_id']and type(intent['owner_pid'])is int and intent['owner_pid']>0 and
        type(intent['owner_start_ticks'])is int and intent['owner_start_ticks']>0 and intent['qualification_only']is own,
        'SYSTEM_HISTORY_SAME_ORIGINAL_INTENT_REQUEST_CONTRACT_BOOT_AFFINITY')
   if own:
    from native_system_probe_child import OWN_endpoint_ok
    need(OWN_endpoint_ok(intent['OWN_endpoint']),'SYSTEM_HISTORY_OWN_INTENT_NEVER_PROVIDER')
   else:need(intent['OWN_endpoint']is None,'SYSTEM_HISTORY_PRODUCTION_NO_OWN_ENDPOINT')
   if r['state']=='NOT_STARTED':
    need(r['child_handle_present']is False and r['child_returncode']is None and r['exit_code']is None and
         r['terminal_present']is False and r['terminal']is None and type(r['failure_type'])is str,
         'SYSTEM_HISTORY_NOT_STARTED_NEVER_FABRICATED_EXIT0_OR_UNKNOWN_RELEASE')
    n,nref=control(p/'NOT_STARTED_PUBLIC.json',budget);refs.append(nref)
    need(n==dict(PUBLIC_code='DYNTEAM_SYSTEM_PROBE_POPEN_NOT_STARTED',sequence=seq,
          exception_type=r['failure_type'],request_replays=0)and
         probe_files(p)==['INTENT_PUBLIC.json','NOT_STARTED_PUBLIC.json'],
         'SYSTEM_HISTORY_ORIGINAL_NOT_STARTED_RECEIPT_NO_REPLAY')
    terminal=None
   else:
    need(r['state']=='HTTP_PHYSICAL_TERMINAL'and r['exit_code']==0 and
         (not r['child_handle_present']or r['child_returncode']==0)and r['terminal_present']is True,
         'SYSTEM_HISTORY_NO_LIVE_OR_UNPROVEN_PHYSICAL_UNKNOWN_DISCARDED')
    c,cref=control(p/'CUSTODY_PUBLIC.json',budget);t,tref=control(p/'TERMINAL_PUBLIC.json',budget);refs.extend((cref,tref))
    need(c==dict(schema='count14-dynteam-system-probe-custody-v1',sequence=seq,state='HTTP_PHYSICAL_TERMINAL',
         exit_code=0,upper_charge_preserved=True,experiment_permits_used=0,request_replays=0),
         'SYSTEM_HISTORY_REAL_PARENT_PHYSICAL_TERMINAL_CUSTODY')
    keys={'schema','sequence','session_id','request_id','contract_sha256','original_probe_source_sha256','retries',
          'original_financial_tables_written','request_replays','system_cost_not_experiment','included_in_search_budget',
          'http_status','reported_tokens','possible_unmeasured_tokens_upper','started_at','completed_at','healthy','error_type',
          'elapsed_seconds','prompt_is_fixed_health_only'}
    need(set(t)in(keys,keys|{'prompt_tokens','completion_tokens'})and
         t['prompt_is_fixed_health_only']is True and type(t['elapsed_seconds'])in(int,float)and
         math.isfinite(t['elapsed_seconds'])and t['elapsed_seconds']>=0 and
         t['schema']=='count14-dynteam-system-probe-terminal-v1'and t['sequence']==seq and
         t['session_id']==session and t['request_id']==intent['request_id']and t['contract_sha256']==contract and
         t['original_probe_source_sha256']==ORIGINAL_SHA and t['retries']==t['original_financial_tables_written']==t['request_replays']==0 and
         t['system_cost_not_experiment']is True and t['included_in_search_budget']is False and
         type(t['http_status'])is int and 100<=t['http_status']<=599,
         'SYSTEM_HISTORY_ORIGINAL_TERMINAL_FINANCIAL_AND_HTTP_FIELDS')
    measured,upper=t['reported_tokens'],t['possible_unmeasured_tokens_upper']
    need((measured is None or type(measured)is int and measured>0)and type(upper)is int and upper>=0 and
         (measured is None or upper==0)and r['terminal']==dict(reported_tokens=measured,
          possible_unmeasured_tokens_upper=upper,http_status=t['http_status']),
         'SYSTEM_HISTORY_RAM_AND_ORIGINAL_USAGE_NONE_UPPER_EXACT_NOT_ZERO_FILL')
    if measured is not None:
     need(all(type(t.get(k))is int and t[k]>=0 for k in('prompt_tokens','completion_tokens'))and
          t['prompt_tokens']+t['completion_tokens']==measured,'SYSTEM_HISTORY_ORIGINAL_TWO_REPORTED_USAGE_SCALARS')
    begin,end=(datetime.datetime.fromisoformat(t[k])for k in('started_at','completed_at'))
    need(begin.tzinfo is not None and end.tzinfo is not None and begin<=end and type(t['healthy'])is bool and
         (t['http_status']==200 or not t['healthy'])and
         probe_files(p)==['CUSTODY_PUBLIC.json','INTENT_PUBLIC.json','TERMINAL_PUBLIC.json'],
         'SYSTEM_HISTORY_ORIGINAL_TIMES_AND_FAILED_HTTP_NEVER_HEALTHY')
    terminal=copy.deepcopy(t) # Exact original scalar controls retained only in RAM.
   output.append(dict(sequence=seq,request_id=p.name[9:],directory=p,child=None,state=r['state'],terminal=terminal,
       exit_code=r['exit_code'],failure_type=r['failure_type'],intent_wall_ns=r['intent_wall_ns']))
   need(private_directory(p)==dstat,'SYSTEM_HISTORY_PROBE_DIRECTORY_IDENTITY_DRIFT')
 if records:need(cfg['last_intent_wall']==records[-1]['intent_wall_ns']and type(cfg['last_intent_mono'])is int,
                 'SYSTEM_HISTORY_ORIGINAL_LAST_INTENT_CLOCKS_PRESERVED_NOT_RECONSTRUCTED')
 for r in refs:
  _,again=control(Path(r['path']),budget);need(again==r,'SYSTEM_HISTORY_CONTROL_BYTES_CHANGED_DURING_SCAN')
 need(before==leaves()and private_directory(home)==identity,'SYSTEM_HISTORY_NO_CONCURRENT_LEAF_OR_ROOT_DRIFT')
 closed=row['history_control_bindings']
 need(closed==dict(schema='count14-original-sealed-SYSTEM-history-control-bindings-v1',home=str(home),
      home_identity=list(identity),control_references=refs),
      'SYSTEM_HISTORY_CLOSED_ORIGINAL_SOURCE_CONTROLS_EXACT')
 measured=sum((r['terminal']or{}).get('reported_tokens')or 0 for r in output)
 upper=sum((r['terminal']or{}).get('possible_unmeasured_tokens_upper',0)for r in output)
 physical=sum(r['state']=='HTTP_PHYSICAL_TERMINAL'for r in output)
 need((measured,upper,physical)==(original_public['reported_SYSTEM_tokens'],original_public['unmeasured_SYSTEM_upper'],
      original_public['HTTP_physical_terminal']),'SYSTEM_HISTORY_ALL_ORIGINAL_PUBLIC_TOTALS_EQUAL')
 return dict(registered=True,records=output,session_id=session,public=dict(registered=True,sequence=cfg['sequence'],
     explicitly_started=cfg['started'],HTTP_physical_terminal=physical,SYSTEM_occupied_slots=0,
     reported_SYSTEM_tokens=measured,unmeasured_SYSTEM_upper=upper,reported_None_records=sum(r['terminal']is not None and
       r['terminal']['reported_tokens']is None for r in output),NOT_STARTED_records=sum(r['state']=='NOT_STARTED'for r in output),
     source_history_complete=True,no_original_monotonic_rebased_or_health_fabricated=True,
     raw_request_session_key_and_body_excluded=True)),refs

class VerifiedSystemHistory:
 __slots__=('_seal','_snapshot','_references','_source','OWN')
 def __init__(self,*a,**k):raise ValueError('SYSTEM_HISTORY_ONLY_ORIGINAL_TYPED_NEW_BIRTH_VERIFIER')
 def __setattr__(self,n,v):
  need(not hasattr(self,'_seal'),'SYSTEM_HISTORY_IMMUTABLE_CAPABILITY');object.__setattr__(self,n,v)
 def public(self):return copy.deepcopy(self._snapshot['public'])
 @property
 def paid_activation_authorized(self):return False
 @property
 def live_scheduler_restored(self):return False
 @property
 def whole_runnable_ready(self):return False

def _self_pin():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def _publish(core,*,source_cap,service_reference,read_budget,own):
 """Append-only PUBLIC-control hashes while the exact source cap is live.

 This does not edit the existing original service SOURCE/ISSUED or financial
 schema. The separate sidecar binds timestamps/None/raw controls to OLD birth,
 so a later valid-looking metadata rewrite cannot be mistaken for history.
 """
 verify_sources()
 from dataclasses import asdict
 import durable_service_source_controls as C
 import source_services_controls as S
 import paid_cold_material as M
 from bounded_metadata_ro import ReadBudget
 from native_peer_registry import process_birth
 from normal_cold_sealer import save_candidate
 need(type(read_budget)is ReadBudget and type(source_cap)is S.RetiredServiceSourceControls and
      source_cap.OWN is own and core.qualification_only is own and source_cap.source_birth==process_birth(os.getpid()),
      'SYSTEM_HISTORY_SOURCE_ONLY_EXACT_LIVE_TYPED_RETIRED_SERVICE_CAP')
 if own:need(core.home.name.startswith('OWN-'),'SYSTEM_HISTORY_SOURCE_OWN_HOME_ONLY')
 else:need(M.digest(core.contract)in CONTRACTS and core.home==Path(core.contract['arms'][0]['root'])/'owner',
           'SYSTEM_HISTORY_SOURCE_ONLY_EXACT_APPROVED_CONTRACTS')
 S.verify_registered_source(source_cap,core=core,read_budget=read_budget)
 original,record=C._read_complete(service_reference,core.home,own=own,budget=read_budget)
 before=source_cap.snapshot()
 need(original['source_controls']==before and original['old_owner_birth']==asdict(source_cap.source_birth),
      'SYSTEM_HISTORY_SOURCE_EXACT_ORIGINAL_DURABLE_SOURCE_REFERENCE')
 data,refs=_read_bound(core.home/'system-health',before['SYSTEM'],asdict(source_cap.source_birth),
     M.digest(core.contract),own=own,budget=read_budget)
 leaf=core.home/(OWN_LEAF_NAME if own else LEAF_NAME)
 leaf.mkdir(mode=0o700,parents=False,exist_ok=False)
 body=dict(schema='count14-retired-system-history-source-v1',OWN=own,source_module_sha256=_self_pin(),
     source_pins=dict(PINS),old_owner_birth=asdict(source_cap.source_birth),contract_sha256=M.digest(core.contract),
     owner_home=M.descriptor(core.home),source_directory=M.descriptor(leaf),
     original_service_source=record,original_service_controls_sha256=M.digest(before),
     original_history_public=data['public'],original_control_references=refs,
     live_scheduler_restored=False,paid_activation_authorized=False,whole_runnable_ready=False)
 saved=save_candidate(leaf/'SOURCE_PUBLIC.json',body)
 S.verify_registered_source(source_cap,core=core,read_budget=read_budget)
 again,again_refs=_read_bound(core.home/'system-health',source_cap.snapshot()['SYSTEM'],asdict(source_cap.source_birth),
     M.digest(core.contract),own=own,budget=read_budget)
 need(source_cap.snapshot()==before and again==data and again_refs==refs and
      C._read_complete(service_reference,core.home,own=own,budget=read_budget)==(original,record),
      'SYSTEM_HISTORY_SOURCE_DRIFT_RETAIN_PARTIAL_NO_RETRY')
 marker=dict(schema='count14-retired-system-history-ISSUED-v1',OWN=own,source_module_sha256=_self_pin(),
     source_identity=saved['identity'],source_sha256=saved['sha256'],old_owner_birth=body['old_owner_birth'],
     live_scheduler_restored=False,paid_activation_authorized=False,whole_runnable_ready=False)
 issued=save_candidate(leaf/'ISSUED_PUBLIC.json',marker)
 fd=os.open(core.home,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
 return dict(path=saved['identity']['path'],sha256=saved['sha256'],issued_sha256=issued['sha256'])

def publish_history(core,*,source_cap,service_reference,read_budget):
 return _publish(core,source_cap=source_cap,service_reference=service_reference,read_budget=read_budget,own=False)
def publish_OWN_history(core,*,source_cap,service_reference,read_budget):
 return _publish(core,source_cap=source_cap,service_reference=service_reference,read_budget=read_budget,own=True)

class HistoryReference:
 __slots__=('_path','_pin','_seal','OWN')
 def __init__(self,*a,**k):raise ValueError('SYSTEM_HISTORY_ONLY_FIXED_REFERENCE_LOADER')
 def __setattr__(self,n,v):
  need(not hasattr(self,'_seal'),'SYSTEM_HISTORY_REFERENCE_IMMUTABLE');object.__setattr__(self,n,v)
def _reference(path,pin,*,own):
 p=Path(path)
 need(p.is_absolute()and p.resolve()==p and p.name=='SOURCE_PUBLIC.json'and
      p.parent.name==(OWN_LEAF_NAME if own else LEAF_NAME)and type(pin)is str and
      re.fullmatch('[0-9a-f]{64}',pin)is not None,'SYSTEM_HISTORY_EXACT_REFERENCE_NAMESPACE_NOT_AUTHORITY')
 r=object.__new__(HistoryReference);r._path,r._pin,r.OWN=str(p),pin,own;r._seal=_SEAL;return r
def load_reference(path,sha256):return _reference(path,sha256,own=False)
def load_OWN_reference(path,sha256):return _reference(path,sha256,own=True)

def _read(reference,*,history_reference,owner,ticket,read_budget,own):
 verify_sources()
 import durable_service_source_controls as C
 from bounded_metadata_ro import ReadBudget
 need(type(read_budget)is ReadBudget,'SYSTEM_HISTORY_ORIGINAL_FINITE_METADATA_BUDGET')
 verify=C.verify_OWN_reference if own else C.verify_reference
 source=verify(reference,owner=owner,ticket=ticket,read_budget=read_budget)
 need(type(source)is C.VerifiedRetiredServiceControls and source.OWN is own and
      source.old_owner_birth.boot_id==source.new_owner_birth.boot_id,
      'SYSTEM_HISTORY_ORIGINAL_NEW_BIRTH_SAME_BOOT_THREE_LOCKS_CAPABILITY')
 if own:need(owner.core.qualification_only is True and owner.core.home.name.startswith('OWN-'),
             'SYSTEM_HISTORY_OWN_NEVER_PRODUCTION_RECEIVER')
 else:need(not owner.core.qualification_only and source.contract_sha256 in CONTRACTS and
           owner.core.home==Path(owner.core.contract['arms'][0]['root'])/'owner',
           'SYSTEM_HISTORY_ONLY_APPROVED_TWO_NEW_ARM_CONTRACTS')
 from dataclasses import asdict
 import paid_cold_material as M
 need(type(history_reference)is HistoryReference and history_reference._seal is _SEAL and history_reference.OWN is own and
      Path(history_reference._path)==owner.core.home/(OWN_LEAF_NAME if own else LEAF_NAME)/'SOURCE_PUBLIC.json',
      'SYSTEM_HISTORY_T_DERIVED_HOME_AND_TYPED_SOURCE_NAMESPACE')
 leaf=Path(history_reference._path).parent;private_directory(leaf)
 marker,_=M.private_read(leaf/'ISSUED_PUBLIC.json',limit=262144)
 need(marker['schema']=='count14-retired-system-history-ISSUED-v1'and marker['OWN']is own and
      marker['source_module_sha256']==_self_pin()and marker['source_identity']['path']==history_reference._path and
      marker['source_sha256']==history_reference._pin and marker['old_owner_birth']==asdict(source.old_owner_birth)and
      marker['live_scheduler_restored']is marker['paid_activation_authorized']is marker['whole_runnable_ready']is False,
      'SYSTEM_HISTORY_OLD_BIRTH_COMPLETE_MARKER_BEFORE_SOURCE_READ')
 path=M.existing(marker['source_identity'],private=True)
 body,_=M.private_read(path,history_reference._pin,limit=8*1024*1024)
 expected_ref=source._reference
 need(body['schema']=='count14-retired-system-history-source-v1'and body['OWN']is own and
      body['source_module_sha256']==_self_pin()and body['source_pins']==PINS and
      body['old_owner_birth']==asdict(source.old_owner_birth)and body['contract_sha256']==source.contract_sha256 and
      body['owner_home']==M.descriptor(owner.core.home)and body['source_directory']==M.descriptor(leaf)and
      body['original_service_source']==expected_ref and body['original_service_controls_sha256']==M.digest(source.snapshot())and
      body['live_scheduler_restored']is body['paid_activation_authorized']is body['whole_runnable_ready']is False,
      'SYSTEM_HISTORY_SOURCE_SIDE_CLOSED_CONTROL_AND_ORIGINAL_DURABLE_REFERENCE_BINDING')
 row=source.component('SYSTEM')
 snapshot,refs=_read_bound(owner.core.home/'system-health',row,asdict(source.old_owner_birth),source.contract_sha256,
     own=own,budget=read_budget)
 need(body['original_history_public']==snapshot['public']and body['original_control_references']==refs,
      'SYSTEM_HISTORY_ALL_ORIGINAL_SOURCE_CONTROL_BYTES_IDENTITIES_AND_TIMES_UNCHANGED')
 again=verify(reference,owner=owner,ticket=ticket,read_budget=read_budget)
 need(again.snapshot()==source.snapshot()and again.new_owner_birth==source.new_owner_birth,
      'SYSTEM_HISTORY_ORIGINAL_PAIR_CAP_AND_SOURCE_STILL_CURRENT_AFTER_FULL_SCAN')
 result=object.__new__(VerifiedSystemHistory)
 result._snapshot,result._references,result._source,result.OWN=snapshot,tuple(refs),source,own
 result._seal=_SEAL;return result

def read_history(reference,*,history_reference,owner,ticket,read_budget):
 return _read(reference,history_reference=history_reference,owner=owner,ticket=ticket,read_budget=read_budget,own=False)
def read_OWN_history(reference,*,history_reference,owner,ticket,read_budget):
 return _read(reference,history_reference=history_reference,owner=owner,ticket=ticket,read_budget=read_budget,own=True)
