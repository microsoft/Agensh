"""Normal-cold HELD financial writer; never queue/SEARCH/whole activation.

Original RW ledger methods may run only after independent normal source/pair,
real service retirement, exact gate/fence/post-clock and CURRENT resource
custody checks. No constructor/migration/reclassification on paid history.
Old AUX accounting epochs/UNKNOWN slots survive. Old authorizer metadata is
not a callable/new child authority. Missing actual components always WAIT.
"""
from dataclasses import asdict
from pathlib import Path
from types import MethodType,SimpleNamespace
import ast
import copy
import hashlib
import importlib
import inspect
import json
import os
import sqlite3
import subprocess
import threading
import textwrap

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
import staged_financial_runtime as S
import financial_runtime_source_control as F

PINS=dict(staged_financial_runtime='62de21eed76372cbe6d6721da10891d0a86e4cfc65dbbdbbf22294b3e49baba5',
 financial_runtime_source_control='5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906',
 active_clock_method_runtime='c24b4168f0a4fe3dc88cda7a086e2cdf6a2f3249e864391c9f94abb653bd26be',
 source_services_controls='f7c72e41dc7df2940917ad664d582308ab936387c0b5190a21e2c07bac2d55db',
 source_services_retirement='084a59c44b0bfe49cca9c138472bda76575cd52a24fbed569f0b8f765aaa1887',
 dynteam_membership_fence='2f6e13e919778c4dcfc985ca3338ddbb89b77cac98437f7adb19ff02bf192a51',
 dynamic_role_gate='605a824a6b3fa0ec039947b33e263396448814c50daf38d1384ee83cf7176212',
 admission_gate='8504daf99a91a322add5338b55677218f2cb3d103bee401eaae720c9048a3821',
 native_resource_producer='c1187cd5195a3b431a6eabd330578bd911ebe3fc4405a1358944d750df48be07',
 native_cohort_resources='26d1181e98dbf9972b517c1cb621f2b16d0d84780eef9bea83ab9eca7755ebb5')
SERVICES_MODULE_SHA256='fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83'
_SEAL=object()
_GRAPHS={}
_WRITERS={}
_FINANCIAL=frozenset(('account','_identity','frontier','global_unresolved','global_logical_unresolved',
 'unknown_policy_enabled','unknown_charged','unknown_statistics','admission_fault','model_paused',
 'tx','event','reserve','sent','settle','unknown','charge_unknown_at_reservation',
 '_charge_unknown_at_reservation','_unknown_thresholds','latch_fault'))


def verify_sources():
 for name,pin in PINS.items():
  p=Path(importlib.import_module(name).__file__)
  M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and hashlib.sha256(p.read_bytes()).hexdigest()==pin,
   'NORMAL_HELD_WRITER_FIXED_ORIGINAL_COMPONENT_PINS')
 return dict(PINS)


class _BindingRO:
 """Existing owned RO handle, exposing only its REAL transaction boolean."""
 def __init__(self,ro):self.ro=ro
 @property
 def in_transaction(self):self.ro._check();return self.ro._raw.in_transaction
 def execute(self,*a,**k):return self.ro.execute(*a,**k)


def _role_controls(core,raw):
 from dynamic_role_gate import DynamicRoleGate,_compile_original_reserve
 from admission_gate import AdmissionGate
 value=DynamicRoleGate.__new__(DynamicRoleGate);value.ledger=core.ledger
 M.need(type(raw)is dict and set(raw)=={'epoch','births','held'},
  'NORMAL_HELD_WRITER_COMPLETE_ORIGINAL_ROLE_CONTROL_FIELDS')
 M.need(type(raw['epoch'])is int and raw['epoch']>=0,'NORMAL_HELD_WRITER_REAL_ROLE_EPOCH')
 value.epoch=raw['epoch'];value.births={};value.held={tuple(k)for k in raw['held']};value.gates=[]
 for row in raw['births']:
  key=row['trajectory'],row['role'];M.sha(row['birth_sha256'])
  M.need(key not in value.births,'NORMAL_HELD_WRITER_UNIQUE_ORIGINAL_ROLE_BIRTHS')
  value.births[key]=row['birth_sha256']
 registered={(t,r)for t,row in core.rows.items()for r in row['roles']}
 M.need(value.held<=registered and set(value.births)<=registered,
  'NORMAL_HELD_WRITER_ORIGINAL_ROLE_CATALOGUE_MEMBERSHIP')
 gate=AdmissionGate(core.ledger,global_allocated_cap=96,search_allocated_cap=78)
 gate.closed=True;gate.startup_held=set(core.rows)
 gate._dynteam_role_control=value
 gate.reserve=MethodType(_compile_original_reserve(),gate);value.gates.append(gate)
 core.roles=value;core.gate=gate
 core.v2_dispositions.bind_gate(gate)


def _fences(core,raw,*,cuts,own):
 from dynteam_membership_fence import MembershipFence,Lease
 from new_scope_ledger import native_catalogue
 M.need(type(raw)is dict and set(raw)==set(core.rows),'NORMAL_HELD_WRITER_ALL_REAL_SOURCE_MEMBERSHIP_FENCES')
 result={}
 for t,row in raw.items():
  M.need(set(row)=={'roles','_leases','_role_busy','_epoch','_cut','_sealed','_last_generation','_final_retirement'},
   'NORMAL_HELD_WRITER_COMPLETE_FENCE_STATE_NO_GUESSED_EPOCH_OR_LEASE')
  M.need(type(row['roles'])is dict and (own or row['roles']==native_catalogue(arm=core.rows[t]['arm'])),
   'NORMAL_HELD_WRITER_PINNED_NATIVE_FENCE_CATALOGUE')
  value=MembershipFence.__new__(MembershipFence);value.roles=copy.deepcopy(row['roles']);value._lock=threading.Lock()
  value._leases={}
  for item in row['_leases']:
   lease=Lease(**item);M.need(lease.operation_id not in value._leases,'NORMAL_HELD_WRITER_UNIQUE_SOURCE_LEASES')
   value._leases[lease.operation_id]=lease
  value._role_busy=set(row['_role_busy'])
  M.need(not value._leases and not value._role_busy,
   'NORMAL_HELD_WRITER_WAIT_REAL_NATIVE_EFFECT_CUSTODY_NOT_EMPTY_BY_DEFAULT')
  for field in ('_epoch','_cut','_sealed','_last_generation','_final_retirement'):setattr(value,field,copy.deepcopy(row[field]))
  M.need(type(value._epoch)is int and value._epoch>=0 and type(value._last_generation)is int and value._last_generation>=0,
   'NORMAL_HELD_WRITER_REAL_MEMBERSHIP_COUNTERS')
  if not own:
   token=dict(original_generation=value._cut,membership_epoch=value._epoch,native_membership_admission_closed=True,
    pending_native_effects=0,full_static_role_catalogue_sha256=M.digest(value.roles))
   M.need(value._cut is not None and value._sealed==cuts[t]['snapshot_reference']['sha256']and
    M.digest(token)==cuts[t]['membership_token_sha256'],
    'NORMAL_HELD_WRITER_FENCE_FIELDS_MATCH_ORIGINAL_SNAPSHOT_TOKEN_NOT_HASH_GUESS')
   MembershipFence.verify_after_original_capture(value,token)
  result[t]=value
 core.membership_fences=result


def _receiver_hook(stage,context,read_budget):
 import active_clock_method_runtime as A
 graph=context.normal_components
 roles=graph['role_controls'];clock=graph['post_clock'];fences=graph['membership_fences']
 _role_controls(stage.core,roles)
 _fences(stage.core,fences,cuts=graph.get('cuts'),own=stage.OWN)
 pauses={}
 for row in clock['budget_pause']:
  key=row['trajectory'],row['role']
  M.need(key not in pauses and row['since_ns']is None,'NORMAL_HELD_WRITER_EXACT_POST_SHUTDOWN_PAUSE_CONTROLS')
  pauses[key]=dict(total_ns=row['total_ns'],since_ns=None)
 stage.core.gate._budget_pause=pauses
 if stage.OWN:
  _,proof=A.bind_OWN_original_active_clock_methods(stage.core,clock,read_budget=read_budget)
  stage.method_proofs.append(proof)
 else:A.bind_original_active_clock_methods(stage,owner=context.source_owner,ticket=context.source_ticket,read_budget=read_budget)


def _private_make():
 """ONE new fixed hook in a private AST clone, before semantic comparison."""
 verify_sources();original=ast.parse(textwrap.dedent(inspect.getsource(S._make)))
 revised=copy.deepcopy(original);body=revised.body[0].body
 sites=[i for i,n in enumerate(body)if isinstance(n,ast.Import)and
  any(a.name=='financial_runtime_source_control'and a.asname=='source'for a in n.names)]
 M.need(len(sites)==1,'NORMAL_HELD_WRITER_FIXED_PRE_SEMANTIC_ORIGINAL_STAGE_HOOK')
 hook=ast.parse('_receiver_hook(stage,context,read_budget)').body[0];body.insert(sites[0],hook)
 reverse=copy.deepcopy(revised);del reverse.body[0].body[sites[0]]
 M.need(ast.dump(reverse,include_attributes=False)==ast.dump(original,include_attributes=False),
  'NORMAL_HELD_WRITER_ONLY_EXPLICIT_FIXED_COMPONENT_BINDING_HOOK')
 namespace={};globals_=dict(S._make.__globals__,_receiver_hook=_receiver_hook)
 exec(compile(ast.fix_missing_locations(revised),__file__+':private_original_stage_hook','exec'),globals_,namespace)
 return namespace['_make']


def _services_module():
 module=importlib.import_module('durable_service_source_controls')
 p=Path(module.__file__)
 expected=Path(__file__).resolve().parents[1]/'formal100m-services-durable-source-controls-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/durable_service_source_controls.py'
 M.need(SERVICES_MODULE_SHA256 is not None and p==expected and p.resolve()==p and not p.is_symlink()and
  hashlib.sha256(p.read_bytes()).hexdigest()==SERVICES_MODULE_SHA256,
  'NORMAL_HELD_WRITER_WAIT_FIXED_DURABLE_PHYSICAL_SERVICE_CONTROL_VERIFIER')
 return module


def prepare_registered_graph(ticket,*,owner,services_reference,read_budget):
 import normal_inert_cut as T
 M.need(type(read_budget)is ReadBudget,'NORMAL_HELD_WRITER_FINITE_METADATA_BUDGET');read_budget.check()
 M.need(type(ticket)is T.NormalInertTicket,'NORMAL_HELD_WRITER_ONLY_PRODUCTION_ORIGINAL_TYPED_T')
 source=F.load_registered_source(owner,ticket=ticket,read_budget=read_budget)
 module=_services_module()
 services=module.verify_reference(services_reference,owner=owner,ticket=ticket,read_budget=read_budget)
 M.need(type(services)is module.VerifiedRetiredServiceControls,
  'NORMAL_HELD_WRITER_EXACT_ORIGINAL_SOURCE_SERVICES_NOT_DICT_OR_BOOL')
 cap=T.verify_inert_ticket(ticket,owner=owner,read_budget=read_budget);pair=owner.core.metadata_inert_pair
 M.need(services.old_owner_birth==cap.old_owner_birth and services.new_owner_birth==cap.new_owner_birth and
  services.contract_sha256==cap.contract_sha256 and tuple(services.lock_fds)==tuple(pair.lock_fds),
  'NORMAL_HELD_WRITER_SAME_SOURCE_NEW_BIRTH_CONTRACT_AND_ORIGINAL_THREE_LOCKS')
 body=services.snapshot();pre=cap._body['source_controls'];post=cap._body['post_retirement_controls']
 context=SimpleNamespace(OWN=False,old_owner_birth=cap.old_owner_birth,new_owner_birth=cap.new_owner_birth,
  contract=pair.material['contract'],rows=owner.core.rows,owner_home=owner.core.home,
  ledger_home=owner.core.ledger.home,queue_home=owner.core.queue.home,ledger_database=cap.ledger_database,
  queue_database=cap.queue_database,ledger_db=_BindingRO(owner.core.ledger.db),queue_db=owner.core.queue.db,
  lock_fds=tuple(pair.lock_fds),source_owner=owner,source_ticket=ticket,services_reference=services_reference,
  services_cap=services,normal_components=dict(role_controls=pre['financial']['registered_role_controls'],
   cuts=pre['cuts'],post_clock=post['normal_clock_controls'],membership_fences=body['membership_fences']))
 stage=_private_make()(context,source.controls['normal_financial_runtime_controls'],read_budget=read_budget,
  final_controls=cap.component('paid_FINAL_controls'))
 _GRAPHS[id(stage)]=dict(stage=stage,OWN=False,ticket=ticket,owner=owner,services=services,context=context,
  financial_before=F._db_controls(Path(cap.ledger_database['path']),Path(cap.queue_database['path']),read_budget),
  writer=None)
 return stage


def _same(stage,budget,*,own):
 M.need(type(budget)is ReadBudget,'NORMAL_HELD_WRITER_EXACT_FINITE_METADATA_BUDGET')
 M.need(type(stage)is S.StagedFinancialRuntime and id(stage)in _GRAPHS and _GRAPHS[id(stage)]['stage']is stage and
  stage.OWN is own and stage.new_owner_birth==process_birth(os.getpid()),
  'NORMAL_HELD_WRITER_EXACT_REGISTERED_NEW_GRAPH_AND_NAMESPACE')
 budget.check();record=_GRAPHS[id(stage)]
 M.need(not stage.ledger.mutex._is_owned()and not stage.queue.mutex._is_owned(),
  'NORMAL_HELD_WRITER_METADATA_AND_RESOURCE_IO_OUTSIDE_SCIENCE_LOCKS')
 if not own:
  import normal_inert_cut as T
  cap=T.verify_inert_ticket(record['ticket'],owner=record['owner'],read_budget=budget)
  fresh=_services_module().verify_reference(record['context'].services_reference,owner=record['owner'],
   ticket=record['ticket'],read_budget=budget)
  M.need(cap.new_owner_birth==stage.new_owner_birth and fresh.snapshot()==record['services'].snapshot()and
   tuple(fresh.lock_fds)==tuple(stage.context.lock_fds),'NORMAL_HELD_WRITER_FRESH_ORIGINAL_PAIR_AND_SERVICE_PROOF')
 else:
  import normal_inert_cut as T
  source=record['OWN_source']
  M.need(type(source)is F.VerifiedFinancialRuntimeSource and source.OWN is True and
   source.old_owner_birth==stage.old_owner_birth and source.new_owner_birth==stage.new_owner_birth and
   M.nonexecuting(stage.old_owner_birth,stage.new_owner_birth),
   'NORMAL_HELD_WRITER_OWN_REAL_TWO_BIRTH_SOURCE_CHAIN')
  T._validate_owned_locks(stage.context.lock_fds,[row for kind,row in source._body['locks']])
 return record


def _physical_source(stage,record):
 M.need(stage.controls['native_services']=={}and stage.controls['native_service_count']==0 and
  not stage.unbound_native_services,'NORMAL_HELD_WRITER_WAIT_UNBOUND_ORIGINAL_NATIVE_SERVICE_CUSTODY')
 if not record['OWN']:
  body=record['services'].snapshot();physical=body['physical_service_retirement']
  M.need(physical['native_control_listener_and_handlers_ended']is True and not physical['control_close_job_alive'],
   'NORMAL_HELD_WRITER_REAL_ORIGINAL_CONTROL_PHYSICAL_TERMINAL')
  for key in ('SYSTEM','resource'):
   M.need(body[key]['registered']is True and physical[key]['registered']is True and
    physical[key]['physical_clear']is True and physical[key]['live_children']==0,
    'NORMAL_HELD_WRITER_WAIT_REAL_SYSTEM_AND_RESOURCE_CUSTODY_NOT_UNKNOWN_ZERO')


def _fresh_current_resource(stage,producer,budget,*,own):
 from native_cohort_resources import NativeCohortResources
 from native_resource_producer import NativeResourceProducer
 M.need(type(stage.resources)is NativeCohortResources and stage.resources.ledger is stage.ledger and
  stage.resources.core is stage.core and stage.resources.owner==stage.new_owner_birth,
  'NORMAL_HELD_WRITER_ORIGINAL_CURRENT_OWNER_RESOURCE_OBJECT')
 if not own:
  from native_docker_scope import ScopedDocker
  from native_container_retirement import NativeContainerRegistry
  from native_system_health import NativeSystemHealth
  M.need(type(producer)is NativeResourceProducer and producer.core is stage.core and
   producer.owner==stage.new_owner_birth and producer.contract_sha==M.digest(stage.core.contract)and
   producer.core.resource_producer is producer and producer.records,
   'NORMAL_HELD_WRITER_WAIT_ACTUAL_NEW_OWNER_ORIGINAL_RESOURCE_PRODUCER')
  record=_GRAPHS[id(stage)];old=record['services'].component('resource')['configuration']
  old_system=record['services'].component('SYSTEM')['configuration']
  from source_services_controls import sources
  M.need(producer._outside.__func__ is NativeResourceProducer._outside and
   producer._publish.__func__ is NativeResourceProducer._publish and producer.poll.__func__ is NativeResourceProducer.poll and
   producer.sequence>old['sequence'] and producer.next_due>=old['next_due'] and
   producer.inventory_sha==old['inventory_sha256']==stage.resources.allocation.inventory_sha256 and
   str(producer.plan_path)==old['plan_path'] and sources(producer.sources,budget)==old['sources'],
   'NORMAL_HELD_WRITER_ORIGINAL_PRODUCER_METHODS_SOURCES_COUNTERS_AND_ALLOCATION')
  system=getattr(stage.core,'system_health',None)
  M.need(type(system)is NativeSystemHealth and system.core is stage.core and system.owner==stage.new_owner_birth and
   system.sequence>=old_system['sequence']and sources(system.sources,budget)==old_system['sources']and
   system.last_intent_wall is not None and system.last_intent_mono is not None and
   (old_system['last_intent_wall']is None or system.last_intent_wall>=old_system['last_intent_wall'])and
   (old_system['last_intent_mono']is None or system.last_intent_mono>=old_system['last_intent_mono']),
   'NORMAL_HELD_WRITER_WAIT_REAL_NEW_SYSTEM_STRUCTURE_WITH_ORIGINAL_TIMER_HISTORY')
  M.need(type(stage.core.native_containers)is NativeContainerRegistry and
   stage.core.native_containers.core is stage.core and type(stage.core.native_containers.docker)is ScopedDocker and
   stage.core.native_containers.docker.route.qualification_only is False,
   'NORMAL_HELD_WRITER_WAIT_ACTUAL_NEW_NATIVE_DAEMON_BINDING')
  last=producer.records[-1]
  M.need(last['state']=='OBSERVATION_PUBLISHED'and type(last['child'])is subprocess.Popen and
   last['child'].poll()==0 and last['job']['owner']==asdict(stage.new_owner_birth)and
   last['job']['contract_sha256']==M.digest(stage.core.contract),
   'NORMAL_HELD_WRITER_ONLY_COMPLETED_CURRENT_ORIGINAL_SAMPLER_NOT_SOURCE_METADATA')
 previous={name:getattr(stage.resources,name)for name in stage._resource_methods}
 try:
  for name,bound in stage._resource_methods.items():setattr(stage.resources,name,bound)
  status=stage.resources.refresh();budget.check()
  M.need(status['experiment_admission_open']is True and status['SYSTEM_admission_open']is True,
   'NORMAL_HELD_WRITER_WAIT_ORIGINAL_FRESH_RESOURCE_AND_HEALTH_PREDICATES')
  if not own:
   M.need(producer.last_published==stage.resources.state['raw_public_receipt_sha256']and
    producer.plan.get('OWN_fixture')is None,
    'NORMAL_HELD_WRITER_ACTUAL_PRODUCER_RECEIPT_MATCH_NO_OWN_HOST_PROJECTION')
 finally:
  # Only the NEW unpublished graph was bound. Preserve the actual original
  # refresh's cached observation/failure controls, but never leave methods
  # open after refusal (or before the separate RW component commit).
  for name,bound in previous.items():setattr(stage.resources,name,bound)


class NormalHeldFinancialWriter:
 __slots__=('_stage','_database','_seal','OWN','old_owner_birth','new_owner_birth')
 def __init__(self,*args,**kwargs):raise M.PaidColdWait('NORMAL_HELD_WRITER_ONLY_NORMAL_COMPONENT_CHAIN_ISSUER')
 def __setattr__(self,name,value):
  M.need(not hasattr(self,'_seal'),'NORMAL_HELD_WRITER_COMPONENT_CAPABILITY_IMMUTABLE')
  object.__setattr__(self,name,value)
 @property
 def ledger(self):return self._stage.ledger
 @property
 def queue_authorized(self):return False
 @property
 def SEARCH_authorized(self):return False
 @property
 def paid_activation_authorized(self):return False
 @property
 def whole_runnable_ready(self):return False
 @property
 def safe_to_TERM(self):return False
 def public(self):
  return dict(PUBLIC_code='NORMAL_HELD_ORIGINAL_FINANCIAL_WRITER_ONLY',OWN=self.OWN,
   old_owner_birth=asdict(self.old_owner_birth),new_owner_birth=asdict(self.new_owner_birth),
   actual_original_financial_methods_enabled=True,queue_authorized=False,SEARCH_authorized=False,
   old_AUX_authorizer_callbacks_recreated=False,original_AUX_accounting_epoch_preserved=True,
   constructor_migration_or_request_reclassification=False,whole_runnable_ready=False,paid_activation_authorized=False)


def open_registered_held_writer(stage,*,resource_producer,read_budget):
 record=_same(stage,read_budget,own=False);_physical_source(stage,record)
 _fresh_current_resource(stage,resource_producer,read_budget,own=False)
 return _open(stage,record,read_budget)


def _open(stage,record,budget):
 M.need(record['writer']is None and stage.core.gate.closed and set(stage.core.gate.startup_held)==set(stage.core.rows)and
  not stage.core.gate.waiters and not stage.capacity.authorizers and stage.capacity.epoch==
  stage.controls['ledger_attribute_controls']['model_capacity_owner_epoch']['value'],
  'NORMAL_HELD_WRITER_EXACT_HELD_GATE_OLD_AUX_ACCOUNTING_DOMAIN_NO_FAKE_AUTHORIZER')
 for t,clock in stage.core.active_clock.states.items():
  M.need(clock['mode']in('HOLD','FINAL'),'NORMAL_HELD_WRITER_ORIGINAL_ACTIVE_CLOCK_MUST_BE_HELD')
 p=Path(stage.context.ledger_database['path'])
 previous_db,previous_raw=stage.ledger.db,stage.dispositions.raw_connection
 previous_ledger={name:getattr(stage.ledger,name)for name in _FINANCIAL}
 previous_dispositions={name:getattr(stage.dispositions,name)for name in stage._disposition_methods}
 previous_resources={name:getattr(stage.resources,name)for name in stage._resource_methods}
 db=None;writer=None
 try:
  for name,bound in stage._resource_methods.items():setattr(stage.resources,name,bound)
  M.need(stage.resources.experiment_open()and stage.resources.system_open(),
   'NORMAL_HELD_WRITER_FRESH_ORIGINAL_RESOURCE_PREDICATES_STILL_TRUE_AT_RW_BOUNDARY')
  now=F._db_controls(p,Path(stage.context.queue_database['path']),budget)
  M.need(now==record['financial_before'],'NORMAL_HELD_WRITER_ORIGINAL_FIXED_FINANCIAL_AND_SCHEMA_EQUALITY')
  db=sqlite3.connect(p.as_uri()+'?mode=rw&cache=private',uri=True,timeout=0,isolation_level=None,check_same_thread=False)
  db.row_factory=sqlite3.Row;db.set_progress_handler(budget.progress,1000)
  # NEW handle only; these are the original Ledger connection settings, not
  # schema/migration/shared host configuration or old connection changes.
  db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA synchronous=FULL')
  M.existing(stage.context.ledger_database,private=True)
  M.need(not db.in_transaction and all(list(db.execute(sql).fetchone())==now['six_financial_COUNT_SUM'][name]
   for name,sql in F._SIX_SQL.items()),'NORMAL_HELD_WRITER_NEW_RW_HANDLE_SAME_SIX_FINANCIAL_EQUATIONS')
  if not record['OWN']:
   states=[r[0]for r in db.execute('SELECT state FROM accounts')]
   M.need(states and all(s=='COMMITTED_PARKED'for s in states),
    'NORMAL_HELD_WRITER_PRODUCTION_NORMAL_CUT_ACCOUNTS_REMAIN_PARKED')
  stage.ledger.db=db;stage.dispositions.raw_connection=db
  for name in _FINANCIAL:setattr(stage.ledger,name,stage._ledger_methods[name])
  for name,bound in stage._disposition_methods.items():setattr(stage.dispositions,name,bound)
  # Do not keep the finite metadata VM deadline attached to a long-lived new
  # writer. The original methods/RLock/SQL are now the original live runtime.
  db.set_progress_handler(None,0)
  writer=object.__new__(NormalHeldFinancialWriter);writer._stage,writer._database=stage,db
  writer.OWN=record['OWN'];writer.old_owner_birth,writer.new_owner_birth=stage.old_owner_birth,stage.new_owner_birth
  writer._seal=_SEAL;record['writer']=writer;_WRITERS[id(writer)]=writer
  return writer
 except BaseException:
  # Revert ONLY this new unpublished method/connection graph. No original
  # connection transaction, COMMIT/ROLLBACK, row or source object is touched.
  stage.ledger.db=previous_db;stage.dispositions.raw_connection=previous_raw
  for name,bound in previous_ledger.items():setattr(stage.ledger,name,bound)
  for name,bound in previous_dispositions.items():setattr(stage.dispositions,name,bound)
  for name,bound in previous_resources.items():setattr(stage.resources,name,bound)
  if writer is not None:_WRITERS.pop(id(writer),None)
  record['writer']=None
  if db is not None:db.close()
  raise


def prepare_OWN_graph(source_reference,*,components_sha256,read_budget):
 """Explicit sandbox only; not accepted by production T/services verifiers."""
 from metadata_inert_pair import _ReadOnly
 source=F.load_OWN_source(source_reference,read_budget=read_budget)
 connections=[]
 try:
  home=Path(source_reference.path).parent.parent
  M.need(home.name.startswith('OWN-normal-financial-handoff-'),
   'NORMAL_HELD_WRITER_OWN_ACTUAL_CANONICAL_PHYSICAL_DOMAIN')
  row,_=M.private_read(home/'OWN-normal-held-components.json',components_sha256)
  M.need(row['schema']=='OWN_NORMAL_HELD_FINANCIAL_COMPONENTS_V1'and row['OWN']is True and
   row['source_reference']==dict(path=source_reference.path,sha256=source_reference.sha256)and
   row['old_owner_birth']==asdict(source.old_owner_birth)and row['contract_sha256']==source.contract_sha256,
   'NORMAL_HELD_WRITER_OWN_SOURCE_COMPONENTS_SAME_OLD_BIRTH_AND_FINANCIAL_SOURCE')
  raw=source._body;storage=raw['storage'];contract=raw['OWN_contract']
  for kind in ('ledger','queue'):connections.append(_ReadOnly(Path(storage[kind+'_database']['path']),kind,read_budget))
  context=SimpleNamespace(OWN=True,old_owner_birth=source.old_owner_birth,new_owner_birth=source.new_owner_birth,
   contract=contract,rows={r['trajectory_id']:r for r in contract['trajectories']},owner_home=home,
   ledger_home=home/'ledger',queue_home=home/'queue',ledger_database=storage['ledger_database'],
   queue_database=storage['queue_database'],ledger_db=_BindingRO(connections[0]),queue_db=connections[1],
   lock_fds=tuple(F._OWN_RECEIVERS[id(source)]['fds']),normal_components=row['components'])
  stage=_private_make()(context,source.controls['normal_financial_runtime_controls'],read_budget=read_budget)
  _GRAPHS[id(stage)]=dict(stage=stage,OWN=True,OWN_source=source,connections=connections,context=context,writer=None,
   financial_before=F._db_controls(Path(storage['ledger_database']['path']),Path(storage['queue_database']['path']),read_budget))
  return stage
 except BaseException:
  for db in connections:db._close_local()
  F.close_OWN_source(source,read_budget=ReadBudget())
  raise


def open_OWN_held_writer(stage,*,read_budget):
 record=_same(stage,read_budget,own=True);_physical_source(stage,record)
 _fresh_current_resource(stage,None,read_budget,own=True)
 return _open(stage,record,read_budget)


def close_OWN_held_writer(stage,*,read_budget):
 record=_same(stage,read_budget,own=True)
 writer=record['writer']
 if writer is not None:
  M.need(not writer._database.in_transaction,'NORMAL_HELD_WRITER_OWN_NORMAL_CLOSE_NO_OPEN_TRANSACTION')
  writer._database.close();_WRITERS.pop(id(writer),None)
 for db in record['connections']:db._close_local()
 F.close_OWN_source(record['OWN_source'],read_budget=read_budget)
 _GRAPHS.pop(id(stage),None);S._STAGED.pop(id(stage),None)
