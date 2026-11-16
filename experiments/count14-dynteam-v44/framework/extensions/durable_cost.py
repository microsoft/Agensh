"""Read only native accounting, append reservation charge and PARTIAL overlays.

A missing original parent is NEVER an observed wait. Original RUNNING/child/
terminal=null, native UNKNOWN_STOPPED and active reservation all stay unchanged.
Model physical UNKNOWN capacity remains occupied even after logical charging.
"""
from pathlib import Path
from common import need,digest,strict,hash_file,wire,Refused
import final_attempts as A
import native_replicate_attempts as R
import aux_unknown_replacement as U
from durable_final import ended,append,enqueue_after_partial,durable_wait

class AccountingConflict(Refused):pass
def money_need(flag,code):
 if not flag:raise AccountingConflict(code)

def accounting(d,r):
 l=d.ledger;j=r['job'];scope=r['scope'];base=Path(r['config']['aux_root']);branch=base/f"k{j['replicate']}"
 with l.mutex:permits=[dict(p)for p in l.db.execute('SELECT * FROM aux_permits WHERE scope=?',(scope,))]
 native=branch/'ledger.json';book=branch/'ledger.json.reservations-v52.json'
 if not native.exists():
  need(not permits,'DISK_MISSING_NATIVE_HAS_HOST_PERMITS');n={'requests':{},'actual_tokens':0,'model_calls':0};np={'sha256':digest({'absent':True})};b={'active':{}};bp={'sha256':digest({'absent':True})}
 else:
  need(native.is_file()and native.resolve()==native,'DISK_NATIVE_CANONICAL_ACCOUNTING')
  np=hash_file(native);n=strict(native.read_bytes())
  need(n.get('setting')=='single'and type(n.get('requests'))is dict,'DISK_NATIVE_ORIGINAL_ACCOUNTING_SCHEMA')
  if book.exists():need(book.is_file()and book.resolve()==book,'DISK_BOOK_CANONICAL_ACCOUNTING');bp=hash_file(book);b=strict(book.read_bytes())
  else:need(not n['requests'],'DISK_NATIVE_REQUESTS_REQUIRE_BOOK');b={'active':{}};bp={'sha256':digest({'absent':True})}
 money_need(set(n['requests'])=={p['request_id']for p in permits if p['request_id']is not None},'DISK_NATIVE_HOST_EXACT_REQUEST_SET')
 pending=[p for p in permits if p['state']in('RESERVED','SENT','UNKNOWN')]
 ids={p['request_id']for p in pending};need(None not in ids,'DISK_UNSENT_NOT_CHARGED')
 need(set(b.get('active',{}))<=ids,'DISK_NO_UNACCOUNTED_ACTIVE_RESERVATION')
 charges=[];measured=tokenized=0;unreported=0
 # Metadata checks before any new charge/allocation.
 for rid,row in n['requests'].items():
  need(row.get('role')=='single','DISK_NATIVE_ROLE')
  if rid in ids:
   need(row.get('state')in U.UNKNOWN_STATES,'DISK_PENDING_REQUIRES_NATIVE_UNKNOWN_CLASSIFICATION')
   if 'tokens'not in row:need(row['state']=='UNKNOWN_STOPPED','DISK_ONLY_ORIGINAL_UNKNOWN_MAY_LACK_USAGE');unreported+=1;continue
  else:need(row.get('state')in('COMPLETED','UNKNOWN_CHARGED','REJECTED_PREGEN','RETRYABLE_REJECTED'),'DISK_NATIVE_OTHER_REQUEST_SETTLED')
  need(type(row.get('tokens'))is int and row['tokens']>=0,'DISK_NATIVE_TOKEN_INTEGER')
  tokenized+=row['tokens']
  if rid not in ids:measured+=row['tokens']
 money_need(n['actual_tokens']==tokenized and n['model_calls']==len(n['requests']),'DISK_NATIVE_TOTALS_NOT_IMPUTED')
 cp=base/f"evaluator-custody-k{j['replicate']}"/'custody.sqlite'
 if cp.exists():eu,ep=R.custody(cp)
 else:need(not permits,'DISK_EVALUATOR_CUSTODY_REQUIRED_AFTER_MODEL');eu=0;ep=digest({'not_started':True})
 need(eu==0,'DISK_EVALUATOR_PHYSICAL_CUSTODY_NOT_TERMINAL')
 for p in pending:
  rid=p['request_id'];row=n['requests'][rid];a=b.get('active',{}).get(rid)
  if a is not None:
   upper=a['upper'];money_need(type(upper)is int and upper>0 and upper==a['input_upper_bound']+a['max_output_tokens'],'DISK_ORIGINAL_RESERVATION_UPPER')
  else:need(row['state']=='UNKNOWN_CHARGED'and type(row.get('tokens'))is int and row['tokens']>0,'DISK_RESERVATION_OR_NATIVE_CONSERVATIVE_CHARGE_REQUIRED');upper=row['tokens']
  v={'kind':U.KIND,'schema':'agensh-aux-unknown-reservation-charge-v1','trajectory':j['trajectory'],'point_id':j['point'],'job_id':j['id'],'claim':j['claim'],'replicate_id':j['replicate'],'attempt':j.get('attempt',1),'scope':scope,'permit_id':p['id'],'request_id':rid,'billing_domain':'AUX_FINALIZATION','charged_tokens':upper,'input_upper_bound':a['input_upper_bound']if a else None,'max_output_tokens':a['max_output_tokens']if a else None,'charge_basis':'USER_AUTHORIZED_RESERVATION_UPPER_BOUND_NOT_MEASURED_USAGE','search_budget_delta':0,'physical_terminal_proven':False,'original_host_state':p['state'],'original_native_state':row['state'],'native_ledger_pin':np,'native_reservation_book_pin':bp,'no_replay':True,'no_usage_backfill':True,'no_terminal_backfill':True,'original_native_active_reservation_retained':a is not None}
  charges.append(v)
 if native.exists():need(hash_file(native)==np,'DISK_ENDED_NATIVE_ACCOUNTING_CHANGED')
 if book.exists():need(hash_file(book)==bp,'DISK_ENDED_NATIVE_BOOK_CHANGED')
 return {'schema':'disk-final-logical-disposition-proof-v1','scope':scope,'model_unresolved':len(pending),'logical_model_unresolved':0,'physical_unknown_slots_retained':len(pending),'evaluator_unresolved':0,'native_aux_tokens':measured,'native_request_count':len(n['requests']),'native_ledger_sha256':np['sha256'],'evaluator_proof_sha256':ep,'native_unreported_unknown_count':unreported,'unknown_aux_reservation_charge':sum(v['charged_tokens']for v in charges),'provider_terminal_claimed':False,'native_usage_rewritten':False,'search_budget_delta':0},charges

def dispose(d,r,*,maximum):
 q=d.queue;l=d.ledger;j=r['job'];raw=q._job(j['id'])
 if r.get('orphan')is not None:
  need(raw['state']=='RUNNING'and raw['terminal']is None and strict(raw['child'].encode())==r['orphan']and ended(r['orphan']),'DISK_ORPHAN_EXACT_PROCESS_PHYSICALLY_ENDED')
  provenance={'custody':'ORIGINAL_PARENT_LOST_CHILD_PHYSICALLY_ENDED','original_child':r['orphan'],'wait_observed':False,'exit_code':None,'signal':None,'original_claim':raw['claim'],'original_raw_state':'RUNNING','original_terminal_remains_null':True}
 else:
  t=durable_wait(q,raw);need(t['exit_code']!=0 or t['signal']is not None,'DISK_SUCCESSFUL_HOLD_NOT_PARTIAL')
  provenance={'custody':'GENUINE_DURABLE_PARENT_WAIT','original_terminal_sha256':digest(t),'original_claim':raw['claim']}
 p,charges=accounting(d,r);p['custody_provenance']=provenance
 U._schema(l)
 with l.tx():
  for v in charges:
   old=l.db.execute('SELECT metadata FROM '+U.TABLE+' WHERE request_id=?',(v['request_id'],)).fetchone()
   if old is not None:money_need(strict(old[0].encode())==v,'DISK_EXISTING_RESERVATION_CHARGE_CONFLICT')
   else:l.db.execute('INSERT INTO '+U.TABLE+' VALUES(?,?)',(v['request_id'],wire(v).decode()));l.event(j['trajectory'],U.KIND,v)
  allocation={'job_id':j['id'],'claim':j['claim'],'point_id':j['point'],'replicate_id':j['replicate'],'attempt':j.get('attempt',1),'policy':A.POLICY,'allocation':'SYSTEM_CONSUMPTION','billing_domain':'AUX_FINALIZATION','search_budget_delta':0,**p,'allocation_note':'measured failed AUX only; reservation UNKNOWN remains separate AUX_FINALIZATION'}
  l.db.execute('CREATE TABLE IF NOT EXISTS aux_attempt_allocations(job_id TEXT PRIMARY KEY,metadata TEXT NOT NULL)')
  for action in('UPDATE','DELETE'):l.db.execute('CREATE TRIGGER IF NOT EXISTS no_'+action.lower()+"_aux_attempt_allocation BEFORE "+action+" ON aux_attempt_allocations BEGIN SELECT RAISE(ABORT,'append only'); END")
  prior=l.db.execute('SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',(j['id'],)).fetchone()
  if prior is not None:money_need(strict(prior[0].encode())==allocation,'DISK_FAILED_ALLOCATION_CONFLICT')
  else:l.db.execute('INSERT INTO aux_attempt_allocations VALUES(?,?)',(j['id'],wire(allocation).decode()));l.event(j['trajectory'],'AUX_FAILED_REPLICATE_SYSTEM_CONSUMPTION',allocation)
 with q.tx():
  now=q._job(j['id']);need(now==raw,'DISK_ORIGINAL_JOB_CHANGED_DURING_DISPOSITION')
  row={'policy':A.POLICY,'point_id':j['point'],'replicate_id':j['replicate'],'attempt':j.get('attempt',1),'original_claim':j['claim'],'disposition':'PARTIAL','allocation':'SYSTEM_CONSUMPTION','billing_domain':'AUX_FINALIZATION','search_budget_delta':0,**p}
  old=q.db.execute('SELECT metadata FROM replicate_partials WHERE job_id=?',(j['id'],)).fetchone()
  if old is not None:need(strict(old[0].encode())==row,'DISK_PARTIAL_PROOF_CHANGED')
  else:q.db.execute('INSERT INTO replicate_partials VALUES(?,?)',(j['id'],wire(row).decode()));q.event('REPLICATE_PARTIAL_DURABLE_CUSTODY',dict(job_id=j['id'],**row))
  if r.get('orphan')is not None:append(q,'disk_orphan_dispositions',j['id'],provenance)
 r['partial']=True;r['replacement_job_id']=enqueue_after_partial(q,raw,maximum)
 return r['replacement_job_id']

def enqueue_existing_partial(d,r,maximum):
 """Consume genuine persisted PARTIAL/allocation, never recreate its wait."""
 j=r['job'];q=d.queue
 t=durable_wait(q,q._job(j['id']));need(t['exit_code']!=0 or t['signal']is not None,'DISK_PRIOR_PARTIAL_REAL_FAILED_WAIT')
 with q.mutex:p=q.db.execute('SELECT metadata FROM replicate_partials WHERE job_id=?',(j['id'],)).fetchone()
 with d.ledger.mutex:a=d.ledger.db.execute('SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',(j['id'],)).fetchone()
 need(p is not None and a is not None,'DISK_PRIOR_PARTIAL_AND_ALLOCATION')
 p,a=strict(p[0].encode()),strict(a[0].encode())
 need(p['original_claim']==j['claim']and a['claim']==j['claim']and p['terminal_sha256']==a['terminal_sha256']==digest(t),'DISK_PRIOR_PARTIAL_ALLOCATION_SAME_TERMINAL')
 return enqueue_after_partial(q,q._job(j['id']),maximum)
