"""Developer packaging only. Fixed public framework closure, no experiment IO."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent
B=HERE.parent
LEAVES={
 'expansion-100m-v1':('expansion100_contract.py','expansion100_quota.py','build_expansion_runtime.py','build_x48_host.py','BASELINE_PINS.json','HOST_RENDERER_PINS.json'),
 'continuation100-native-v1':('disk_clock.py','disk_search_policy.py'),
 'continuation100-dependency-v3':('a4_final_fault_gate.py','trajectory_isolation.py'),
 'a4-upstream-rejected-v2':('rejection_ledger.py','rejection_transport.py'),
 'a4-disk-final-custodian-v1':('disk_capacity.py','durable_final.py','durable_cost.py','disk_control.py'),
 'a4-glm-session-header-v1':('glm_session_header.py',),
 'a4-health-window20-v4':('health_window20.py',),
 'a4-aux-timeout900-v1':('aux_timeout.py','aux_allowance.py'),
 'aux-unknown-replacement-v1':('aux_unknown_replacement.py',),
 'aux-metadata-rpc-wait-v2':('metadata_rpc_wait.py',),
 'fork-manager-isolation-v1':('aggregate_manager_isolation.py',),
 'fork-final-claim-nonblocking-v1':('fork_final_claim_nonblocking.py',),
 'a4-branch-projection-repair-v1':('branch_projection_repair.py',),
 'a4-private-db-repair-v1':('private_db_repair.py',),
 'late-aggregate-fork-v1':('aggregate_agent.py','aggregate_capacity.py','aggregate_final.py','aggregate_final_binding.py',
   'aggregate_install.py','aggregate_phase.py','aggregate_projection.py','aggregate_prompt.py','aggregate_source.py','run_aggregate_final_child.py','pilot-campaign.py'),
}

def build(destination):
 dest=Path(destination);assert not dest.exists()and not dest.is_symlink();dest.mkdir(mode=0o700)
 pins={}
 for folder,names in LEAVES.items():
  for name in names:
   assert name not in pins,'DUPLICATE_FLAT_MODULE'
   p=B/folder/name;assert p.is_file()and not p.is_symlink();raw=p.read_bytes()
   if name.endswith('.py'):compile(raw,name,'exec')
   out=dest/name;out.write_bytes(raw);out.chmod(0o600)
   pins[name]={'source_relative':str(p.relative_to(B)),'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
 (dest/'PUBLIC_DEPENDENCY_CLOSURE.json').write_text(json.dumps(pins,sort_keys=True,indent=2)+'\n')
 return pins
if __name__=='__main__':
 import sys
 print(json.dumps({'public_modules':len(build(sys.argv[1])),'models':0}))
