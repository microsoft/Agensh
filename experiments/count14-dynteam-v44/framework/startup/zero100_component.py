"""OWN zero-model native cut/release wiring. NOT a real host-launcher rehearsal.

Uses the original fake native SDK fixture, real model relay/gate/SQLite/CAS/K3
queue implementations, and explicit synthetic kernel domains. Zero GLM/Docker.
"""
from pathlib import Path
import json,os,sys
from common import wire,publish,digest
from test_native_scientific_owner import ScientificOwnerCompositionTests
from test_scientific_relay import req

def run():
 f=ScientificOwnerCompositionTests('runTest');f.setUp()
 try:
  c=f.start();native={str(k):dict(v.process_identity)for k,v in f.team.sessions.items()}
  # OWN fixture only. Production uses guarded append authorization, never this.
  f.l.db.execute('UPDATE accounts SET targets=? WHERE trajectory=?',(wire([10_000_000,20_000_000,50_000_000,100_000_000]).decode(),f.team.t))
  snapshots=[]
  for target in(10_000_000,20_000_000,50_000_000,100_000_000):
   assert f.l.frontier(f.team.t)['target']==target
   f.e.run(req(),(f.team.t,'worker-00'));f.commit_queue()
   snapshots.append(f.cas.verify_snapshot(c.ref)['target_tokens'])
   if target!=100_000_000:f.release()
  assert c.step()['owner_state']=='FINAL_PARKED'
  assert f.queue.frontier()=={'QUEUED':12}
  assert native=={str(k):dict(v.process_identity)for k,v in f.team.sessions.items()}
  assert len(f.sent)==4
  return {'schema':'agensh-v2-100m-own-component-zero-model-v1','result':'PASS',
   'regular_snapshot_targets':snapshots,'K3_jobs_queued':12,'synthetic_upstream_requests':len(f.sent),
   'same_native_process_identities':True,'same_session_and_ledger_objects':True,
   'kernel_domains':'explicit-original-synthetic-fixture','real_models':0,'real_Docker':0,
   'whole_launcher_rehearsal':False,'production_resumed':False}
 finally:f.tearDown()
if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
