"""One host mutex for two FINANCIALLY INDEPENDENT ledgers.

Only admission counters/condition are shared, never account rows, charges, usage,
requests, owner locks or connections. Main scientific completion remains local.
All real main SEARCH/AUX and branch SEARCH/AUX keep physical UNKNOWN slots.
Attach while holding the existing writer mutex, before branch work is possible.
"""
import functools, threading
from common import need

class CapacityPeer:
 def __init__(self,main,branch,*,search_cap=80,global_cap=96,hold=None):
  need(main is not branch and main.home!=branch.home,'BRANCH_SEPARATE_LEDGER_REQUIRED')
  need(not hasattr(main,'_aggregate_capacity_peer'),'BRANCH_CAPACITY_ATTACH_ONCE')
  self.main=main;self.branch=branch;self.search_cap=search_cap;self.global_cap=global_cap;self.hold=hold or (lambda:False)
  need(1<=search_cap<=global_cap<=96,'BRANCH_SHARED_CAPS')
  self.ledgers=(main,branch);self.raw={};self.gates=set()
  with main.capacity_changed:
   # The brand new branch has no background activity yet. It uses its OWN DB
   # and flock. The common lock serializes both reservation boundaries.
   branch.mutex=main.mutex;branch.capacity_changed=main.capacity_changed
   self.condition=main.capacity_changed
   for l in self.ledgers:
    self.raw[l]={'global_unresolved':l.global_unresolved,'global_logical_unresolved':l.global_logical_unresolved,'unknown_statistics':l.unknown_statistics,'admission_fault':l.admission_fault,'model_paused':l.model_paused}
   for l in self.ledgers:
    l.global_unresolved=self.physical
    l.unknown_statistics=self.statistics_for(l)
    l.admission_fault=self.fault_for(l)
    # Closure MUST NOT wait for the other experiment to finish; physical
    # capacity above remains shared, and is not closure evidence.
    raw=self.raw[l]['global_unresolved']
    def logical(l=l,raw=raw):
     with self.condition:return raw()-l.db.execute('SELECT COUNT(*) FROM unknown_charges').fetchone()[0]
    l.global_logical_unresolved=logical
    l._aggregate_capacity_peer=self
   def main_paused():
    if self.hold() or self.raw[main]['model_paused']():return True
    row=branch.db.execute('SELECT paused,reason FROM model_control WHERE singleton=1').fetchone()
    # A new branch owner starts held before fresh admission: that local hold
    # must NOT stop mainline. A real FINAL incident is still a global stop.
    return bool(row and row[0] and row[1]!='NEW_CURRENT_OWNER_REQUIRES_RELEASE')
   main.model_paused=main_paused
   branch.model_paused=lambda:self.hold() or self.raw[branch]['model_paused']() or self.raw[main]['model_paused']()
 def physical(self):
  with self.condition:return sum(self.raw[l]['global_unresolved']()for l in self.ledgers)
 def search(self):
  with self.condition:return sum(l.db.execute("SELECT COUNT(*) FROM requests WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0]for l in self.ledgers)
 def statistics_for(self,l):
  def statistics(t):
   with self.condition:
    own=self.raw[l]['unknown_statistics'](t);other=self.branch if l is self.main else self.main
    both=self.raw[other]['unknown_statistics']('__aggregate_capacity_metadata_only__')
    return {**own,'sent_requests':own['sent_requests']+both['sent_requests'],'unknown_requests':own['unknown_requests']+both['unknown_requests']}
  return statistics
 def fault_for(self,l):
  def fault(t):
   with self.condition:
    own=self.raw[l]['admission_fault'](t)
    if own:return own
    # A peer's GLOBAL UNKNOWN ratio stop is global. Its per-trajectory fault
    # does not poison unrelated main trajectories.
    other=self.branch if l is self.main else self.main
    r=other.db.execute("SELECT code FROM unknown_stops WHERE scope='GLOBAL' ORDER BY event_seq LIMIT 1").fetchone()
    return None if r is None else r[0]
  return fault
 def bind_gate(self,gate):
  need(gate.ledger in self.ledgers and gate.global_cap==self.global_cap,'BRANCH_GATE_CAPACITY_BINDING')
  if gate in self.gates:return
  original=gate.reserve;peer=self
  @functools.wraps(original)
  def reserve(*args,**kwargs):
   guard=kwargs.get('admission_guard')
   def admission():
    # Composed with the ORIGINAL HTTP/identity/custody guard; never replaces it.
    while True:
     if guard is not None:guard()
     need(not gate.closed,'ADMISSION_GATE_SHUTDOWN_NO_SEND')
     if peer.search()<peer.search_cap:return
     peer.condition.wait(timeout=.25)
   kwargs['admission_guard']=admission
   return original(*args,**kwargs)
  with self.condition:gate.reserve=reserve;self.gates.add(gate)

def share_final_slots(main,branch,*,cap=12):
 """Existing queues retain their OWN immutable jobs/claims; at most12 combined.
 No job identity collision: distinct branch manifest/trajectory namespace.
 """
 need(main is not branch and main.home!=branch.home and 1<=cap<=12,'BRANCH_FINAL_QUEUE_SEPARATE')
 lock=main.mutex
 with lock:
  branch.mutex=lock
  for q in (main,branch):
   original=q.claim
   def claim(original=original):
    import final_attempts as attempts
    from final_queue import ACTIVE
    with lock:
     count=sum(sum(r['state']in ACTIVE for r in attempts.live_rows(x))for x in(main,branch))
     if count>=cap:return None
     return original()
   q.claim=claim
 return {'global_final_subtask_cap':cap,'financial_queues_separate':True}
