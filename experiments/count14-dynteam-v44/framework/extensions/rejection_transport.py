"""Retry only explicit upstream HTTP429/503 before any response stream.

Same request object, bytes, original session, reservation and RNG. Timeouts,
HTTPother, post-header/stream/usage errors never enter this retry path.
"""
import time,threading,urllib.error
from types import MethodType
from common import need,strict
from feasibility_relay import Rejected
CODES={429:'UPSTREAM_EXPLICIT_REJECTED_429',503:'UPSTREAM_EXPLICIT_REJECTED_503'}

class Monitor:
 def __init__(self,ledgers):self.ledgers=tuple(ledgers);self.lock=threading.RLock();self.last={}
 def record(self,l,meta,attempt,status):
  row={'request_id':meta['request_id'],'attempt':attempt,'http_status':status,'window_seconds':600,'response_content_logged':False}
  with l.tx():l.event(meta['trajectory'],'UPSTREAM_HTTP_ATTEMPT',row)
  with self.lock:self.last[meta['request_id']]=dict(row)
 def ratio(self,now_ns=None):
  lower=(time.time_ns()if now_ns is None else now_ns)-600*10**9;sent=set();attempts={};old429=set()
  for l in self.ledgers:
   with l.mutex:
    for row in l.db.execute("SELECT kind,metadata FROM events WHERE at_ns>=?AND kind IN('SENT','UNKNOWN_EXECUTION','UPSTREAM_HTTP_ATTEMPT')",(lower,)):
     kind,m=row[0],strict(row[1].encode());rid=m['request_id'];key=(id(l),rid)
     if kind=='SENT':sent.add(key)
     elif kind=='UNKNOWN_EXECUTION'and m.get('code')=='UPSTREAM_HTTP_429':old429.add(key)
     elif kind=='UPSTREAM_HTTP_ATTEMPT':attempts.setdefault(key,[]).append(m)
  # Include new retry attempts as physical provider calls, not SEARCH requests.
  total=len(sent|set(attempts))+sum(max(0,len(v)-1)for v in attempts.values())
  rejected=sum(r['http_status']==429 for v in attempts.values()for r in v)+len(old429-set(attempts))
  return {'window_seconds':600,'provider_attempts':total,'http429':rejected,'stop':total>0 and rejected*2>total}

class RetryOpener:
 def __init__(self,original,ledger,metadata,monitor,*,sleep=time.sleep):
  self.original=original;self.ledger=ledger;self.metadata=metadata;self.monitor=monitor;self.sleep=sleep
 def open(self,request,*args,**kwargs):
  meta=self.metadata()
  for attempt in range(1,7):
   try:response=self.original.open(request,*args,**kwargs)
   except urllib.error.HTTPError as e:
    status=e.code
    if status not in CODES:raise # original caller retains error classification
    e.close();self.monitor.record(self.ledger,meta,attempt,status)
    ratio=self.monitor.ratio()
    if status==429 and ratio['stop']:
     with self.ledger.tx():
      self.ledger.event('GLOBAL','UPSTREAM_HTTP429_RATIO_STOP',ratio)
      self.ledger.db.execute("UPDATE model_control SET paused=1,epoch=epoch+1,reason='UPSTREAM_HTTP429_RATIO_GT50_STOP'WHERE singleton=1")
     self.ledger.latch_fault('GLOBAL','UPSTREAM_HTTP429_RATIO_GT50_STOP')
     raise Rejected(CODES[status]+'_GLOBAL_RATIO_STOP',429)from None
    if attempt==6:raise Rejected(CODES[status],status)from None
    delay=min(300,10*2**(attempt-1))
    with self.ledger.tx():self.ledger.event(meta['trajectory'],'UPSTREAM_REJECTION_BACKOFF',{'request_id':meta['request_id'],'http_status':status,'attempt':attempt,'sleep_seconds':delay,'same_reservation_and_session':True})
    self.sleep(delay)
    if self.ledger.model_paused():raise Rejected(CODES[status],status)from None
   else:
    self.monitor.record(self.ledger,meta,attempt,response.status);return response

def install(engine,overlay,monitor):
 from rejection_ledger import reject
 need(not isinstance(overlay.original,RetryOpener),'UPSTREAM_REJECTION_RETRY_ONCE')
 usage=engine.ledger;l=usage.ledger;original=usage.record
 def record(_,rid,identity,kind,request_sha,*,response=None,usage=None,code=None):
  statuses={**{v:k for k,v in CODES.items()},CODES[429]+'_GLOBAL_RATIO_STOP':429}
  if usage is None and kind=='UNKNOWN'and code in statuses:
   with monitor.lock:proof=dict(monitor.last[rid])
   need(proof['http_status']==statuses[code]and proof['request_id']==rid,'UPSTREAM_REJECTION_RUNTIME_RESPONSE_PROOF')
   try:return reject(l,rid,statuses[code],{'kind':'RUNTIME_EXPLICIT_HTTP_RESPONSE',**proof})
   finally:
    if _.admission_gate is not None:_.admission_gate.notify()
  return original(rid,identity,kind,request_sha,response=response,usage=usage,code=code)
 usage.record=MethodType(record,usage)
 overlay.original=RetryOpener(overlay.original,l,overlay.metadata,monitor)
