"""Final fault scope gate, including already cached original bound methods.

No network/credential/Gitea/ledger/UNKNOWN guard is disabled. Local component
failures retain their own latch and handles. Only actual relay/financial stops
can execute the old all-six seal. This is not a request/recovery retry layer.
"""
from types import FunctionType
import threading
from common import need
import trajectory_isolation as I

FINANCIAL_PREFIXES=('SEARCH_','UPSTREAM_','LOCAL_PROMPT_','ACCOUNTED_','UPPER_BOUND_',
 'RELAY_','SCIENTIFIC_CONTINUATION_STORAGE_','UNCLEAN_OWNER_')
FINANCIAL_CODES=frozenset({'SCIENTIFIC_HTTP_LIFECYCLE_STORAGE_UNKNOWN',
 'SCIENTIFIC_HTTP_LISTENER_UNKNOWN','SCIENTIFIC_HTTP_START_FAILED_RETAIN',
 'SCIENTIFIC_HTTP_BIND_STORAGE_FAILURE','SCIENTIFIC_HTTP_FINISH_STORAGE_FAILURE',
 'SCIENTIFIC_HTTP_REQUEST_BINDING_UNKNOWN','SCIENTIFIC_HTTP_KEEPALIVE_CUSTODY_UNKNOWN',
 'SCIENTIFIC_HTTP_KEEPALIVE_START_UNKNOWN','SCIENTIFIC_HTTP_REJECTION_METADATA_UNKNOWN'})

def evidence(l):
 """Fixed metadata only; never exception messages, response bodies or stacks."""
 peer=getattr(l,'_aggregate_capacity_peer',None)
 with l.mutex:
  for own in(peer.ledgers if peer is not None else (l,)):
   domain='main'if own is l else 'branch'
   row=own.db.execute('SELECT paused,reason FROM model_control WHERE singleton=1').fetchone()
   initial=(peer is not None and own is peer.branch and row is not None
            and row['reason']=='NEW_CURRENT_OWNER_REQUIRES_RELEASE')
   if row and row['paused']and not initial:
    return {'scope':'relay-or-billing','domain':domain,'proof':'MODEL_CONTROL_PAUSED'}
   if own.db.execute('SELECT 1 FROM unknown_stops LIMIT 1').fetchone():
    return {'scope':'relay-or-billing','domain':domain,'proof':'UNKNOWN_STOP_THRESHOLD'}
   if own.db.execute("SELECT 1 FROM accounts WHERE state='FAULT' LIMIT 1").fetchone():
    return {'scope':'relay-or-billing','domain':domain,'proof':'FAULTED_ACCOUNT'}
   for t,code in own.memory_faults.items():
    if code.startswith(FINANCIAL_PREFIXES)or code in FINANCIAL_CODES:
     return {'scope':'relay-or-billing','domain':domain,'proof':'RELAY_OR_FINANCIAL_LATCH','trajectory':t,'code':code}
 return None

def global_reason(l):
 p=evidence(l)
 return None if p is None else p['proof']

def _trampoline(self,trajectory):
 # A code-object replacement is intentional: changing an attribute alone does
 # not intercept bound original methods captured before isolation was installed.
 return _A4_FINAL_FAULT_GATE(self,trajectory)

class FinalGate:
 def __init__(self,driver):
  self.driver=driver;self.lock=threading.RLock();self.counts={};self.original=None
 def enter(self,driver,t):
  need(driver is self.driver,'A4_FINAL_GATE_SAME_DRIVER')
  l=driver.ledger
  with self.lock,l.mutex:
   p=evidence(l);key=('GLOBAL'if p else 'LOCAL',t)
   n=self.counts.get(key,0)+1;self.counts[key]=n
   # Repeated local control errors cannot create an unbounded event storm.
   try:
    if n==1 or n%120==0 or p is not None:
     with l.tx():l.event(t,'A4_FINAL_FAULT_SCOPE_DECISION',{
       'entry':'ORIGINAL_CLASS_FAULT_INCLUDING_CACHED_METHODS','count':n,
       'global_admission_sealed':p is not None,'relay_financial_evidence':p,
       'local_scope':'trajectory'if t in driver.rows else 'owner-control-component',
       'requests_replayed':0,'messages_locals_stacks_omitted':True})
   except BaseException:
    # Failed diagnostic storage cannot suppress the pre-existing financial stop.
    if p is not None:self.original(driver,t)
    raise
   if p is not None:return self.original(driver,t)
   if t in driver.rows:
    driver._isolation.trajectories.add(t)
    l.latch_fault(t,'SCIENTIFIC6_DRIVER_FAILURE_RETAINED_NO_RETRY')
   # Never latch GLOBAL for an owner-control/point failure. It would itself
   # poison admission_fault() for all six even with driver.failed left false.
   return None
 def install(self):
  d=self.driver;f=type(d)._fault
  need(not hasattr(d,'_a4_final_fault_gate')and f.__closure__ is None
       and f.__name__=='_fault'and f.__code__.co_argcount==2,
       'A4_FINAL_GATE_ORIGINAL_PYTHON_METHOD_ONCE')
  self.function=f;self.old_code=f.__code__;self.old_global=f.__globals__.get('_A4_FINAL_FAULT_GATE')
  need(self.old_global is None,'A4_FINAL_GATE_NEW_FIXED_GLOBAL')
  self.original=FunctionType(f.__code__,f.__globals__,f.__name__,f.__defaults__,f.__closure__)
  f.__globals__['_A4_FINAL_FAULT_GATE']=self.enter
  # Preserves function identity; cached MethodType/function aliases all see it.
  f.__code__=_trampoline.__code__
  d._a4_final_fault_gate=self
  return self
 def restore_for_own_test_only(self):
  self.function.__code__=self.old_code
  self.function.__globals__.pop('_A4_FINAL_FAULT_GATE',None)
  del self.driver._a4_final_fault_gate
