"""Natural terminal n<3 PUBLIC closeout. No private input or native re-audit.

The original n3 ABI is never patched or called. Successful native aggregates
are fixed original results, not new evaluations; failed attempts never score.
All original job terminal/disposition/allowed-extra chains must be exhausted.
"""
from pathlib import Path
import hashlib,json,os,sqlite3,stat,time,statistics
EXPECTED=dict(pid=940620,start='30685049',boot_id='c611833c-3ede-48d6-9e7a-3772afe31ecb')
ROOT=Path('/mnt/ptb-scratch2/ag31x48b46')
TRAJECTORY='agensh-v2-20261030-x48/Agensh-8/block-3/seed-2806506801'
TARGET=50000000
TRACKS=frozenset('agensh-v2-20261030-x48/Agensh-8/block-'+str(i)+'/seed-'+str(seed)for i,seed in((1,1855033666),(2,185023928),(3,2806506801)))
SCHEMA='count14-agensh-v21-k3-terminal-nlt3-public-v1'
PREPARED='K3_TERMINAL_NLT3_PREPARED_PUBLIC.json'
AUDIT='K3_TERMINAL_NLT3_AUDIT_PUBLIC.json'
RECEIPT='USER_NLT3_TERMINAL_SIDECAR_V1_PUBLIC.json'
FAILURE='USER_NLT3_TERMINAL_SIDECAR_V1_FAILURE_PUBLIC.json'
METRICS=('unique_candidates','correct_candidates','successful_tasks','maximum_one_to_one_matches')
POLICY='USER_20261027_K3_SINGLE_REPLICATE_MAX_TWO_REPLACEMENTS'
PINS={'final_queue': '7a7aeadc26ca35bdd64c6569634dab4ff6e9617ec9dee18a71ccd6797742773c', 'final_attempts': '9bc1cc86ceb8ae8d017dd0703d1f74cdca356d94882edb15bc600b604686b684', 'budget': 'a05ca90afffb7c149766cf4b74126eb94ba79910afd72049a1ff54d2bc50df8f'}
FORBIDDEN=frozenset(('private-context','evaluator-private','pocs','requests','credentials'))
NAMES=frozenset(('aggregate.json','physical-custody.json','input-policy.json','saved.json','POINT_QUEUED.json',PREPARED,AUDIT))

def need(ok):
 if not ok:raise RuntimeError('PUBLIC_CURRENT940_NLT3_TERMINAL_CLOSEOUT_REFUSED')
def wire(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def digest(v):return sha(wire(v))
def pin(v):return type(v)is str and len(v)==64 and all(c in'0123456789abcdef'for c in v)
def integer(v):return type(v)is int and v>=0
def narrow(e):
 out=[];tb=e.__traceback__
 while tb:out.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
 return dict(exception_type=type(e).__name__,locations=out,messages_locals_omitted=True)

def read_public(p,expected=None):
 p=Path(p);need(p.is_absolute()and p.resolve()==p and p.is_relative_to(ROOT)and p.name in NAMES and not FORBIDDEN.intersection(p.parts))
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  st=os.fstat(fd);need(stat.S_ISREG(st.st_mode)and st.st_nlink==1 and st.st_size<4*2**20)
  with os.fdopen(os.dup(fd),'rb')as f:raw=f.read(4*2**20)
  need(len(raw)==st.st_size and(expected is None or sha(raw)==expected))
  return json.loads(raw),dict(path=str(p),sha256=sha(raw),size=len(raw))
 finally:os.close(fd)

def queue_snapshot(o,point):
 import final_attempts,aux_allowance
 q=o.driver.queue;need(q.mutex.acquire(timeout=2.))
 try:
  rows=[r for r in final_attempts.all_rows(q)if r['point']==point];need(0<len(rows)<=12)
  partials={r['job_id']:json.loads(r['metadata'])for r in q.db.execute('SELECT job_id,metadata FROM replicate_partials WHERE job_id IN('+','.join('?'for _ in rows)+')',tuple(r['id']for r in rows))}
  maximum={}
  for k in(1,2,3):
   initial=[r for r in rows if r['replicate']==k and r.get('attempt',1)==1];need(len(initial)==1)
   maximum[k]=aux_allowance.maximum(q,initial[0]);need(maximum[k]in(3,4))
   need((maximum[k]==4)==aux_allowance.allowed(point,k,4))
  events=[json.loads(r[0])for r in q.db.execute("SELECT metadata FROM events WHERE kind='CHILD_TERMINAL'AND json_extract(metadata,'$.job_id')IN("+','.join('?'for _ in rows)+')',tuple(r['id']for r in rows))]
  waits={r['id']:sum(e==dict(job_id=r['id'],**json.loads(r['terminal']))for e in events)==1 if r['terminal']else False for r in rows}
  return dict(rows=rows,partials=partials,maximum=maximum,wait_events=waits)
 finally:q.mutex.release()

def waited(row):
 need(row['state']in('CHILD_EXITED_HOLD','COMPLETE')and type(row['claim'])is str and row['claim'])
 t=json.loads(row['terminal']);child=json.loads(row['child'])
 need(t.get('wait_observed')is True and t.get('identity')==child)
 code=t.get('exit_code');sig=t.get('signal')
 need((integer(code)and sig is None)or(code is None and type(sig)is int and sig>0))
 return t

def failed(row,t,p):
 need(type(p)is dict and p.get('policy')==POLICY and p.get('point_id')==row['point']and p.get('replicate_id')==row['replicate']and p.get('attempt')==row.get('attempt',1))
 need(p.get('original_claim')==row['claim']and p.get('disposition')=='PARTIAL'and p.get('allocation')=='SYSTEM_CONSUMPTION'and p.get('billing_domain')=='AUX_FINALIZATION'and p.get('search_budget_delta')==0)
 need(pin(p.get('scope'))and p.get('evaluator_unresolved')==0)
 disk=p.get('schema')=='disk-final-logical-disposition-proof-v1'
 if disk:
  provenance=p.get('custody_provenance',{});need(provenance==dict(custody='GENUINE_DURABLE_PARENT_WAIT',original_terminal_sha256=digest(t),original_claim=row['claim']))
 else:need(p.get('terminal_sha256')==digest(t))
 if disk:
  need(integer(p.get('model_unresolved'))and p.get('logical_model_unresolved')==0 and p.get('physical_unknown_slots_retained')==p['model_unresolved'])
  need(p.get('provider_terminal_claimed')is False and p.get('native_usage_rewritten')is False and(t['exit_code']!=0 or t['signal']is not None))
  need(integer(p.get('unknown_aux_reservation_charge'))and integer(p.get('native_unreported_unknown_count')))
 elif p.get('schema')=='aux-partial-explicit-unknown-logical-closure-v1':
  receipts=p.get('unknown_charge_receipts');need(type(receipts)is list and receipts)
  need(p.get('logical_model_unresolved')==0 and p.get('model_unresolved')==p.get('physical_unknown_slots_retained')==len(receipts))
  need(p.get('provider_terminal_claimed')is False and p.get('native_usage_rewritten')is False and all(integer(r.get('charged_tokens'))and pin(r.get('metadata_sha256'))for r in receipts))
  need(p.get('unknown_aux_reservation_charge')==sum(r['charged_tokens']for r in receipts))
  # Native exit0 can be a formally disposed UNKNOWN; it is still NOT valid.
 else:need(p.get('model_unresolved')==0 and(t['exit_code']!=0 or t['signal']is not None))
 for name in('native_aux_tokens','native_request_count'):need(integer(p.get(name)))
 for name in('native_ledger_sha256','evaluator_proof_sha256'):need(pin(p.get(name)))
 if not disk:need(pin(p.get('request_ids_sha256')))
 return dict(job_id=row['id'],replicate_index=row['replicate'],replicate_attempt=row.get('attempt',1),disposition_sha256=digest(p),terminal_sha256=digest(t),physical_UNKNOWN_retained=p.get('physical_unknown_slots_retained',0),valid=False)

def select_naturally_terminal(snapshot):
 rows=snapshot['rows'];partials=snapshot['partials'];selected=[];excluded=[];exhausted=[]
 need(len({r['id']for r in rows})==len(rows)and set(r['replicate']for r in rows)=={1,2,3})
 for k in(1,2,3):
  group=[r for r in rows if r['replicate']==k];by_attempt={r.get('attempt',1):r for r in group};need(len(by_attempt)==len(group))
  # All attempts are checked; never select the largest/most successful result.
  need(set(by_attempt)==set(range(1,len(group)+1))and len(group)<=snapshot['maximum'][k])
  initial=by_attempt[1]['id'];valid=[]
  for a in range(1,len(group)+1):
   row=by_attempt[a];need(snapshot['wait_events'].get(row['id'])is True);t=waited(row)
   need(a==1 or row.get('original_job')==initial)
   if row['id']in partials:excluded.append(failed(row,t,partials[row['id']]))
   else:
    need(t['exit_code']==0 and t['signal']is None);valid.append(row)
  need(len(valid)<=1)
  if valid:
   # No attempt can follow an already valid result, even if its score is lower.
   need(valid[0].get('attempt',1)==len(group));selected.extend(valid)
  else:
   need(len(group)==snapshot['maximum'][k]);exhausted.append(k)
 return selected,excluded,exhausted

def financial_disposition(o,row,p):
 l=o.driver.ledger;need(l.mutex.acquire(timeout=4.))
 try:
  found=l.db.execute('SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',(row['id'],)).fetchone();need(found is not None)
  allocation=json.loads(found[0]);need(all(allocation.get(k)==v for k,v in dict(job_id=row['id'],claim=row['claim'],point_id=row['point'],replicate_id=row['replicate'],attempt=row.get('attempt',1)).items()))
  keys=('schema','custody_provenance','native_unreported_unknown_count','policy','allocation','billing_domain','search_budget_delta','scope','model_unresolved','logical_model_unresolved','physical_unknown_slots_retained','evaluator_unresolved','native_aux_tokens','native_request_count','request_ids_sha256','native_ledger_sha256','terminal_sha256','evaluator_proof_sha256','unknown_aux_reservation_charge','unknown_charge_receipts','provider_terminal_claimed','native_usage_rewritten')
  need(all(allocation.get(k)==p[k]for k in keys if k in p))
  if p.get('schema')=='disk-final-logical-disposition-proof-v1':
   charges=[json.loads(r[0])for r in l.db.execute("SELECT metadata FROM aux_unknown_reservation_charges WHERE json_extract(metadata,'$.job_id')=?",(row['id'],))]
   need(len(charges)==p['model_unresolved']and len({c['request_id']for c in charges})==len(charges))
   need(sum(c['charged_tokens']for c in charges)==p['unknown_aux_reservation_charge'])
   for charge in charges:
    need(all(charge.get(k)==v for k,v in dict(job_id=row['id'],claim=row['claim'],point_id=row['point'],replicate_id=row['replicate'],attempt=row.get('attempt',1),scope=p['scope'],physical_terminal_proven=False,no_replay=True,no_usage_backfill=True,no_terminal_backfill=True).items()))
  for receipt in p.get('unknown_charge_receipts',[]):
   charge=l.db.execute('SELECT metadata FROM aux_unknown_reservation_charges WHERE request_id=?',(receipt['request_id'],)).fetchone();need(charge is not None)
   charge=json.loads(charge[0]);need(digest(charge)==receipt['metadata_sha256']and charge.get('charged_tokens')==receipt['charged_tokens']and charge.get('permit_id')==receipt['permit_id'])
 finally:l.mutex.release()

def scope_binding(o,scope,point,row,policy):
 l=o.driver.ledger;need(l.mutex.acquire(timeout=4.))
 try:
  r=l.db.execute('SELECT trajectory,binding FROM aux_scopes WHERE scope=?',(scope,)).fetchone();need(r is not None)
  binding=json.loads(r[1]);need(digest(binding)==scope)
  need(r[0]==binding.get('trajectory')==TRAJECTORY and binding.get('setting')=='Agensh-8'and binding.get('purpose')=='AUX_FINALIZATION')
  need(binding.get('target_tokens')==TARGET and binding.get('replicate_index')==row['replicate']and binding.get('input_policy_sha256')==policy and binding.get('manifest_sha256')==o.driver.queue.manifest)
  a=row.get('attempt',1)
  if a>1:need(binding.get('replicate_attempt')==a and binding.get('point_id')==point)
  else:need(binding.get('replicate_attempt',1)==1)
  need(l.db.execute("SELECT COUNT(*)FROM aux_permits WHERE scope=?AND state IN('RESERVED','SENT','UNKNOWN')",(scope,)).fetchone()[0]==0)
 finally:l.mutex.release()

def identity(o):
 import final_queue as original_queue,budget as original_budget,final_attempts as original_attempts
 need(o.identity==EXPECTED and os.getpid()==EXPECTED['pid']and os.geteuid()==0 and o.activated and o.home==ROOT/'d')
 a=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()
 need(a[19]==EXPECTED['start']and a[0]not in('Z','X')and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==EXPECTED['boot_id'])
 need(TRAJECTORY in TRACKS and TARGET in(10000000,20000000,50000000,100000000))
 need(o.driver.queue.home==o.home/'final-queue'and o.driver.ledger.home==o.home/'ledger')
 need(type(o.driver.queue)is original_queue.FinalQueue and type(o.driver.ledger)is original_budget.Ledger)
 for name,module in(('final_queue',original_queue),('final_attempts',original_attempts),('budget',original_budget)):
  need(sha(Path(module.__file__).read_bytes())==PINS[name])

def prepare(o):
 identity(o);point=digest(dict(trajectory=TRAJECTORY,target=TARGET));snap=queue_snapshot(o,point)
 valid,excluded,exhausted=select_naturally_terminal(snap)
 for row in snap['rows']:
  if row['id']in snap['partials']:financial_disposition(o,row,snap['partials'][row['id']])
 if len(valid)==3:return dict(original_n3_NOOP=True,point=point)
 first=snap['rows'][0];need(all(r['trajectory']==TRAJECTORY and r['setting']=='Agensh-8'and r['target']==TARGET and r['input_root']==first['input_root']and r['input_policy']==first['input_policy']for r in snap['rows']))
 ir=Path(first['input_root']);ip,ip_pin=read_public(ir/'input-policy.json',first['input_policy']);saved,saved_pin=read_public(ir/'snapshot/saved.json',ip['saved']['sha256']);seal,seal_pin=read_public(ir.parent/'POINT_QUEUED.json')
 need(pin(ip['snapshot_sha256'])and pin(ip['pins']['source'])and pin(ip['pins']['manifest']))
 need(ip['trajectory']==TRAJECTORY and ip['target_tokens']==TARGET and saved['nominal_budget']==TARGET and saved['original_snapshot_sha256']==ip['snapshot_sha256'])
 need(seal['snapshot']['sha256']==ip['snapshot_sha256']and seal['target_tokens']==TARGET and ip['pins']['manifest']==o.driver.queue.manifest)
 aux=o.home/'final-points'/digest(point);need(aux.resolve()==aux and aux.is_dir())
 evidence=[];records=[];files=[ip_pin,saved_pin,seal_pin]
 for row in valid:
  k=row['replicate'];a=row.get('attempt',1);base=aux if a==1 else aux/'replacement-attempts'/f'k{k}-a{a}'
  aggregate,ap=read_public(base/'results/Agensh-8'/f's{TARGET//1000000}m-k{k}'/'aggregate.json',row['result']if row['state']=='COMPLETE'else None)
  custody,cp=read_public(base/f'k{k}'/'physical-custody.json');files.extend((ap,cp))
  need(aggregate.get('complete')is True and aggregate.get('evaluation_complete')is True and aggregate['trajectory']==TRAJECTORY and aggregate['replicate_index']==k and aggregate['input_policy_sha256']==first['input_policy'])
  need(aggregate['source_sha256']==ip['pins']['source']and aggregate['protocol_sha256']==o.driver.manifest['protocol']['final_v21'])
  need(custody.get('schema')=='count14-agensh-final-physical-custody-v1'and custody.get('native_model_and_evaluator_scopes_terminal')is True and custody.get('unresolved')==0)
  need(custody['aggregate_sha256']==ap['sha256']and custody['trajectory']==TRAJECTORY and custody['replicate_index']==k and custody['target_tokens']==TARGET and custody['input_policy_sha256']==first['input_policy'])
  need(custody['evaluator_custody']['physical_terminal']is True and custody['evaluator_custody']['unresolved']==0)
  if a>1:need(aggregate['replicate_attempt']==custody['replicate_attempt']==a and aggregate['point_id']==custody['point_id']==point)
  for metric in METRICS:need(integer(aggregate.get(metric)))
  scope_binding(o,aggregate['native_domain_binding_sha256'],point,row,first['input_policy'])
  records.append(aggregate);evidence.append(dict(job_id=row['id'],replicate_index=k,replicate_attempt=a,aggregate=ap,custody=cp,scope=aggregate['native_domain_binding_sha256'],terminal_sha256=digest(waited(row))))
 for key in('initial_input_sha256','frozen_catalog_sha256'):
  need(all(pin(r.get(key))for r in records)and len({r[key]for r in records})<=1)
 need(queue_snapshot(o,point)==snap)
 return dict(original_n3_NOOP=False,point=point,snapshot=snap,selected=valid,records=records,evidence=evidence,excluded=excluded,exhausted=exhausted,files=files,aux=aux,policy_sha256=first['input_policy'],snapshot_sha256=ip['snapshot_sha256'])

def commit(o,p):
 from common import publish
 if p['original_n3_NOOP']:return dict(PASS=True,original_n3_NOOP=True,point=p['point'],no_original_scientific_method_or_audit_changed=True)
 point=p['point'];aux=p['aux'];need(not(aux/AUDIT).exists()and not(aux/PREPARED).exists())
 for f in p['files']:read_public(Path(f['path']),f['sha256'])
 need(queue_snapshot(o,point)==p['snapshot'])
 provenance=dict(schema='count14-agensh-terminal-nlt3-prepared-v1',point=point,trajectory=TRAJECTORY,target_tokens=TARGET,owner=EXPECTED,source_queue_snapshot_sha256=digest(p['snapshot']),source_files=p['files'],evidence=p['evidence'],excluded_attempts=p['excluded'],exhausted_replicate_indices=p['exhausted'],PASS=False,not_terminal_acceptance=True)
 publish(aux/PREPARED,wire(provenance),mode=0o400)
 # Only original completion of already-successful/waited children; no request.
 q=o.driver.queue
 for row,e in zip(p['selected'],p['evidence']):
  need(q.mutex.acquire(timeout=2.))
  try:
   actual=q._job(row['id']);need(actual==row)
   if row['state']!='COMPLETE':q.complete(row['id'],row['claim'],result_sha256=e['aggregate']['sha256'],verified_native_audit=dict(job_id=row['id'],result_sha256=e['aggregate']['sha256'],complete=True,unresolved_physical_custody=0,terminal_nlt3_prepared_sha256=digest(provenance)))
  finally:q.mutex.release()
 after=queue_snapshot(o,point);selected,excluded,exhausted=select_naturally_terminal(after)
 need([r['id']for r in selected]==[r['id']for r in p['selected']]and all(r['state']=='COMPLETE'for r in selected)and excluded==p['excluded']and exhausted==p['exhausted'])
 for row,e in zip(selected,p['evidence']):need(row['result']==e['aggregate']['sha256'])
 for f in p['files']:read_public(Path(f['path']),f['sha256'])
 n=len(selected);need(n in(0,1,2))
 result=dict(schema=SCHEMA,PASS=True,owner=EXPECTED,producer_source_sha256=sha(Path(__file__).read_bytes()),trajectory=TRAJECTORY,setting='Agensh-8',nominal_budget=TARGET,point=point,terminal=True,complete=n>0,evaluation_complete=n>0,score_computable=n>0,planned_replicates=3,replicates_complete=n,replacement_policy=POLICY,maximum_attempts_by_replicate={str(k):v for k,v in p['snapshot']['maximum'].items()},all_original_slots_naturally_terminal=True,all_unsuccessful_slots_exhausted=True,no_QUEUED_RUNNING_or_CUSTODY_UNKNOWN_ignored=True,input_policy_sha256=p['policy_sha256'],source_snapshot_sha256=p['snapshot_sha256'],means={m:statistics.fmean(r[m]for r in p['records']) for m in METRICS}if n else None,ranges={m:[min(r[m]for r in p['records']),max(r[m]for r in p['records'])]for m in METRICS}if n else None,evidence=p['evidence'],source_files=p['files'],excluded_attempts=p['excluded'],exhausted_replicate_indices=p['exhausted'],prepared_sha256=digest(provenance),source_queue_snapshot_after_sha256=digest(after),validated_before_publication_at_ns=time.time_ns(),search_feedback=False,billing_domain='AUX_FINALIZATION',original_n3_ABI_methods_and_files_unchanged=True,original_scores_not_reevaluated_or_changed=True,UNKNOWN_fees_and_physical_unproven_slots_NOT_released=True,union_metrics_not_recomputed_and_not_available=True,score_is_only_mean_of_original_valid_replicates=True,not_system_consumption_or_whole_AUX_invoice=True)
 publish(aux/AUDIT,wire(result),mode=0o400)
 return result

def apply(o):
 from common import publish
 try:
  result=commit(o,prepare(o))
  # This is observed AFTER durable audit publication, never the earlier check
  # time, mtime, collector arrival or report publication time. Boundary is <.
  accepted_at_ns=time.time_ns()
  receipt=dict(PASS=True,schema='count14-agensh-v21-terminal-nlt3-accepted-public-v1',owner=EXPECTED,point=result['point'],original_n3_NOOP=result.get('original_n3_NOOP',False),terminal_audit_published=not result.get('original_n3_NOOP',False),producer_schema=SCHEMA,models=0,durable_audit_acceptance_observed_at_ns=accepted_at_ns)
  if not result.get('original_n3_NOOP',False):receipt.update(audit_sha256=digest(result),producer_source_sha256=result['producer_source_sha256'],replicates_complete=result['replicates_complete'],score_computable=result['score_computable'])
  publish(o.control.approved/RECEIPT,wire(receipt),mode=0o600)
 except BaseException as e:
  publish(o.control.approved/FAILURE,wire(dict(PASS=False,**narrow(e),retain_all_partial_no_automatic_retry=True)),mode=0o600);raise
