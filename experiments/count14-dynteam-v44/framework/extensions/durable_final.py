"""FINAL-only disk custody. Never constructs a scientific driver or SEARCH team.

Old genuine wait receipts stay evidence of the OLD parent's wait. They are never
wrapped as a Popen, re-polled, or reported as a wait by this new process. Orphans
have a separate disposition with unknown exit status and original raw rows kept.
"""
from pathlib import Path
import copy,json,os,threading,time
from common import need,digest,wire,publish,hash_file,strict,private_dir
import final_attempts as A
import native_replicate_attempts as R
from native_final_dispatch import NativeFinalDispatcher

PENDING=('RESERVED','SENT','UNKNOWN')

def ended(identity):
 """Existing identity metadata only; no signals/attach/foreign waitpid."""
 from final_queue import process_identity
 need(type(identity)is dict and set(identity)=={'pid','ppid','start','boot_id'},'DISK_ORIGINAL_EXACT_IDENTITY')
 try:current=process_identity(identity['pid'])
 except FileNotFoundError:return True
 return (current['boot_id'],current['start'])!=(identity['boot_id'],identity['start'])

def durable_wait(q,j):
 """Durable original terminal + matching append-only CHILD_TERMINAL event."""
 need(j['state']in('CHILD_EXITED_HOLD','COMPLETE')and j['child']and j['terminal'],'DISK_ORIGINAL_TERMINAL_REQUIRED')
 t=strict(j['terminal'].encode());child=strict(j['child'].encode())
 need(t.get('wait_observed')is True and t.get('identity')==child,'DISK_GENUINE_OLD_WAIT_IDENTITY')
 need((type(t.get('exit_code'))is int and t.get('signal')is None)or(t.get('exit_code')is None and type(t.get('signal'))is int),'DISK_GENUINE_OLD_WAIT_OUTCOME')
 rows=[strict(r[0].encode())for r in q.db.execute("SELECT metadata FROM events WHERE kind='CHILD_TERMINAL'")]
 need(any(r==dict(job_id=j['id'],**t)for r in rows),'DISK_GENUINE_OLD_WAIT_APPEND_ONLY_EVENT')
 return t

def append(q_or_l,table,key,value):
 """Caller holds tx. New additive append-only table, idempotent exact replay."""
 db=q_or_l.db;db.execute('CREATE TABLE IF NOT EXISTS '+table+'(id TEXT PRIMARY KEY,metadata TEXT NOT NULL)')
 for action in('UPDATE','DELETE'):
  db.execute('CREATE TRIGGER IF NOT EXISTS no_'+action.lower()+'_'+table+' BEFORE '+action+' ON '+table+" BEGIN SELECT RAISE(ABORT,'append only'); END")
 prior=db.execute('SELECT metadata FROM '+table+' WHERE id=?',(key,)).fetchone()
 if prior is not None:need(strict(prior[0].encode())==value,'DISK_APPEND_RECEIPT_CONFLICT');return False
 db.execute('INSERT INTO '+table+' VALUES(?,?)',(key,wire(value).decode()));return True

def enqueue_after_partial(q,j,maximum):
 """Only a fresh next attempt. Original claims, native requests stay untouched."""
 attempt=j.get('attempt',1)
 if attempt>=maximum:return None
 nxt=attempt+1;need(2<=nxt<=4,'DISK_ATTEMPT_LIMIT')
 table='replacement_jobs'if nxt<4 else 'aux_stall_exempt_replacement_jobs'
 new=digest({'point':j['point'],'replicate':j['replicate'],'attempt':nxt})
 with q.tx():
  need(q.db.execute('SELECT 1 FROM replicate_partials WHERE job_id=?',(j['id'],)).fetchone()is not None,'DISK_PARTIAL_BEFORE_NEW_ATTEMPT')
  old=q.db.execute('SELECT * FROM '+table+' WHERE id=?',(new,)).fetchone()
  if old is None:
   q.db.execute('INSERT INTO '+table+" VALUES(?,?,?,'QUEUED',NULL,NULL,NULL,NULL,?,?)",(new,j['point'],j['replicate'],nxt,j.get('original_job',j['id'])))
   q.event('ONE_REPLICATE_REPLACEMENT_ENQUEUED',{'job_id':new,'failed_job_id':j['id'],'point_id':j['point'],'replicate_id':j['replicate'],'attempt':nxt,'rng_policy_sha256':digest(A.RNG_POLICY),'new_requests_required':True,'billing_domain':'AUX_FINALIZATION','search_budget_delta':0,'policy':A.POLICY})
  else:need(old['point']==j['point']and old['replicate']==j['replicate']and old['attempt']==nxt and old['original_job']==j.get('original_job',j['id']),'DISK_EXACT_EXISTING_REPLACEMENT')
 return new

class HistoricalRecords:
 def __init__(self,dispatch,metadata):self.d=dispatch;self.metadata=metadata
 def load(self):
  d=self.d;q=d.queue
  with q.mutex:jobs=A.effective_rows(q)
  for j in jobs:
   meta=self.metadata[j['id']]['artifacts'];path=Path(meta['config']['path'])
   point=d.points.setdefault(j['point'],{'aux':d.point_base(j['point']),'jobs':[],'audited':False})
   if j['state']=='QUEUED':continue
   point['jobs'].append(j['id'])
   need(meta['config']['exists']and hash_file(path)['sha256']==meta['config']['sha256'],'DISK_PINNED_EXISTING_CHILD_CONFIGURATION')
   c=strict(path.read_bytes());need(c['trajectory']==j['trajectory']and c['k']==j['replicate']and c['input_root']==j['input_root']and c['input_policy_sha256']==j['input_policy']and digest(c['manifest'])==q.manifest,'DISK_OLD_CONFIG_SAME_CLAIM_INPUTS')
   r={'job':copy.deepcopy(j),'child':None,'config':c,'path':path,'scope':c['scope'],'terminal':None,'historical':True}
   # Overlay PARTIAL preserves raw original state; no fabricated wait handle.
   raw=q._job(j['id'])
   if raw['state']in('CHILD_EXITED_HOLD','COMPLETE'):r['terminal']=durable_wait(q,raw);r['wait_custodian']='ORIGINAL_PARENT_DURABLE_RECEIPT'
   elif raw['state']=='RUNNING':need(raw['terminal']is None,'DISK_ORPHAN_NO_TERMINAL_BACKFILL');r['orphan']=strict(raw['child'].encode())
   else:need(False,'DISK_NONRECONSTRUCTABLE_OLD_CLAIM_LOCAL_HOLD')
   if j['state']=='PARTIAL':r['partial']=True
   d.children[j['id']]=r
  for point,p in d.points.items():
   rows=[j for j in jobs if j['point']==point]
   p['audited']=len(rows)==3 and all(j['state']=='COMPLETE'for j in rows)
   if p['audited']:need((p['aux']/'K3_AUDIT.json').is_file(),'DISK_COMPLETED_POINT_ORIGINAL_AUDIT_REQUIRED')
  return {'old_wait_receipts':sum(r['terminal']is not None for r in d.children.values()),'orphan_claims':sum('orphan'in r for r in d.children.values()),'complete_points_preserved':sum(p['audited']for p in d.points.values())}

class FinalOnlyDispatcher(NativeFinalDispatcher):
 def __init__(self,ledger,queue,capacity,server,*,directory,configuration,python_command,environment,entry,entry_sha256,point_base):
  # Existing dispatch directory is permitted ONLY with the exclusive existing
  # ledger/queue locks; old config/stdout/stderr are never overwritten.
  from budget import Ledger
  from final_queue import FinalQueue
  from model_capacity import ModelCapacity
  from final_host_rpc import HostServer
  need(type(ledger)is Ledger and type(queue)is FinalQueue and type(capacity)is ModelCapacity and capacity.ledger is ledger and type(server)is HostServer and server.capacity is capacity,'DISK_ORIGINAL_SHARED_NATIVE_PORTS')
  self.ledger,self.queue,self.capacity,self.server=ledger,queue,capacity,server
  self.root=private_dir(directory);self.configuration=configuration;self.command=tuple(python_command);self.environment=dict(environment)
  self.children={};self.points={};self.faulted=False;self.lock=threading.RLock();self.held_points={};self.point_base=point_base
  self.entry=Path(entry);self.entry_pin=hash_file(self.entry);need(self.entry_pin['sha256']==entry_sha256,'DISK_ORIGINAL_FINAL_ENTRY_PIN')
 def _fault(self,trajectory,kind):
  # A local FINAL error never touches owner or peer model admission.
  with self.ledger.tx():self.ledger.event(trajectory,kind,{'point_local':True,'requests_replayed':0,'owner_global_fault':False})
 def dispatch_one(self):
  before=set(self.children)
  try:return super().dispatch_one()
  except BaseException as e:
   for k in set(self.children)-before:
    r=self.children[k];self.held_points[r['job']['point']]=type(e).__name__
   raise
 def poll_record(self,key,r):
  if r.get('partial'):return
  j=r['job'];child=r.get('child')
  if child is not None and r['terminal']is None:
   r['terminal']=self.queue.reap(key,j['claim'],child)
  if r['terminal']is None:return
  t=r['terminal']
  if t['exit_code']!=0 or t['signal']is not None:
   self.dispose_failed(r);return
  with self.ledger.mutex:
   n=self.ledger.db.execute("SELECT COUNT(*)FROM aux_permits WHERE scope=? AND state IN('RESERVED','SENT','UNKNOWN')",(r['scope'],)).fetchone()[0]
  need(n==0,'DISK_SUCCESSFUL_HOLD_UNRESOLVED_PHYSICAL_CUSTODY')
 def audit_point(self,p):
  if p['audited']:return
  # Native selection, K3 audit, evaluator custody and result fingerprints intact.
  rows=R.selected(self,p)
  if rows is None:return
  from v21_inputs import verify_input
  from r16_natural_contract import natural,label
  from native_k3 import audit_three
  rows.sort(key=lambda r:r['job']['replicate']);c=rows[0]['config'];j=rows[0]['job'];aux=p['aux']
  ip=verify_input(j['input_root'],expected_policy_sha=j['input_policy'],trajectory=j['trajectory'],setting=j['setting']);nm=natural(ip)
  runs=R.paths(rows,label(j['target'],nm),j['setting'])
  audit=audit_three(aux,runs,trajectory=j['trajectory'],setting=j['setting'],target_tokens=j['target'],source_sha256=c['manifest']['protocol']['source_bundle'],protocol_sha256=c['manifest']['protocol']['final_v21'],input_policy_sha256=j['input_policy'],natural_stop=nm)
  out=aux/'K3_AUDIT.json'
  if out.exists():need(strict(out.read_bytes())==audit,'DISK_EXISTING_AUDIT_NOT_REPLACED')
  else:publish(out,wire(audit))
  for r,run in zip(rows,runs):
   raw=self.queue._job(r['job']['id']);result=hash_file(run['aggregate'])['sha256']
   if raw['state']=='COMPLETE':need(raw['result']==result,'DISK_PRIOR_COMPLETION_SAME_RESULT');continue
   self.queue.complete(raw['id'],raw['claim'],result_sha256=result,verified_native_audit={'job_id':raw['id'],'result_sha256':result,'complete':True,'unresolved_physical_custody':0,'original_k3_audit_sha256':digest(audit)})
  p['audited']=True
 def poll(self):
  events=[]
  # Independent point fault domains. No owner-wide FAULT, no peer shutdown.
  for key,r in list(self.children.items()):
   try:self.poll_record(key,r)
   except BaseException as e:
    self.held_points[r['job']['point']]=type(e).__name__;events.append({'job_id':key,'exception_type':type(e).__name__})
    if hasattr(self,'on_error'):self.on_error(r['job']['point'],e)
  for key,p in self.points.items():
   try:self.audit_point(p)
   except BaseException as e:self.held_points[key]=type(e).__name__;events.append({'point_id':key,'exception_type':type(e).__name__})
  return {'status':self.status(),'local_holds':events}
