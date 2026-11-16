"""Independent4M SEARCH branch from immutable16M CAS, NOT mainline custody.

Mainline can already be at20M (or still running). Never consult its current
frontier/ref/session/fence, never close/resume it, never add a row to its DB.
"""
from pathlib import Path
import copy
from common import need,digest,wire,publish
from scientific_profile import SearchProfile
from scientific_relay import ScientificRelay
from admission_gate import AdmissionGate
PARK=16_000_000;CAP=4_000_000;FINAL=20_000_000;ROLE='worker-00'

class AggregateProfile(SearchProfile):
 def __init__(self,manifest,policy,policy_sha,parent,phase,seed):
  super().__init__(manifest,policy,policy_sha);self.parent=parent;self.phase=phase
  self.seed=int(digest({'domain':'AGENSH_V2_FORK_AGGREGATE_SEARCH','seed':seed})[:8],16)
  self.rows[phase]={**self.rows[phase],'seed':self.seed,'roles':[ROLE]}
 def reserve_rng(self,ledger,t,role,rid):
  need(t==self.phase and role==ROLE,'AGGREGATE_FRESH_PHASE_IDENTITY');m=super().reserve_rng(ledger,t,role,rid)
  with ledger.tx():ledger.event(t,'LATE_AGGREGATE_RNG_DOMAIN',{'parent_trajectory':self.parent,'request_id':rid,'domain':'AGENSH_V2_FORK_AGGREGATE_SEARCH','derived_search_seed':self.seed})
  return m

class Phase:
 def __init__(self,driver,record,home,prompt_pin,*,ledger,manifest,source,branch_id,peer=None):
  self.driver=driver;self.original=record['launch'].controller;self.l=ledger;self.parent=source['parent_trajectory'];self.id=branch_id
  need(ledger is not driver.ledger and ledger.home!=driver.ledger.home,'AGGREGATE_FINANCIAL_LEDGER_INDEPENDENT')
  self.home=Path(home);self.home.mkdir(mode=0o700)
  self.source=copy.deepcopy(source);self.cas=self.original.cas;self.ref=copy.deepcopy(source['snapshot']);self.expected=copy.deepcopy(source['expected'])
  d=self.cas.verify_snapshot(self.ref,expected=self.expected)
  need(d['trajectory']==self.parent and d['target_tokens']==PARK and d['reserved']==d['unresolved']==d['active_operations']==0,'AGGREGATE_SEALED16M_SOURCE_ONLY')
  need(d['pins']['manifest']==digest(driver.manifest),'AGGREGATE_SOURCE_MAIN_MANIFEST')
  self.parent_actual=d['actual_search_tokens'];need(0<=self.parent_actual<=PARK,'AGGREGATE_PARENT_BUDGET')
  self.binding={'schema':'agensh-independent-fork-aggregate-search-v1','parent_trajectory':self.parent,'phase_trajectory':self.id,
   'original16_snapshot':self.ref,'original16_actual':self.parent_actual,'aggregate_cap':CAP,'nominal20':FINAL,
   'source_binding_sha256':digest(source),'prompt':copy.deepcopy(prompt_pin),'mainline_can_continue':True,
   'shared_original_ledger':False,'billing_domain':'SEARCH_AGGREGATE_BRANCH','fee_category':'综合分支','mainline_search_budget_delta':0,
   'aggregate_is_fresh_agent':True,'original_worker_identity_reused':False,'branch_manifest_sha256':digest(manifest)}
  self.l.register(self.id,[ROLE],digest(manifest),targets=[CAP],request_cap=1)
  with self.l.tx():self.l.event(self.id,'LATE_AGGREGATE_BRANCH_LINK',self.binding)
  publish(self.home/'PHASE.json',wire(self.binding),mode=0o400)
  self.gate=AdmissionGate(self.l,global_allocated_cap=manifest['scheduling']['global_gateway_cap'],search_allocated_cap=manifest['scheduling']['search_cap'])
  if peer is not None:peer.bind_gate(self.gate)
  self.profile=AggregateProfile(manifest,driver.config['model_policy'],digest(driver.config['model_policy']),self.parent,self.id,record['row']['seed'])
  self.relay=None;self.sealed=None
 def bind(self,transport):
  need(self.relay is None,'AGGREGATE_TRANSPORT_BIND_ONCE')
  self.relay=ScientificRelay(transport,self.l,self.driver.bounds,self.home/'continuations',model=self.driver.config['model_policy']['model'],max_output=self.driver.config['maximum_output'],max_inflight=1,global_allocated_cap=self.gate.global_cap,admission_gate=self.gate,profile=self.profile)
 def before_call(self,upper):
  with self.l.capacity_changed:
   f=self.l.frontier(self.id)
   if f['state']=='DRAINING':return False
   need(f['state']=='RUNNING'and self.l.admission_fault(self.id)is None,'AGGREGATE_ACTIVE_ACCOUNT')
   if f['actual']+f['reserved']+upper>CAP:
    need(not f['unresolved'],'AGGREGATE_SERIAL_NO_UNRESOLVED_TAIL')
    self.l.close_admission(self.id,'LATE_AGGREGATE_BUDGET_TAIL_CLOSED');return False
   return True
 def accounting(self):
  f=self.l.frontier(self.id);a=self.parent_actual
  need(a<=PARK and f['actual']+f['reserved']<=CAP and a+f['actual']+f['reserved']<=FINAL,'AGGREGATE_COMBINED_HARD_BUDGET')
  return {'original_search_tokens':a,'aggregate_search_tokens':f['actual'],'actual_search_tokens':a+f['actual'],'nominal_budget':FINAL,
   'budget_gap':FINAL-a-f['actual'],'aggregate_nominal':CAP,'aggregate_unused_tail':CAP-f['actual'],'mainline_search_budget_delta':0,'fee_category':'综合分支'}
 def seal(self,workspace,sandbox_receipt):
  need(self.sealed is None,'AGGREGATE_SEAL_ONCE');self.cas.verify_snapshot(self.ref,expected=self.expected)
  f=self.l.frontier(self.id);need(f['state']=='DRAINING'and not any(f[k]for k in('reserved','unresolved','active_operations')),'AGGREGATE_SETTLED_CUT')
  need(sandbox_receipt['cgroup_frozen']is True and sandbox_receipt['network']=='none'and sandbox_receipt['whole_container']is True,'AGGREGATE_PHYSICAL_FREEZE_REQUIRED')
  cas=self.cas;work=cas.capture_tree(Path(workspace));db=cas.temporary();self.relay.continuations.backup(db);ld=cas.temporary();self.l.backup(ld)
  self.sealed={**self.binding,**self.accounting(),'workspace':work,'continuations':cas.store(db),'durable_ledger':cas.store(ld),'freeze':copy.deepcopy(sandbox_receipt),'mainline_frozen_required':False}
  p=cas.temporary();publish(p,wire(self.sealed),mode=0o400);ref=cas.store(p)
  publish(self.home/'SEALED.json',wire({'ref':ref,'accounting':self.accounting()}),mode=0o400)
  with self.l.tx():self.l.event(self.id,'LATE_AGGREGATE_BRANCH_SEALED',{'ref':ref,**self.accounting()})
  return ref
