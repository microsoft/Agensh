"""One shared actual FINAL Popen cap and original shared physical FP8 cap.

Historical genuine wait receipt excludes a HOLD from concurrency, not from
its immutable audit. Unresolved old physical model permits still consume96.
"""
from types import MethodType
from common import need,digest,strict
import final_attempts as A
from durable_final import durable_wait

class Slots:
 def __init__(self,dispatchers,cap=3):
  need(type(cap)is int and cap==3,'DISK_FINAL_CAP3');self.ds=tuple(dispatchers);self.cap=cap
  lock=self.ds[0].queue.mutex
  for d in self.ds:d.queue.mutex=lock
 def active(self):
  count=0
  for d in self.ds:
   for j in A.live_rows(d.queue):
    if j['state']=='CHILD_EXITED_HOLD':durable_wait(d.queue,j)
    elif j['state']in('CLAIMED','RUNNING','CUSTODY_UNKNOWN'):count+=1
  return count
 def candidate(self,q):
  rows=A.live_rows(q)
  need(not any(j['state']=='CUSTODY_UNKNOWN'for j in rows),'FINAL_QUEUE_UNKNOWN_NO_NEW_LAUNCH')
  if self.active()>=self.cap:return None
  d=next(x for x in self.ds if x.queue is q)
  return next((j for j in rows if j['state']=='QUEUED'and j['point']not in d.held_points),None)
 def install(self):
  import final_queue
  final_queue._claim_candidate=self.candidate
  return self

def local_pause(d):
 c=d.capacity
 def pause(_,scope,metadata):
  # All original public metadata field/identity validation still runs, but
  # isolate AUX point rather than poisoning SEARCH/peer publishers.
  allowed={'http_status','error_type','timeout','setting','role','request_id','charged_tokens','classification','finalization'}
  need(type(metadata)is dict and set(metadata)<=allowed,'CAPACITY_INCIDENT_METADATA_ONLY')
  from common import ident,integer
  if 'error_type'in metadata:ident(metadata['error_type'])
  if 'request_id'in metadata:ident(metadata['request_id'])
  if 'http_status'in metadata:need(metadata['http_status']is None or type(metadata['http_status'])is int and 100<=metadata['http_status']<=599,'CAPACITY_INCIDENT_HTTP')
  if 'charged_tokens'in metadata:integer(metadata['charged_tokens'],'CAPACITY_INCIDENT_TOKENS')
  for k in('timeout','finalization'):
   if k in metadata:need(type(metadata[k])is bool,'CAPACITY_INCIDENT_BOOL')
  if 'classification'in metadata:need(metadata['classification']in('REJECTED_PREGEN','RETRYABLE_REJECTED','UNKNOWN_CHARGED'),'CAPACITY_INCIDENT_CLASSIFICATION')
  if 'setting'in metadata:need(metadata['setting']in('Agensh-16','Agensh-1'),'CAPACITY_INCIDENT_SETTING')
  if 'role'in metadata:need(metadata['role']=='single','CAPACITY_INCIDENT_ROLE')
  with d.ledger.tx():
   owner=c._scope(scope)
   r=next(r for r in d.children.values()if r.get('scope')==scope);point=r['job']['point']
   d.held_points[point]='AUX_INCIDENT_PENDING_PHYSICAL_TERMINAL'
   d.ledger.event(owner['trajectory'],'DISK_FINAL_POINT_LOCAL_INCIDENT',{'scope':scope,'point_id':point,'metadata':metadata,'global_hold':False})
  return True
 c.pause=MethodType(pause,c)
 acquire,sent=c.acquire,c.sent
 def guard(scope):
  c._scope(scope)
  r=next(r for r in d.children.values()if r.get('scope')==scope)
  need(r['job']['point']not in d.held_points,'DISK_AUX_POINT_ISOLATED_NO_NEW_SEND')
 def take(_,scope,permit):guard(scope);return acquire(scope,permit)
 def send(_,scope,permit,request):c._permit(scope,permit);guard(scope);return sent(scope,permit,request)
 c.acquire=MethodType(take,c);c.sent=MethodType(send,c)

def point_unknown_tail(d,point):
 """All attempts, not just this process's Popen records. Metadata only."""
 scopes=set();l=d.ledger
 with l.mutex:
  for scope,raw in l.db.execute('SELECT scope,binding FROM aux_scopes'):
   b=strict(raw.encode());key={'trajectory':b.get('trajectory'),'target':b.get('target_tokens')}
   if b.get('point_kind')=='NATURAL_STOP':key.update(point_kind='NATURAL_STOP',policy_sha256=b['natural_stop']['policy_sha256'])
   if digest(key)==point:scopes.add(scope)
  exists=l.db.execute("SELECT 1 FROM sqlite_master WHERE name='aux_unknown_reservation_charges'").fetchone()
  charged=set()if not exists else{strict(r[0].encode())['request_id']for r in l.db.execute('SELECT metadata FROM aux_unknown_reservation_charges')}
  tail=0
  for raw, in l.db.execute("SELECT metadata FROM events WHERE kind='AUX_MODEL_SENT' ORDER BY seq"):
   e=strict(raw.encode())
   if e['scope']not in scopes:continue
   permit=l.db.execute('SELECT state FROM aux_permits WHERE id=?',(e['permit_id'],)).fetchone()
   if e['request_id']in charged:tail+=1
   elif permit is not None and permit[0]=='TERMINAL':tail=0
  return tail

def global_recent_unknown_ratio(dispatchers,*,started_ns,now_ns):
 """Authorized ten-minute 5xx/UNKNOWN threshold, only new custodian epoch."""
 since=max(started_ns,now_ns-600*10**9);sent=0;bad=set()
 for d in dispatchers:
  with d.ledger.mutex:
   sent+=d.ledger.db.execute("SELECT COUNT(*)FROM events WHERE kind='AUX_MODEL_SENT' AND at_ns>=?",(since,)).fetchone()[0]
   for raw, in d.ledger.db.execute("SELECT metadata FROM events WHERE kind='DISK_FINAL_POINT_LOCAL_INCIDENT' AND at_ns>=?",(since,)):
    e=strict(raw.encode());m=e['metadata'];status=m.get('http_status')
    if status in(429,503):continue
    if m.get('classification')=='UNKNOWN_CHARGED'or type(status)is int and 500<=status<=599:bad.add((id(d.ledger),m.get('request_id')))
 return {'sent':sent,'5xx_or_unknown':len(bad),'window_seconds':600,'ratio':len(bad)/sent if sent else None,'stop':bool(sent and len(bad)/sent>.2)}
