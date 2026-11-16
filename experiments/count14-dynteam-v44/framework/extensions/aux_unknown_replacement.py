"""Explicit AUX UNKNOWN reservation charges, logical PARTIAL, physical slots kept.

Consumes/extends OPS append-only rows; never alters native ledgers, active books,
original host permits, provider terminals, usages, old claims or requests. Only
fresh replacement jobs get a new claim and RNG attempt, under original max2.
"""
from pathlib import Path
from types import MethodType
import json
from common import need,digest,wire,strict,hash_file,integer,Refused
import final_attempts
import native_replicate_attempts as original_attempts

TABLE='aux_unknown_reservation_charges'
KIND='AUX_UNKNOWN_CHARGED_AT_RESERVATION'
UNKNOWN_STATES=('UNKNOWN_STOPPED','UNKNOWN_CHARGED')

def _rows(l):
 with l.mutex:return [strict(r[0].encode())for r in l.db.execute('SELECT metadata FROM '+TABLE)]

def _schema(l):
 with l.tx():
  l.db.execute('CREATE TABLE IF NOT EXISTS '+TABLE+'(request_id TEXT PRIMARY KEY,metadata TEXT NOT NULL)')
  for action in ('UPDATE','DELETE'):
   l.db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{action.lower()}_aux_unknown_reservation_charge BEFORE {action} ON {TABLE} BEGIN SELECT RAISE(ABORT,'append only'); END")

def pending_charges(dispatcher,record):
 """After real Popen wait only. Read whitelisted native accounting metadata."""
 l=dispatcher.ledger;j=record['job'];scope=record['scope'];terminal=record['terminal']
 need(record['child'] is not None and record['child'].returncode is not None and terminal is not None
      and terminal['wait_observed'] is True and (terminal['exit_code']!=0 or terminal['signal'] is not None),
      'AUX_UNKNOWN_ORIGINAL_FAILED_POPEN_WAIT')
 root=Path(record['config']['aux_root']);branch=root/f"k{j['replicate']}"
 native=branch/'ledger.json';book=branch/'ledger.json.reservations-v52.json'
 need(native.is_file()and book.is_file()and native.resolve()==native and book.resolve()==book,
      'AUX_UNKNOWN_EXISTING_NATIVE_ACCOUNTING_METADATA')
 native_pin=hash_file(native);book_pin=hash_file(book);n=strict(native.read_bytes());b=strict(book.read_bytes())
 with l.mutex:
  permits=[dict(p)for p in l.db.execute('SELECT * FROM aux_permits WHERE scope=?',(scope,))]
  pending=[p for p in permits if p['state']in('RESERVED','SENT','UNKNOWN')]
  need(set(n['requests'])=={p['request_id']for p in permits if p['request_id']is not None},
       'AUX_UNKNOWN_NATIVE_HOST_REQUEST_SET')
 rows=[]
 for p in pending:
  rid=p['request_id'];need(p['state']in('SENT','UNKNOWN')and rid is not None,'AUX_UNKNOWN_NO_UNSENT_CHARGE')
  r=n['requests'][rid];need(r['state']in UNKNOWN_STATES and r['role']=='single','AUX_UNKNOWN_NATIVE_CLASSIFICATION_REQUIRED')
  a=b.get('active',{}).get(rid)
  if a is not None:
   upper=a['upper'];need(type(upper)is int and upper==a['input_upper_bound']+a['max_output_tokens']and upper>0,
                        'AUX_UNKNOWN_ORIGINAL_RESERVATION_UPPER')
  else:
   need(r['state']=='UNKNOWN_CHARGED'and type(r['tokens'])is int and r['tokens']>0,
        'AUX_UNKNOWN_RESERVATION_OR_NATIVE_CONSERVATIVE_CHARGE_REQUIRED');upper=r['tokens']
  with l.mutex:prior=l.db.execute('SELECT metadata FROM '+TABLE+' WHERE request_id=?',(rid,)).fetchone()
  if prior:
   row=strict(prior[0].encode())
   need(all(row.get(k)==v for k,v in {'job_id':j['id'],'claim':j['claim'],'point_id':j['point'],
        'replicate_id':j['replicate'],'attempt':j.get('attempt',1),'scope':scope,'permit_id':p['id'],
        'request_id':rid,'charged_tokens':upper,'native_ledger_pin':native_pin,'native_reservation_book_pin':book_pin,
        'billing_domain':'AUX_FINALIZATION','search_budget_delta':0,'physical_terminal_proven':False,
        'no_replay':True,'no_usage_backfill':True,'no_terminal_backfill':True}.items()),'AUX_UNKNOWN_EXACT_PRIOR_CHARGE')
  else:
   row={'kind':KIND,'schema':'agensh-aux-unknown-reservation-charge-v1','trajectory':j['trajectory'],
    'point_id':j['point'],'job_id':j['id'],'claim':j['claim'],'replicate_id':j['replicate'],
    'attempt':j.get('attempt',1),'scope':scope,'permit_id':p['id'],'request_id':rid,
    'billing_domain':'AUX_FINALIZATION','charged_tokens':upper,
    'input_upper_bound':a['input_upper_bound']if a else None,'max_output_tokens':a['max_output_tokens']if a else None,
    'charge_basis':'USER_AUTHORIZED_RESERVATION_UPPER_BOUND_NOT_MEASURED_USAGE','search_budget_delta':0,
    'physical_terminal_proven':False,'original_host_state':p['state'],'original_native_state':r['state'],
    'native_ledger_pin':native_pin,'native_reservation_book_pin':book_pin,'no_replay':True,
    'no_usage_backfill':True,'no_terminal_backfill':True,'original_native_active_reservation_retained':a is not None}
   with l.tx():l.db.execute('INSERT INTO '+TABLE+' VALUES(?,?)',(rid,wire(row).decode()));l.event(j['trajectory'],KIND,row)
  rows.append(row)
 need(hash_file(native)==native_pin and hash_file(book)==book_pin,'AUX_UNKNOWN_EXITED_METADATA_CHANGED')
 return rows,permits,n,b,native_pin

def proof(dispatcher,record,charges,permits,n,b,native_pin):
 j=record['job'];ids={r['request_id']for r in charges};pending={p['request_id']for p in permits if p['state']in('RESERVED','SENT','UNKNOWN')}
 need(ids==pending and ids,'AUX_UNKNOWN_EACH_PENDING_SLOT_EXPLICITLY_CHARGED')
 need(set(b.get('active',{}))<=ids,'AUX_UNKNOWN_NO_UNCHARGED_ACTIVE_RESERVATION')
 all_tokens=0;measured=0
 for rid,r in n['requests'].items():
  need(r['role']=='single'and type(r['tokens'])is int and r['tokens']>=0,'AUX_UNKNOWN_NATIVE_TOKEN_FIELDS')
  all_tokens+=r['tokens']
  if rid in ids:need(r['state']in UNKNOWN_STATES,'AUX_UNKNOWN_ONLY_AUTHORIZED_NATIVE_UNKNOWN')
  else:
   need(r['state']in('COMPLETED','UNKNOWN_CHARGED','REJECTED_PREGEN','RETRYABLE_REJECTED'),'AUX_UNKNOWN_OTHER_NATIVE_SETTLEMENT')
   measured+=r['tokens']
 need(n['actual_tokens']==all_tokens and n['model_calls']==len(n['requests']),'AUX_UNKNOWN_NATIVE_ACCOUNTING_TOTALS')
 cp=Path(record['config']['aux_root'])/f"evaluator-custody-k{j['replicate']}"/'custody.sqlite'
 eu,ep=original_attempts.custody(cp)
 need(eu==0,'AUX_UNKNOWN_NO_UNRESOLVED_EVALUATOR')
 return {'schema':'aux-partial-explicit-unknown-logical-closure-v1','scope':record['scope'],
  'model_unresolved':len(pending),'logical_model_unresolved':0,'physical_unknown_slots_retained':len(pending),
  'evaluator_unresolved':0,'native_aux_tokens':measured,'native_request_count':len(n['requests']),
  'request_ids_sha256':digest(sorted(n['requests'])),'native_ledger_sha256':native_pin['sha256'],
  'terminal_sha256':digest(record['terminal']),'evaluator_proof_sha256':ep,
  'unknown_aux_reservation_charge':sum(r['charged_tokens']for r in charges),
  'unknown_charge_receipts':[{k:r[k]for k in('request_id','permit_id','charged_tokens')}|{'metadata_sha256':digest(r)}for r in charges],
  'provider_terminal_claimed':False,'native_usage_rewritten':False,'search_budget_delta':0}

def partial_and_replace(q,job_id,claim,p):
 """Original max2/new-RNG enqueue algorithm; new proof says logical≠physical."""
 with q.tx():
  j=q._job(job_id);attempt=j.get('attempt',1)
  need(j['state']=='CHILD_EXITED_HOLD'and j['claim']==claim,'AUX_PARTIAL_ORIGINAL_FAILED_CLAIM')
  terminal=strict(j['terminal'].encode());need(terminal['wait_observed']is True and (terminal['exit_code']!=0 or terminal['signal']is not None),
    'AUX_PARTIAL_REAL_FAILED_TERMINAL')
  need(p['schema']=='aux-partial-explicit-unknown-logical-closure-v1'and p['logical_model_unresolved']==p['evaluator_unresolved']==0
       and p['model_unresolved']==p['physical_unknown_slots_retained']==len(p['unknown_charge_receipts'])
       and p['model_unresolved']>0 and p['terminal_sha256']==digest(terminal)
       and p['unknown_aux_reservation_charge']==sum(r['charged_tokens']for r in p['unknown_charge_receipts'])
       and p['provider_terminal_claimed']is False and p['native_usage_rewritten']is False,
       'AUX_PARTIAL_EXPLICIT_AUTHORIZED_LOGICAL_NOT_PHYSICAL_CLOSURE')
  row={'policy':final_attempts.POLICY,'point_id':j['point'],'replicate_id':j['replicate'],'attempt':attempt,
   'original_claim':claim,'disposition':'PARTIAL','allocation':'SYSTEM_CONSUMPTION',
   'billing_domain':'AUX_FINALIZATION','search_budget_delta':0,**p,
   'allocation_note':'native measured failed-replicate AUX only; UNKNOWN charge remains separate AUX_FINALIZATION, not system allocation'}
  old=q.db.execute('SELECT metadata FROM replicate_partials WHERE job_id=?',(job_id,)).fetchone()
  if old is not None:need(strict(old[0].encode())==row,'AUX_PARTIAL_APPEND_DISPOSITION_CONFLICT')
  else:
   q.db.execute('INSERT INTO replicate_partials VALUES(?,?)',(job_id,wire(row).decode()))
   q.event('REPLICATE_PARTIAL_AUX_UNKNOWN_EXPLICIT_CHARGE',{'job_id':job_id,**row})
  if attempt>=3:return None
  nxt=attempt+1;new=digest({'point':j['point'],'replicate':j['replicate'],'attempt':nxt})
  if q.db.execute('SELECT 1 FROM replacement_jobs WHERE id=?',(new,)).fetchone()is None:
   q.db.execute("INSERT INTO replacement_jobs VALUES(?,?,?,'QUEUED',NULL,NULL,NULL,NULL,?,?)",(new,j['point'],j['replicate'],nxt,j.get('original_job',job_id)))
   q.event('ONE_REPLICATE_REPLACEMENT_ENQUEUED',{'job_id':new,'failed_job_id':job_id,'point_id':j['point'],
    'replicate_id':j['replicate'],'attempt':nxt,'rng_policy_sha256':digest(final_attempts.RNG_POLICY),
    'new_requests_required':True,'billing_domain':'AUX_FINALIZATION','search_budget_delta':0,'policy':final_attempts.POLICY})
  return new

def _threshold(dispatcher,point):
 l=dispatcher.ledger
 with l.mutex:
  l=dispatcher.ledger;scopes={r['scope']for r in dispatcher.children.values()if r['job']['point']==point and r.get('scope')}
  charged={r['request_id']for r in _rows(l)if r['point_id']==point}
  tail=0
  for e in l.db.execute("SELECT metadata FROM events WHERE kind='AUX_MODEL_SENT'ORDER BY seq"):
   meta=strict(e[0].encode())
   if meta['scope']not in scopes:continue
   p=l.db.execute('SELECT state FROM aux_permits WHERE id=?',(meta['permit_id'],)).fetchone()
   if meta['request_id']in charged:tail+=1
   elif p is not None and p[0]=='TERMINAL':tail=0
   # Undecided physical requests are not fabricated successes or failures.
  return tail

def _financial_stop(l,t,code):
 l.latch_fault(t,code)
 with l.tx():
  l.db.execute("UPDATE model_control SET paused=1,epoch=epoch+1,reason=?WHERE singleton=1",(code,))
  l.event(t,'AUX_UNKNOWN_FINANCIAL_OR_THRESHOLD_STOP',{'code':code,'requests_replayed':0})

def dispose(dispatcher,record,original):
 l=dispatcher.ledger;scope=record.get('scope')
 with l.mutex:pending=l.db.execute("SELECT COUNT(*)FROM aux_permits WHERE scope=?AND state IN('RESERVED','SENT','UNKNOWN')",(scope,)).fetchone()[0]
 if not pending:return original(dispatcher,record)
 try:
  charges,permits,n,b,native_pin=pending_charges(dispatcher,record)
  p=proof(dispatcher,record,charges,permits,n,b,native_pin)
  if _threshold(dispatcher,record['job']['point'])>=3:
   _financial_stop(l,record['job']['trajectory'],'THREE_CONSECUTIVE_AUX_UNKNOWNS_SAME_POINT_STOP')
   need(False,'THREE_CONSECUTIVE_AUX_UNKNOWNS_SAME_POINT_STOP')
  j=record['job']
  allocation={'job_id':j['id'],'claim':j['claim'],'point_id':j['point'],'replicate_id':j['replicate'],
   'attempt':j.get('attempt',1),'policy':final_attempts.POLICY,'allocation':'SYSTEM_CONSUMPTION',
   'billing_domain':'AUX_FINALIZATION','search_budget_delta':0,**p,
   'allocation_note':'native measured failed-replicate AUX only; UNKNOWN charge remains separate AUX_FINALIZATION'}
  with l.tx():
   l.db.execute('CREATE TABLE IF NOT EXISTS aux_attempt_allocations(job_id TEXT PRIMARY KEY,metadata TEXT NOT NULL)')
   for action in ('UPDATE','DELETE'):
    l.db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{action.lower()}_aux_attempt_allocation BEFORE {action} ON aux_attempt_allocations BEGIN SELECT RAISE(ABORT,'append only'); END")
   old=l.db.execute('SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',(j['id'],)).fetchone()
   if old is not None:need(strict(old[0].encode())==allocation,'AUX_UNKNOWN_ALLOCATION_CONFLICT')
   else:
    l.db.execute('INSERT INTO aux_attempt_allocations VALUES(?,?)',(j['id'],wire(allocation).decode()))
    l.event(j['trajectory'],'AUX_FAILED_REPLICATE_SYSTEM_CONSUMPTION',allocation)
  replacement=partial_and_replace(dispatcher.queue,j['id'],j['claim'],p)
  record['partial']=True;record['replacement_job_id']=replacement;record['aux_unknown_logical_disposition']=p
  need(replacement is not None,'FINAL_REPLICATE_TWO_REPLACEMENTS_EXHAUSTED')
  return replacement
 except Refused as error:
  # K3/evaluator/claim failure stays point-local. Only actual financial evidence
  # inconsistency (or the explicit three-UNKNOWN threshold above) is global.
  financial={'AUX_UNKNOWN_EXISTING_NATIVE_ACCOUNTING_METADATA','AUX_UNKNOWN_NATIVE_HOST_REQUEST_SET',
   'AUX_UNKNOWN_NO_UNSENT_CHARGE','AUX_UNKNOWN_NATIVE_CLASSIFICATION_REQUIRED',
   'AUX_UNKNOWN_ORIGINAL_RESERVATION_UPPER','AUX_UNKNOWN_RESERVATION_OR_NATIVE_CONSERVATIVE_CHARGE_REQUIRED',
   'AUX_UNKNOWN_EXACT_PRIOR_CHARGE','AUX_UNKNOWN_EXITED_METADATA_CHANGED',
   'AUX_UNKNOWN_EACH_PENDING_SLOT_EXPLICITLY_CHARGED','AUX_UNKNOWN_NO_UNCHARGED_ACTIVE_RESERVATION',
   'AUX_UNKNOWN_NATIVE_TOKEN_FIELDS','AUX_UNKNOWN_ONLY_AUTHORIZED_NATIVE_UNKNOWN',
   'AUX_UNKNOWN_OTHER_NATIVE_SETTLEMENT','AUX_UNKNOWN_NATIVE_ACCOUNTING_TOTALS'}
  if error.code in financial:_financial_stop(l,record['job']['trajectory'],'AUX_UNKNOWN_DISPOSITION_FINANCIAL_EVIDENCE_REQUIRES_CARETAKER')
  raise

def bind_logical(ledger):
 """Call after CapacityPeer attaches; preserve its independent closure formula."""
 original=ledger.global_logical_unresolved
 if getattr(original,'_aux_unknown_logical',False):return
 def logical():
  with ledger.mutex:
   count=ledger.db.execute("SELECT COUNT(*)FROM aux_permits p JOIN "+TABLE+" c ON p.request_id=c.request_id WHERE p.state IN('SENT','UNKNOWN')").fetchone()[0]
   return original()-count
 logical._aux_unknown_logical=True;ledger.global_logical_unresolved=logical

def _pause_unknown(driver,original,scope,metadata):
 if type(metadata)is not dict or metadata.get('classification')!='UNKNOWN_CHARGED':return original(scope,metadata)
 # Identical public metadata validators to original ModelCapacity.pause.
 from common import ident
 allowed={'http_status','error_type','timeout','setting','role','request_id','charged_tokens','classification','finalization'}
 need(set(metadata)<=allowed,'CAPACITY_INCIDENT_METADATA_ONLY')
 if 'error_type'in metadata:ident(metadata['error_type'])
 if 'request_id'in metadata:ident(metadata['request_id'])
 if 'http_status'in metadata:need(metadata['http_status']is None or type(metadata['http_status'])is int and 100<=metadata['http_status']<=599,'CAPACITY_INCIDENT_HTTP')
 if 'charged_tokens'in metadata:integer(metadata['charged_tokens'],'CAPACITY_INCIDENT_TOKENS')
 for key in ('timeout','finalization'):
  if key in metadata:need(type(metadata[key])is bool,'CAPACITY_INCIDENT_BOOL')
 if 'setting'in metadata:need(metadata['setting']in('Agensh-16','Agensh-1'),'CAPACITY_INCIDENT_SETTING')
 if 'role'in metadata:need(metadata['role']=='single','CAPACITY_INCIDENT_ROLE')
 l=driver.ledger;rid=metadata.get('request_id')
 with l.tx():
  owner=driver.capacity._scope(scope) # original authority/identity unchanged
  record=next((r for r in driver.dispatcher.children.values()if r.get('scope')==scope),None)
  need(record is not None,'AUX_UNKNOWN_PAUSE_ORIGINAL_POINT')
  permit=l.db.execute('SELECT * FROM aux_permits WHERE scope=?AND request_id=?',(scope,rid)).fetchone()
  need(permit is not None and permit['state']in('SENT','UNKNOWN')and type(metadata.get('charged_tokens'))is int
       and metadata['charged_tokens']>0,'AUX_UNKNOWN_PAUSE_SENT_CLASSIFIED_RESERVATION')
  point=record['job']['point'];old=l.db.execute('SELECT metadata FROM aux_unknown_pause_incidents WHERE request_id=?',(rid,)).fetchone()
  row={'scope':scope,'point_id':point,'request_id':rid,'metadata':metadata}
  if old is not None:need(strict(old[0].encode())==row,'AUX_UNKNOWN_PAUSE_REPEATED_METADATA_CHANGED')
  else:
   l.db.execute('INSERT INTO aux_unknown_pause_incidents VALUES(?,?)',(rid,wire(row).decode()))
   l.event(owner['trajectory'],'AUX_UNKNOWN_PAUSE_REQUEST_RECORDED_NOT_GLOBAL',row)
  scopes={r['scope']for r in driver.dispatcher.children.values()if r['job']['point']==point and r.get('scope')}
  incidents={strict(r[0].encode())['request_id']for r in l.db.execute('SELECT metadata FROM aux_unknown_pause_incidents')if strict(r[0].encode())['point_id']==point}
  tail=0
  for e in l.db.execute("SELECT metadata FROM events WHERE kind='AUX_MODEL_SENT'ORDER BY seq"):
   m=strict(e[0].encode())
   if m['scope']not in scopes:continue
   state=l.db.execute('SELECT state FROM aux_permits WHERE id=?',(m['permit_id'],)).fetchone()[0]
   if m['request_id']in incidents:tail+=1
   elif state=='TERMINAL':tail=0
  if tail>=3:
   l.db.execute("UPDATE model_control SET paused=1,epoch=epoch+1,reason='THREE_CONSECUTIVE_AUX_UNKNOWNS_SAME_POINT'WHERE singleton=1")
   l.event(owner['trajectory'],'THREE_CONSECUTIVE_AUX_UNKNOWNS_SAME_POINT_STOP',{'point_id':point,'consecutive':tail})
   return True
  return False # Native guard must not turn a single UNKNOWN into MaintenancePause.

def install(driver):
 need(not hasattr(driver,'_aux_unknown_policy'),'AUX_UNKNOWN_POLICY_INSTALL_ONCE')
 _schema(driver.ledger);bind_logical(driver.ledger)
 with driver.ledger.tx():
  driver.ledger.db.execute('CREATE TABLE IF NOT EXISTS aux_unknown_pause_incidents(request_id TEXT PRIMARY KEY,metadata TEXT NOT NULL)')
  for action in ('UPDATE','DELETE'):
   driver.ledger.db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{action.lower()}_aux_unknown_pause BEFORE {action} ON aux_unknown_pause_incidents BEGIN SELECT RAISE(ABORT,'append only'); END")
 original_pause=driver.capacity.pause
 driver.capacity.pause=lambda scope,metadata:_pause_unknown(driver,original_pause,scope,metadata)
 original=original_attempts.dispose
 def guarded(dispatcher,record):
  with dispatcher.ledger.mutex:exists=dispatcher.ledger.db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(TABLE,)).fetchone()
  if not exists:return original(dispatcher,record)
  return dispose(dispatcher,record,original)
 if not getattr(original,'_aux_unknown_guard',False):
  guarded._aux_unknown_guard=True;original_attempts.dispose=guarded
 driver._aux_unknown_policy={'table':TABLE,'original_dispose':original,'original_pause':original_pause,'physical_unknown_slots_retained':True}
 return driver._aux_unknown_policy

def retry_retained_points(driver):
 """After search recovery. Same claims/Popen; fresh replacements only."""
 need(not driver.failed and hasattr(driver,'_isolation')and not driver._isolation.defer_finals,
      'AUX_REPLACEMENT_AFTER_SEARCH_RESTORED')
 d=driver.dispatcher;result=[]
 with d.lock:
  for record in list(d.children.values()):
   child=record['child'];j=record['job']
   if child is None or child.poll()is None:continue
   if record['terminal']is None:record['terminal']=d.queue.reap(j['id'],j['claim'],child)
   if record['terminal']is None or record['terminal']['exit_code']==0:continue
   if not record.get('partial'):original_attempts.dispose(d,record)
   record.pop('isolated_fault',None)
   point=d.points[j['point']];point.pop('isolated_fault',None)
   driver._isolation.points.pop(j['point'],None)
   result.append({'job_id':j['id'],'replacement':record.get('replacement_job_id'),'partial':record.get('partial',False)})
 return result


def bind_extra_dispatcher(parent,dispatcher):
 """Apply the already-qualified point isolation to independent fork FINAL."""
 import trajectory_isolation as isolation_module
 need(hasattr(parent,'_isolation')and not getattr(dispatcher,'_aux_point_isolation',False),
      'AUX_FORK_ORIGINAL_PARENT_ISOLATION_ONCE')
 isolation=parent._isolation;original_dispatch=dispatcher.dispatch_one
 dispatcher._poll=MethodType(isolation_module._poll_replacement(dispatcher._poll,isolation),dispatcher)
 def fault(_,t,kind):
  records=[r for r in dispatcher.children.values()if r['job']['trajectory']==t]
  isolation.record(dispatcher,record=records[-1]if records else None,kind=kind)
 dispatcher._fault=MethodType(fault,dispatcher)
 def dispatch(_):
  try:return original_dispatch()
  except BaseException:
   if parent.failed or isolation_module.global_reason(dispatcher.ledger):raise
   return None
 dispatcher.dispatch_one=MethodType(dispatch,dispatcher);dispatcher._aux_point_isolation=True

def install_fork_manager(manager):
 """Same policy/metadata on independent fork AUX; never mainline billing."""
 from types import SimpleNamespace
 need(not hasattr(manager,'_aux_unknown_policy_proxy'),'AUX_BRANCH_POLICY_INSTALL_ONCE')
 proxy=SimpleNamespace(ledger=manager.l,capacity=manager.capacity,dispatcher=manager.dispatcher)
 receipt=install(proxy);manager._aux_unknown_policy_proxy=proxy
 bind_extra_dispatcher(manager.driver,manager.dispatcher)
 return receipt
