"""Fixed ledger RAM/capacity/resource control source; no financial rewriting.

Only framework control fields and fixed schema/bool queries. No bodies,
result/event metadata, broad DB pin, live SQL under science locks, method
mutation, default-empty custody, callback serialization, or activation.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from dataclasses import asdict
from pathlib import Path
from types import MethodType,CodeType,SimpleNamespace
import copy
import fcntl
import hashlib
import importlib
import marshal
import os
import re
import sqlite3
import stat
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget,ram_lock,readonly
from native_peer_registry import process_birth
from budget import Ledger
from model_capacity import ModelCapacity
from original_relay_core import OriginalRelayCore
from native_scientific_http import NativeScientificHttpServer
from native_cohort_resources import NativeCohortResources,CohortAllocation

SCHEMA='count14-original-financial-runtime-control-source-v1'
PINS=dict(budget='a05ca90afffb7c149766cf4b74126eb94ba79910afd72049a1ff54d2bc50df8f',
 model_capacity='1df72fa17fa25159befd4fed8c5751921c60720d53212dddac57c9de283b09ba',
 original_relay_core='89ac900e66caa67887504522c574c1870f7a8faf51542fe248ca7f35b1541556',
 native_cohort_resources='26d1181e98dbf9972b517c1cb621f2b16d0d84780eef9bea83ab9eca7755ebb5',
 native_scientific_http='eb08ff0d770f2609f24e568d4724e427dbde0b5327e7067d70759f0855e789d3',
 normal_inert_cut='aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',
 metadata_inert_pair='83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da',
 bounded_metadata_ro='621cd0db6da2d1e6422537f6ae2188ac8466627efe803d8b4d39f260bfb7c249')
METHODS=('account','frontier','reserve','model_paused','global_unresolved','global_logical_unresolved',
 'tx','latch_fault','admission_fault','unknown_statistics','_unknown_thresholds','register')
CONTROL_FIELDS=('native_unmanaged_cli','_dynteam_qualification_only','model_capacity_global_cap','model_capacity_owner_epoch')


def verify_sources():
 for name,pin in PINS.items():
  p=Path(importlib.import_module(name).__file__)
  M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and hashlib.sha256(p.read_bytes()).hexdigest()==pin,
   'FINANCIAL_RUNTIME_SOURCE_FIXED_ORIGINAL_COMPONENTS')
 return dict(PINS)


def _fields(ledger):
 return {name:dict(present=hasattr(ledger,name),value=copy.deepcopy(getattr(ledger,name)) if hasattr(ledger,name) else None)
         for name in CONTROL_FIELDS}


def _service(scope,service,core,budget):
 matches=[t for t,s in core.servers.items() if s is service]
 if type(service)is not NativeScientificHttpServer or len(matches)!=1:
  # Retain this scope as UNBOUND, not an empty or physically terminal service.
  return dict(kind='UNREGISTERED_NATIVE_SERVICE_CONTROL_RETAINED',metadata_decoder_available=False,
   physical_terminal=False,runtime_handle_serialized=False)
 t=matches[0]
 M.need(service.ledger is core.ledger and service.scope==scope,
  'FINANCIAL_RUNTIME_SOURCE_SAME_ORIGINAL_HTTP_SERVICE')
 with ram_lock(service.registry_lock,budget):
  row=dict(kind='ORIGINAL_SCIENTIFIC_HTTP',trajectory=t,metadata_decoder_available=True,
   listener_identity_sha256=service.listener_identity_sha256,closed=service.closed,network_closed=service.network_closed,
   listener_stopped=service.listener_stopped,lifecycle_storage_unknown=service.lifecycle_storage_unknown,
   request_count=len(service.requests),retained_count=len(service.retained),accepted_socket_count=len(service.accepted_sockets))
 row.update(listener_thread_alive=service.thread is not None and service.thread.is_alive(),
  listener_loop_finished=service.loop_finished.is_set(),listener_fd_closed=service.socket.fileno()==-1,
  runtime_handle_serialized=False)
 row['physical_terminal']=bool(row['closed']and row['network_closed']and row['listener_stopped']and
  row['listener_loop_finished']and not row['listener_thread_alive']and row['listener_fd_closed']and
  not row['lifecycle_storage_unknown']and row['request_count']==row['retained_count']==row['accepted_socket_count']==0)
 return row


def _method_shapes(methods):
 result={}
 for name,bound in methods.items():
  M.need(type(bound)is MethodType,'FINANCIAL_RUNTIME_SOURCE_ORIGINAL_BOUND_METHOD_GRAPH')
  code=bound.__func__.__code__
  result[name]=dict(module=bound.__func__.__module__,function=code.co_name,file=code.co_filename,
   first_line=code.co_firstlineno,code_sha256=hashlib.sha256(marshal.dumps(code)).hexdigest(),
   semantic_code_sha256=semantic_code_sha256(code))
 return result


def semantic_code_sha256(code):
 """Normalize source coordinates ONLY, recursively; retain semantic structure.

 co_qualname, operations, exception table, names, constants, flags, argument
 counts, local variables, cell/free variables and closure structure remain.
 No global, callable, locals, model value or exception message is serialized.
 """
 M.need(type(code)is CodeType,'FINANCIAL_RUNTIME_SOURCE_EXACT_METHOD_CODE_ONLY')
 def normalized(value):
  if type(value)is CodeType:
   return value.replace(co_filename='',co_firstlineno=1,co_linetable=b'',
    co_consts=tuple(normalized(v)for v in value.co_consts))
  return value
 return hashlib.sha256(marshal.dumps(normalized(code))).hexdigest()


def _capture(core,capacity,resources,*,read_budget,own):
 M.need(type(read_budget)is ReadBudget,'FINANCIAL_RUNTIME_SOURCE_FINITE_METADATA_BUDGET')
 read_budget.check();l=core.ledger
 M.need(type(core)is OriginalRelayCore and type(l)is Ledger and core.qualification_only is own and
  not l.mutex._is_owned(),'FINANCIAL_RUNTIME_SOURCE_EXACT_REGISTERED_COMPONENTS_OUTSIDE_SCIENCE_LOCK')
 verify_sources()
 M.need((own and any(p.startswith('OWN-')for p in core.home.parts))or
  (not own and core.home==Path(core.contract['arms'][0]['root'])/'owner'),
  'FINANCIAL_RUNTIME_SOURCE_OWN_NAMESPACE_OR_ORIGINAL_REGISTERED_HOME')
 with ram_lock(l.mutex,read_budget):
  M.need(type(l.memory_faults)is dict and type(l.native_services)is dict and type(l._dynteam_catalogues)is dict and
   set(l._dynteam_catalogues)==set(core.rows),'FINANCIAL_RUNTIME_SOURCE_EXPLICIT_COMPLETE_RAM_NO_EMPTY_DEFAULT')
  faults=copy.deepcopy(l.memory_faults);services=dict(l.native_services);fields=_fields(l)
  M.need(all(t in core.rows or t=='GLOBAL'for t in faults)and
   all(type(code)is str and re.fullmatch('[A-Z][A-Z0-9_]*',code)for code in faults.values()),
   'FINANCIAL_RUNTIME_SOURCE_FAULT_PUBLIC_CODES_ONLY_NOT_MESSAGES')
  catalogues={t:list(r)for t,r in l._dynteam_catalogues.items()}
  M.need(catalogues=={t:list(r['roles'])for t,r in core.rows.items()},'FINANCIAL_RUNTIME_SOURCE_SAME_ROLE_CATALOGUES')
  methods={name:getattr(l,name)for name in METHODS}
  M.need(all(type(m)is MethodType and m.__self__ is l for m in methods.values()),
   'FINANCIAL_RUNTIME_SOURCE_SAME_ORIGINAL_LEDGER_BOUND_METHODS')
  transaction=l.db.in_transaction
  cap=None
  if capacity is not None:
   M.need(type(capacity)is ModelCapacity and capacity.ledger is l and type(capacity.authorizers)is dict and
    all(callable(a)for a in capacity.authorizers.values())and
    getattr(l,'model_capacity_owner_epoch',None)==capacity.epoch and
    getattr(l,'model_capacity_global_cap',None)==capacity.global_cap,
    'FINANCIAL_RUNTIME_SOURCE_ORIGINAL_CAPACITY_DOMAIN_NOT_RETAGGED')
   cap=dict(global_cap=capacity.global_cap,aux_cap=capacity.aux_cap,epoch=capacity.epoch,
    transport_pin=capacity.transport_pin,classifier_pin=capacity.classifier_pin,
    authorizer_scope_keys=sorted(capacity.authorizers),authorizer_callable_count=len(capacity.authorizers),
    callable_or_old_process_handle_serialized=False,new_owner_binding_qualified=False)
  resource=None
  if resources is not None:
   M.need(type(resources)is NativeCohortResources and resources.core is core and resources.ledger is l and
    type(resources.allocation)is CohortAllocation,'FINANCIAL_RUNTIME_SOURCE_ORIGINAL_RESOURCES')
   resources.allocation.checked()
   launches=copy.deepcopy(resources.launch_reservations)
   M.need(type(launches)is dict and all(type(k)is tuple and len(k)==2 and k[0]in core.rows and
    k[1]in core.rows[k[0]]['roles']and type(v)is int and v>=0 for k,v in launches.items()),
    'FINANCIAL_RUNTIME_SOURCE_LOSSLESS_TYPED_LAUNCH_FORECASTS')
   resource=dict(allocation=asdict(resources.allocation),state=copy.deepcopy(resources.state),
    launch_reservations=[dict(trajectory=t,role=r,forecast_bytes=n)for(t,r),n in sorted(launches.items())],
    failures=copy.deepcopy(resources.failures),next_refresh_mono=resources.next_refresh_mono,
    predicate_proof=copy.deepcopy(resources.predicate_proof),registered_capacity_count=len(resources.capacities),
    expected_capacity_is_registered=capacity is not None and any(c is capacity for c in resources.capacities),
    current_observation_reused_for_new_owner_admission=False)
 read_budget.check()
 service_controls={scope:_service(scope,s,core,read_budget)for scope,s in sorted(services.items())}
 def unlocked():M.need(not l.mutex._is_owned(),'FINANCIAL_RUNTIME_SOURCE_ALL_SQL_OUTSIDE_SCIENCE_LOCK')
 with readonly(l.home/'ledger.sqlite',read_budget,unlocked)as db:
  tables={r[0]for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  schema={name:[dict(cid=r[0],name=r[1],type=r[2],notnull=bool(r[3]),primary_key=bool(r[5]))
    for r in db.execute('PRAGMA table_info("'+name+'")')]
   for name in ('accounts','requests','operations','aux_scopes','aux_permits','unknown_charges','model_control')}
  policy=None
  if 'unknown_policy'in tables:
   r=db.execute('SELECT version FROM unknown_policy WHERE singleton=1').fetchone();policy=None if r is None else r[0]
  row=db.execute('SELECT paused,epoch,reason FROM model_control WHERE singleton=1').fetchone()
  M.need(row is not None,'FINANCIAL_RUNTIME_SOURCE_MODEL_CONTROL_EXISTS')
  model=dict(paused=row[0],epoch=row[1],reason=row[2])
 # Method code and canonical identities are evaluated only after leaving RAM
 # locks. No method is invoked, mutated, or used to configure a live DB.
 marker=M.descriptor(l.owner_marker)
 M.existing(marker,private=True)
 M.need(Path(marker['path'])==l.home/'owner.open','FINANCIAL_RUNTIME_SOURCE_ORIGINAL_OWNER_MARKER')
 result=dict(schema=SCHEMA,OWN=own,source_owner_birth=asdict(process_birth(os.getpid())),
  contract_sha256=M.digest(core.contract),ledger_database=M.descriptor(l.home/'ledger.sqlite'),
  owner_marker=marker,memory_faults=faults,native_services=service_controls,
  native_service_count=len(services),all_original_native_services_explicitly_absent=not services,
  unbound_native_service_count=sum(not r['metadata_decoder_available']for r in service_controls.values()),
  ledger_attribute_controls=fields,catalogues=catalogues,source_connection_in_transaction=transaction,
  original_method_graph=_method_shapes(methods),capacity=cap,resources=resource,
  unknown_policy_version=policy,original_control_schema=schema,model_control=model,
  source_pins=dict(PINS),source_financial_rules_or_history_modified=False,
  current_resources_not_new_owner_authority=True,whole_runnable_ready=False,safe_to_TERM=False)
 with ram_lock(l.mutex,read_budget):
  M.need(l.memory_faults==faults and dict(l.native_services)==services and _fields(l)==fields and
   {name:getattr(l,name)for name in METHODS}==methods and l.db.in_transaction==transaction,
   'FINANCIAL_RUNTIME_SOURCE_RAM_OR_BOUND_METHODS_CHANGED_RETRY_OBSERVATION')
 read_budget.check();return result


def capture_registered(owner,*,read_budget):
 from native_cold_owner import NativeColdOwner
 from native_formal_cohort import NativeFormalCohort
 import normal_inert_cut as T
 M.need(type(owner)is NativeColdOwner and type(owner.core)is OriginalRelayCore and
  type(owner.scientific_smoke)is NativeFormalCohort and not owner.core.qualification_only,
  'FINANCIAL_RUNTIME_SOURCE_ORIGINAL_PRODUCTION_OWNER_GRAPH')
 issuer=owner.normal_inert_cut_issuer
 M.need(type(issuer)is T.NormalInertIssuer and issuer.owner is owner and issuer.ticket is not None,
  'FINANCIAL_RUNTIME_SOURCE_TRUE_ALREADY_ISSUED_NORMAL_INERT_TICKET')
 issuer._current();T._retired_transport(owner,read_budget)
 core=owner.core;cohort=owner.scientific_smoke
 M.need(cohort.final is not None and core.v2_dispositions.ledger is core.ledger and
  core.ledger._dynteam_v2_dispositions is core.v2_dispositions,
  'FINANCIAL_RUNTIME_SOURCE_ORIGINAL_V2_FINAL_AND_RESOURCE_GRAPH')
 result=_capture(core,cohort.final.capacity,core.cohort_resources,read_budget=read_budget,own=False)
 M.need(result['ledger_attribute_controls']['native_unmanaged_cli']==dict(present=True,value=True)and
  result['unknown_policy_version']=='USER_20261027_RESERVATION_V1',
  'FINANCIAL_RUNTIME_SOURCE_ORIGINAL_APPROVED_UNMANAGED_UNKNOWN_POLICY')
 issuer._current();return result


def capture_OWN_components(core,*,capacity=None,resources=None,read_budget):
 return _capture(core,capacity,resources,read_budget=read_budget,own=True)


# This sidecar is independent of the already-issued original normal-INERT
# ticket. It never amends the pre-candidate, original ticket or old ledger.
PUBLICATION='count14-original-financial-runtime-sidecar-INERT-v1'
COMMITTED='count14-original-financial-runtime-sidecar-ISSUED-v1'
LEAF='normal-financial-runtime-source-control-v1'
OWN_LEAF='OWN-normal-financial-runtime-source-control-v1'
_SEAL=object()
_PUBLICATIONS={}
_OWN_RECEIVERS={}
_SIX_SQL={
 'accounts':'SELECT COUNT(*),COALESCE(SUM(actual),0) FROM accounts',
 'requests':'SELECT COUNT(*),COALESCE(SUM(upper_bound),0),COALESCE(SUM(input),0),COALESCE(SUM(output),0) FROM requests',
 'operations':'SELECT COUNT(*) FROM operations',
 'unknown_charges':'SELECT COUNT(*),COALESCE(SUM(upper_bound),0) FROM unknown_charges',
 'aux_scopes':'SELECT COUNT(*) FROM aux_scopes',
 'aux_permits':'SELECT COUNT(*) FROM aux_permits',
}


def _self_pin():
 p=Path(__file__)
 M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and p.name=='financial_runtime_source_control.py',
  'FINANCIAL_RUNTIME_SIDECAR_FIXED_IMPLEMENTATION_SOURCE')
 return hashlib.sha256(p.read_bytes()).hexdigest()


def _budget(value):
 M.need(type(value)is ReadBudget,'FINANCIAL_RUNTIME_SIDECAR_FINITE_READ_BUDGET')
 value.check()


def _db_controls(ledger_path,queue_path,budget):
 """Fixed safe columns only; no result, events metadata or state pin."""
 _budget(budget)
 with readonly(ledger_path,budget,lambda:None)as db:
  finance={name:list(db.execute(sql).fetchone())for name,sql in _SIX_SQL.items()}
  schema={name:[dict(cid=r[0],name=r[1],type=r[2],notnull=bool(r[3]),primary_key=bool(r[5]))
   for r in db.execute('PRAGMA table_info("'+name+'")')]
   for name in ('accounts','requests','operations','aux_scopes','aux_permits','unknown_charges','model_control')}
  tables={r[0]for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  policy=None
  if 'unknown_policy'in tables:
   row=db.execute('SELECT version FROM unknown_policy WHERE singleton=1').fetchone()
   policy=None if row is None else row[0]
  row=db.execute('SELECT paused,epoch,reason FROM model_control WHERE singleton=1').fetchone()
  M.need(row is not None,'FINANCIAL_RUNTIME_SIDECAR_REAL_MODEL_CONTROL')
  model=dict(paused=row[0],epoch=row[1],reason=row[2])
 with readonly(queue_path,budget,lambda:None)as db:
  config=db.execute('SELECT manifest,cap FROM config WHERE singleton=1').fetchone()
  M.need(config is not None,'FINANCIAL_RUNTIME_SIDECAR_REAL_QUEUE_CONFIG')
  tables={r[0]for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  queue=dict(config=dict(manifest=config[0],cap=config[1]),job_state_counts={name:dict(present=name in tables,
   state_counts=([list(r)for r in db.execute('SELECT state,COUNT(*) FROM "'+name+'" GROUP BY state ORDER BY state')]
    if name in tables else None))for name in ('jobs','replacement_jobs','formal_final_control_jobs_v1')})
 return dict(six_financial_COUNT_SUM=finance,original_control_schema=schema,
  unknown_policy_version=policy,model_control=model,original_queue_controls=queue)


def _bind_db(controls,db,contract):
 M.need(controls['original_control_schema']==db['original_control_schema']and
  controls['unknown_policy_version']==db['unknown_policy_version']and controls['model_control']==db['model_control']and
  db['original_queue_controls']['config']==dict(manifest=M.digest(contract),cap=12),
  'FINANCIAL_RUNTIME_SIDECAR_RAM_AND_CURRENT_FIXED_DB_CONTROL_EQUALITY')


def _source_storage(core,queue,full,full_fd):
 import normal_inert_cut as T
 M.need(core.queue is queue and core.ledger.home==core.home/'ledger'and
  queue.home in (core.home/'queue',core.home/'final-queue')and
  full==core.home/'full-affinity-domain-control-v1','FINANCIAL_RUNTIME_SIDECAR_ORIGINAL_SOURCE_STORAGE_GRAPH')
 storage=dict(owner_home=M.descriptor(core.home),ledger_home=M.descriptor(core.ledger.home),
  ledger_database=M.descriptor(core.ledger.home/'ledger.sqlite'),queue_home=M.descriptor(queue.home),
  queue_database=M.descriptor(queue.home/'queue.sqlite'),full_used_directory=M.descriptor(full))
 for name in ('owner_home','ledger_home','queue_home','full_used_directory'):M.existing(storage[name],directory=True,private=True)
 for name in ('ledger_database','queue_database'):M.existing(storage[name],private=True)
 locks=[('ledger',M.descriptor(core.ledger.home/'owner.lock')),
  ('queue',M.descriptor(queue.home/'owner.lock')),('fullused',storage['full_used_directory'])]
 for kind,row in locks:M.existing(row,directory=kind=='fullused',private=True)
 T._validate_owned_locks([core.ledger.fd,queue.fd,full_fd],[row for kind,row in locks])
 return storage,locks


def _save(path,body):
 from normal_cold_sealer import save_candidate
 return save_candidate(path,body)


def _complete(leaf,body,*,final_guard):
 """O_EXCL SOURCE then final fresh check then O_EXCL ISSUED; never overwrite."""
 leaf.mkdir(mode=0o700,parents=False,exist_ok=False)
 body=dict(body,source_directory=M.descriptor(leaf),source_module_sha256=_self_pin(),source_pins=verify_sources(),
  inert_only=True,safe_to_TERM=False,paid_activation_authorized=False,whole_runnable_ready=False)
 reference=_save(leaf/'SOURCE.json',body)
 # If this fails, SOURCE remains a non-consumable partial forever. No marker
 # is synthesized and no automatic rerun replaces the old bytes.
 final_guard()
 marker=dict(schema=COMMITTED,OWN=body['OWN'],source_identity=reference['identity'],source_sha256=reference['sha256'],
  source_module_sha256=body['source_module_sha256'],old_owner_birth=body['old_owner_birth'],
  inert_only=True,safe_to_TERM=False,paid_activation_authorized=False,whole_runnable_ready=False)
 issued=_save(leaf/'ISSUED.json',marker)
 fd=os.open(leaf.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(fd)
 finally:os.close(fd)
 return dict(path=reference['identity']['path'],sha256=reference['sha256'],issued_identity=issued['identity'],
  issued_sha256=issued['sha256'],inert_only=True,whole_runnable_ready=False,safe_to_TERM=False)


def _source(owner,budget):
 import normal_inert_cut as T
 from native_cold_owner import NativeColdOwner
 _budget(budget)
 M.need(type(owner)is NativeColdOwner and type(owner.core)is OriginalRelayCore and not owner.core.qualification_only,
  'FINANCIAL_RUNTIME_SIDECAR_EXACT_ACTUAL_PRODUCTION_SOURCE')
 M.need(not owner.core.ledger.mutex._is_owned()and not owner.core.queue.mutex._is_owned(),
  'FINANCIAL_RUNTIME_SIDECAR_SOURCE_METADATA_IO_OUTSIDE_SCIENCE_LOCKS')
 verify_sources()
 issuer=owner.normal_inert_cut_issuer
 M.need(type(issuer)is T.NormalInertIssuer and issuer.owner is owner and type(issuer.ticket)is T.NormalInertTicket,
  'FINANCIAL_RUNTIME_SIDECAR_WAIT_TRUE_ALREADY_ISSUED_ORIGINAL_TICKET')
 issuer._current();ticket=issuer.ticket
 # This is the original SOURCE, not the new receiver: inspect original fixed
 # metadata only; do not pretend it can verify a post-retirement receiver cap.
 body=T._read_reference(ticket,own=False,read_budget=budget)
 current=process_birth(os.getpid());core=owner.core
 M.need(body['old_owner_birth']==asdict(current)and body['contract_sha256']==M.digest(core.contract)and
  body['owner_home']==M.descriptor(core.home)and core.home==Path(core.contract['arms'][0]['root'])/'owner'and
  core.home.is_relative_to((_C14_SCRATCH))and issuer.birth==current,
  'FINANCIAL_RUNTIME_SIDECAR_SAME_REAL_SOURCE_BIRTH_HOME_CONTRACT_NOT_NEW_AUTHORITY')
 retirement=T._retired_transport(owner,budget)
 M.need(retirement==body['transport_retirement'],
  'FINANCIAL_RUNTIME_SIDECAR_SAME_TRUE_RETIRED_ORIGINAL_HTTP_GRAPH')
 domain=core.formal_full_used_domain
 storage,locks=_source_storage(core,core.queue,domain.directory,domain.fd)
 M.need(all(body[k]==v for k,v in storage.items())and body['locks']==[[k,r]for k,r in locks],
  'FINANCIAL_RUNTIME_SIDECAR_ORIGINAL_TICKET_STORAGE_AND_LOCKS_UNCHANGED')
 return issuer,body,storage,locks,retirement


def publish_registered(owner,*,read_budget):
 """Once, on the true old source AFTER original INERT issue/HTTP retirement."""
 issuer,ticket_body,storage,locks,retirement=_source(owner,read_budget)
 M.need(id(owner)not in _PUBLICATIONS,'FINANCIAL_RUNTIME_SIDECAR_SINGLE_PUBLICATION_NO_RETRY')
 core=owner.core
 before=capture_registered(owner,read_budget=read_budget)
 db=_db_controls(core.ledger.home/'ledger.sqlite',core.queue.home/'queue.sqlite',read_budget)
 _bind_db(before,db,core.contract)
 after=capture_registered(owner,read_budget=read_budget)
 M.need(before==after,'FINANCIAL_RUNTIME_SIDECAR_SOURCE_CONTROLS_CHANGED_WAIT')
 _,current_ticket,current_storage,current_locks,current_retirement=_source(owner,read_budget)
 M.need(current_ticket==ticket_body and current_storage==storage and current_locks==locks and
  current_retirement==retirement,'FINANCIAL_RUNTIME_SIDECAR_SOURCE_BINDING_CHANGED_WAIT')
 ticket=issuer.ticket
 body=dict(schema=PUBLICATION,OWN=False,old_owner_birth=before['source_owner_birth'],
  contract_sha256=before['contract_sha256'],storage=storage,locks=[[k,r]for k,r in locks],
  original_ticket=dict(path=ticket.path,sha256=ticket.sha256,identity=M.descriptor(ticket.path)),
  original_financial_metadata=copy.deepcopy(ticket_body['financial_metadata']),
  original_transport_retirement=retirement,stable_before_after_controls=True,
  normal_financial_runtime_controls=before,current_fixed_db_controls=db)
 def guard():
  _,again,ss,ll,rr=_source(owner,read_budget)
  M.need(again==ticket_body and ss==storage and ll==locks and rr==retirement and
   capture_registered(owner,read_budget=read_budget)==before and
   _db_controls(core.ledger.home/'ledger.sqlite',core.queue.home/'queue.sqlite',read_budget)==db,
   'FINANCIAL_RUNTIME_SIDECAR_POST_SOURCE_WRITE_CHANGED_RETAIN_PARTIAL')
 _PUBLICATIONS[id(owner)]=dict(owner=owner,source_birth=process_birth(os.getpid()),publication_started=True)
 result=_complete(core.home/LEAF,body,final_guard=guard)
 _PUBLICATIONS[id(owner)]['reference']=copy.deepcopy(result)
 return result


def _read_complete(home,*,own,budget):
 _budget(budget);verify_sources()
 M.existing(M.descriptor(home),directory=True,private=True)
 leaf=home/(OWN_LEAF if own else LEAF)
 try:
  M.existing(M.descriptor(leaf),directory=True,private=True)
  # Never read/consume a partial SOURCE when its ISSUED marker is absent.
  marker,_=M.private_read(leaf/'ISSUED.json',limit=262144)
 except FileNotFoundError:raise M.PaidColdWait('FINANCIAL_RUNTIME_SIDECAR_WAIT_COMPLETE_SOURCE_AND_ISSUED')from None
 M.need(type(marker)is dict and set(marker)=={'schema','OWN','source_identity','source_sha256',
  'source_module_sha256','old_owner_birth','inert_only','safe_to_TERM','paid_activation_authorized','whole_runnable_ready'}and
  marker['schema']==COMMITTED and marker['OWN']is own and marker['source_module_sha256']==_self_pin()and
  marker['inert_only']is True and marker['safe_to_TERM']is marker['paid_activation_authorized']is marker['whole_runnable_ready']is False,
  'FINANCIAL_RUNTIME_SIDECAR_FIXED_COMPLETE_MARKER_NOT_AUTHORITY')
 M.need(marker['source_identity']['path']==str(leaf/'SOURCE.json'),
  'FINANCIAL_RUNTIME_SIDECAR_FIXED_DERIVED_SOURCE_PATH_BEFORE_READ')
 p=M.existing(marker['source_identity'],private=True)
 body,pin=M.private_read(p,marker['source_sha256'],limit=4*1024*1024)
 M.need(type(body)is dict and body['schema']==PUBLICATION and body['OWN']is own and
  body['source_directory']==M.descriptor(leaf)and body['source_module_sha256']==_self_pin()and
  body['source_pins']==verify_sources()and body['old_owner_birth']==marker['old_owner_birth']and
  body['storage']['owner_home']==M.descriptor(home)and body['stable_before_after_controls']is True and
  body['inert_only']is True and body['safe_to_TERM']is body['paid_activation_authorized']is body['whole_runnable_ready']is False,
  'FINANCIAL_RUNTIME_SIDECAR_COMMITTED_HASHED_COMPLETE_CONTROL_ENVELOPE')
 controls=body['normal_financial_runtime_controls']
 M.need(controls['schema']==SCHEMA and controls['OWN']is own and controls['source_owner_birth']==body['old_owner_birth']and
  controls['contract_sha256']==body['contract_sha256']and controls['ledger_database']==body['storage']['ledger_database']and
  controls['source_pins']==PINS and controls['source_connection_in_transaction']is False and
  controls['source_financial_rules_or_history_modified']is False,
  'FINANCIAL_RUNTIME_SIDECAR_EXACT_ORIGINAL_SOURCE_RUNTIME_SECTION')
 M.need(all('semantic_code_sha256'in row for row in controls['original_method_graph'].values())and
  set(controls['original_method_graph'])==set(METHODS),
  'FINANCIAL_RUNTIME_SIDECAR_COMPLETE_ORIGINAL_METHOD_SEMANTIC_SHAPES')
 return body,dict(path=str(p),sha256=pin,identity=M.descriptor(p),issued_identity=M.descriptor(leaf/'ISSUED.json'))


class VerifiedFinancialRuntimeSource:
 """Immutable control source only; never runnable or financial RW authority."""
 __slots__=('_controls','_body','_reference','_seal','OWN','old_owner_birth','new_owner_birth','contract_sha256')
 def __init__(self,*args,**kwargs):raise M.PaidColdWait('FINANCIAL_RUNTIME_SIDECAR_ONLY_FIXED_VERIFIER')
 def __setattr__(self,name,value):
  M.need(not hasattr(self,'_seal'),'FINANCIAL_RUNTIME_SIDECAR_IMMUTABLE_VERIFIED_CONTROL_SOURCE')
  object.__setattr__(self,name,value)
 @property
 def controls(self):
  M.need(self._seal is _SEAL,'FINANCIAL_RUNTIME_SIDECAR_EXACT_VERIFIED_CONTROL_SOURCE')
  return copy.deepcopy(self._controls)
 @property
 def safe_to_TERM(self):return False
 @property
 def paid_activation_authorized(self):return False
 @property
 def whole_runnable_ready(self):return False


def _verified(body,reference,current,*,own):
 value=object.__new__(VerifiedFinancialRuntimeSource)
 value._controls={'normal_financial_runtime_controls':copy.deepcopy(body['normal_financial_runtime_controls'])}
 value._body,value._reference=copy.deepcopy(body),copy.deepcopy(reference)
 value.OWN=own;value.old_owner_birth=M.birth(body['old_owner_birth']);value.new_owner_birth=current
 value.contract_sha256=body['contract_sha256'];value._seal=_SEAL
 return value


def load_registered_source(owner,*,ticket,read_budget):
 """Actual post-TERM receiver: original typed T + fixed pair + new sidecar."""
 import normal_inert_cut as T
 import metadata_inert_pair as P
 from native_cold_owner import NativeColdOwner
 _budget(read_budget)
 M.need(type(ticket)is T.NormalInertTicket,
  'FINANCIAL_RUNTIME_SIDECAR_PRODUCTION_REJECTS_OWN_OR_UNTYPED_REFERENCE')
 M.need(type(owner)is NativeColdOwner and type(owner.core)is OriginalRelayCore and
  not owner.core.ledger.mutex._is_owned()and not owner.core.queue.mutex._is_owned(),
  'FINANCIAL_RUNTIME_SIDECAR_RECEIVER_METADATA_IO_OUTSIDE_SCIENCE_LOCKS')
 verify_sources()
 cap=T.verify_inert_ticket(ticket,owner=owner,read_budget=read_budget)
 proof=P.verify_registered_pair(owner,ticket=ticket,read_budget=read_budget)
 M.need(type(cap)is T.VerifiedNormalInertCut and type(proof)is P.VerifiedMetadataPair and not proof.qualification_only and
  cap.new_owner_birth==proof.new_owner_birth==process_birth(os.getpid())and
  cap.old_owner_birth==proof.source_birth and cap.OWN is False and cap.old_owner_birth!=cap.new_owner_birth,
  'FINANCIAL_RUNTIME_SIDECAR_TRUE_NEW_BIRTH_AND_SOURCE_BOUND_ORIGINAL_PAIR')
 pair=owner.core.metadata_inert_pair;material=proof.material
 home=M.existing(cap.owner_home,directory=True,private=True)
 M.need(home==owner.core.home==Path(material['contract']['arms'][0]['root'])/'owner'and
  home.is_relative_to((_C14_SCRATCH)),'FINANCIAL_RUNTIME_SIDECAR_FIXED_REGISTERED_HOME_NOT_CALLER_PATH')
 body,reference=_read_complete(home,own=False,budget=read_budget)
 original_ticket_body=T._read_reference(ticket,own=False,read_budget=read_budget)
 storage=body['storage']
 M.need(body['old_owner_birth']==asdict(cap.old_owner_birth)and body['contract_sha256']==cap.contract_sha256 and
  body['original_ticket']==dict(path=ticket.path,sha256=ticket.sha256,identity=M.descriptor(ticket.path))and
  body['original_financial_metadata']==material['financial_metadata']and
  body['original_transport_retirement']==original_ticket_body['transport_retirement']and
  all(storage[k]==material[k]for k in ('owner_home','ledger_home','ledger_database','queue_home','queue_database','full_used_directory'))and
  body['locks']==[[kind,row]for kind,row in pair.control_lock_records]and
  storage['ledger_database']==cap.ledger_database and storage['queue_database']==cap.queue_database,
  'FINANCIAL_RUNTIME_SIDECAR_SAME_ORIGINAL_TICKET_BIRTH_STORAGE_FINANCIAL_DOMAIN')
 T._validate_owned_locks(pair.lock_fds,[row for kind,row in pair.control_lock_records])
 current=_db_controls(Path(storage['ledger_database']['path']),Path(storage['queue_database']['path']),read_budget)
 M.need(current==body['current_fixed_db_controls'],
  'FINANCIAL_RUNTIME_SIDECAR_CURRENT_ORIGINAL_SCHEMA_FINANCIAL_AND_MODEL_CONTROLS_EQUAL')
 _bind_db(body['normal_financial_runtime_controls'],current,material['contract'])
 again=T.verify_inert_ticket(ticket,owner=owner,read_budget=read_budget)
 M.need(again.old_owner_birth==cap.old_owner_birth and again.new_owner_birth==cap.new_owner_birth and
  _read_complete(home,own=False,budget=read_budget)==(body,reference),
  'FINANCIAL_RUNTIME_SIDECAR_RECEIVER_SOURCE_REFERENCE_CHANGED_WAIT')
 return _verified(body,reference,cap.new_owner_birth,own=False)


def _own_home(home,contract):
 M.existing(M.descriptor(home),directory=True,private=True)
 M.need(home.name.startswith('OWN-normal-financial-handoff-')and contract['arms'][0]['root']==str(home)and
  all(r['trajectory_id'].startswith('OWN-')and Path(r['root']).is_relative_to(home)
   for r in contract['trajectories']),'FINANCIAL_RUNTIME_SIDECAR_OWN_ROOT_AND_ALL_OWN_TRAJECTORIES_ONLY')


def publish_OWN_components(core,*,capacity,resources,queue,full_used_directory,full_used_fd,read_budget):
 """Independent OWN source issuer. NOT a fake production T/HTTP proof."""
 _budget(read_budget)
 M.need(type(core)is OriginalRelayCore and core.qualification_only is True,
  'FINANCIAL_RUNTIME_SIDECAR_ONLY_EXPLICIT_OWN_SOURCE_COMPONENTS')
 M.need(not core.ledger.mutex._is_owned()and not queue.mutex._is_owned(),
  'FINANCIAL_RUNTIME_SIDECAR_OWN_SOURCE_IO_OUTSIDE_SCIENCE_LOCKS')
 verify_sources()
 home=core.home;_own_home(home,core.contract)
 M.need(id(core)not in _PUBLICATIONS,'FINANCIAL_RUNTIME_SIDECAR_OWN_ONE_ISSUE_NO_RETRY')
 storage,locks=_source_storage(core,queue,full_used_directory,full_used_fd)
 before=capture_OWN_components(core,capacity=capacity,resources=resources,read_budget=read_budget)
 db=_db_controls(core.ledger.home/'ledger.sqlite',queue.home/'queue.sqlite',read_budget);_bind_db(before,db,core.contract)
 M.need(before==capture_OWN_components(core,capacity=capacity,resources=resources,read_budget=read_budget),
  'FINANCIAL_RUNTIME_SIDECAR_OWN_STABLE_BEFORE_AFTER_ORIGINAL_CONTROLS')
 body=dict(schema=PUBLICATION,OWN=True,old_owner_birth=before['source_owner_birth'],contract_sha256=M.digest(core.contract),
  OWN_contract=copy.deepcopy(core.contract),storage=storage,locks=[[k,r]for k,r in locks],
  original_ticket=None,original_financial_metadata=None,original_transport_retirement=None,
  actual_production_ticket_or_retired_six_HTTP_graph_qualified=False,
  stable_before_after_controls=True,normal_financial_runtime_controls=before,current_fixed_db_controls=db)
 def guard():
  ss,ll=_source_storage(core,queue,full_used_directory,full_used_fd)
  M.need(ss==storage and ll==locks and
   capture_OWN_components(core,capacity=capacity,resources=resources,read_budget=read_budget)==before and
   _db_controls(core.ledger.home/'ledger.sqlite',queue.home/'queue.sqlite',read_budget)==db,
   'FINANCIAL_RUNTIME_SIDECAR_OWN_CHANGED_RETAIN_PARTIAL_NO_REISSUE')
 _PUBLICATIONS[id(core)]=dict(core=core,source_birth=process_birth(os.getpid()),publication_started=True)
 result=_complete(home/OWN_LEAF,body,final_guard=guard)
 _PUBLICATIONS[id(core)]['reference']=copy.deepcopy(result)
 return result


class OWNFinancialSourceReference:
 __slots__=('_path','_pin','_seal')
 def __init__(self,*args,**kwargs):raise M.PaidColdWait('FINANCIAL_RUNTIME_SIDECAR_ONLY_OWN_REFERENCE_LOADER')
 def __setattr__(self,name,value):
  M.need(not hasattr(self,'_seal'),'FINANCIAL_RUNTIME_SIDECAR_OWN_REFERENCE_IMMUTABLE')
  object.__setattr__(self,name,value)
 @property
 def path(self):return self._path
 @property
 def sha256(self):return self._pin


def load_OWN_reference(path,pin):
 p=Path(path)
 M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and p.name=='SOURCE.json'and
  p.parent.name==OWN_LEAF and p.parent.parent.name.startswith('OWN-normal-financial-handoff-'),
  'FINANCIAL_RUNTIME_SIDECAR_OWN_FIXED_PATH_BEFORE_ANY_READ')
 value=object.__new__(OWNFinancialSourceReference);value._path=str(p);value._pin=M.sha(pin);value._seal=_SEAL
 return value


def load_OWN_source(reference,*,read_budget):
 """Acquire real original OWN locks AFTER true source exit; metadata only."""
 import normal_inert_cut as T
 _budget(read_budget);verify_sources()
 M.need(type(reference)is OWNFinancialSourceReference and reference._seal is _SEAL,
  'FINANCIAL_RUNTIME_SIDECAR_OWN_VERIFIER_REJECTS_PRODUCTION_TICKET')
 checked=load_OWN_reference(reference.path,reference.sha256);home=Path(checked.path).parent.parent
 body,ref=_read_complete(home,own=True,budget=read_budget)
 M.need(ref['path']==checked.path and ref['sha256']==checked.sha256 and
  body['actual_production_ticket_or_retired_six_HTTP_graph_qualified']is False and
  body['original_ticket']is body['original_financial_metadata']is body['original_transport_retirement']is None,
  'FINANCIAL_RUNTIME_SIDECAR_OWN_NOT_PRODUCTION_CAPABILITY')
 _own_home(home,body['OWN_contract'])
 M.need(body['contract_sha256']==M.digest(body['OWN_contract']),
  'FINANCIAL_RUNTIME_SIDECAR_OWN_FROZEN_CONTROL_CONTRACT')
 storage=body['storage'];old=M.birth(body['old_owner_birth']);current=process_birth(os.getpid())
 M.need(old!=current and old.uid==current.uid and M.nonexecuting(old,current),
  'FINANCIAL_RUNTIME_SIDECAR_OWN_TRUE_TWO_BIRTHS_OLD_SOURCE_ENDED')
 M.need(Path(storage['ledger_home']['path'])==home/'ledger'and Path(storage['queue_home']['path'])==home/'queue'and
  Path(storage['ledger_database']['path'])==home/'ledger/ledger.sqlite'and
  Path(storage['queue_database']['path'])==home/'queue/queue.sqlite'and
  Path(storage['full_used_directory']['path'])==home/'full-affinity-domain-control-v1',
  'FINANCIAL_RUNTIME_SIDECAR_OWN_ALL_STORAGE_CANONICAL_WITHIN_SANDBOX')
 for key in ('owner_home','ledger_home','queue_home','full_used_directory'):M.existing(storage[key],directory=True,private=True)
 for key in ('ledger_database','queue_database'):M.existing(storage[key],private=True)
 expected=[['ledger',M.descriptor(home/'ledger/owner.lock')],['queue',M.descriptor(home/'queue/owner.lock')],
  ['fullused',storage['full_used_directory']]]
 M.need(body['locks']==expected,'FINANCIAL_RUNTIME_SIDECAR_OWN_EXACT_THREE_ORIGINAL_LOCKS')
 fds=[]
 try:
  for kind,row in expected:
   M.existing(row,directory=kind=='fullused',private=True)
   fd=os.open(row['path'],os.O_RDONLY|os.O_NOFOLLOW|(os.O_DIRECTORY if kind=='fullused'else 0));fds.append(fd)
   try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:raise M.PaidColdWait('FINANCIAL_RUNTIME_SIDECAR_OWN_WAIT_ORIGINAL_LOCK_NO_FORCE_UNLOCK')from None
  T._validate_owned_locks(fds,[row for kind,row in expected])
  M.need(M.nonexecuting(old,current),'FINANCIAL_RUNTIME_SIDECAR_OWN_OLD_SOURCE_RECHECK')
  db=_db_controls(Path(storage['ledger_database']['path']),Path(storage['queue_database']['path']),read_budget)
  M.need(db==body['current_fixed_db_controls'],
   'FINANCIAL_RUNTIME_SIDECAR_OWN_CURRENT_FIXED_DB_CONTROLS_STILL_EQUAL')
  _bind_db(body['normal_financial_runtime_controls'],db,body['OWN_contract'])
  M.need(_read_complete(home,own=True,budget=read_budget)==(body,ref),
   'FINANCIAL_RUNTIME_SIDECAR_OWN_FIXED_ISSUED_REFERENCE_STABLE')
  value=_verified(body,ref,current,own=True)
  _OWN_RECEIVERS[id(value)]=dict(value=value,fds=fds,locks=expected,thread=threading.get_ident(),closed=False)
  return value
 except BaseException:
  for fd in fds:os.close(fd)
  raise


def close_OWN_source(value,*,read_budget):
 _budget(read_budget);record=_OWN_RECEIVERS.get(id(value))
 M.need(type(value)is VerifiedFinancialRuntimeSource and value.OWN is True and record is not None and
  record['value']is value and record['thread']==threading.get_ident()and value.new_owner_birth==process_birth(os.getpid()),
  'FINANCIAL_RUNTIME_SIDECAR_ONLY_OWN_RECEIVER_NORMAL_LOCAL_CLOSE')
 for fd in record['fds']:os.close(fd)
 record['closed']=True;_OWN_RECEIVERS.pop(id(value),None)
