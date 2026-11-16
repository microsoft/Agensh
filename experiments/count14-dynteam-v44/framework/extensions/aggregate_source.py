"""Tiny16M cut handoff, metadata-only and independent of branch readiness.

OPS's diagnostic target calls save(owner) at COMMITTED, then invokes its ORIGINAL
stage release. This function never starts branch work, queues K3 or changes the
main ledger. The immutable record remains usable after owner.ref moves to20M.
"""
from pathlib import Path
import copy
from common import need,digest,wire,publish,strict
NAME='FORK_SOURCE_16M.json'
SCHEMA='agensh-v2-16m-fork-source-v1'
def validate(cas,source,*,parent=None,manifest_sha=None):
 need(type(source)is dict and set(source)=={'schema','parent_trajectory','snapshot','expected','git_exports','registered_refs','member_cap','setting','mainline_release_required','K_at16'},'FORK_SOURCE_FIELDS')
 need(source['schema']==SCHEMA and source['mainline_release_required']is True and source['K_at16']==0,'FORK_SOURCE_DIAGNOSTIC_ONLY')
 d=cas.verify_snapshot(source['snapshot'],expected=source['expected'])
 need(d['target_tokens']==16_000_000 and d['trajectory']==source['parent_trajectory'],'FORK_SOURCE_SEALED16M')
 need(not any(d[k]for k in('reserved','unresolved','active_operations')),'FORK_SOURCE_NO_PENDING_SEARCH')
 if parent is not None:need(source['parent_trajectory']==parent,'FORK_SOURCE_PARENT')
 if manifest_sha is not None:need(d['pins']['manifest']==manifest_sha,'FORK_SOURCE_MANIFEST')
 need(d['pins']['gitea_exports']==digest({'registered_refs':source['registered_refs'],'exports':source['git_exports']}),'FORK_SOURCE_EXPORTS_BOUND_TO_SNAPSHOT')
 need(source['setting']=='Agensh-'+str(len(d['roles'])),'FORK_SOURCE_ROSTER')
 return d

def save(owner):
 with owner.lock:
  need(owner.state=='COMMITTED'and owner.cut is not None and owner.cut.cut['target_tokens']==16_000_000,'FORK_SOURCE_SAVE_AT_COMMITTED16M_ONLY')
  source={'schema':SCHEMA,'parent_trajectory':owner.t,'snapshot':copy.deepcopy(owner.ref),'expected':copy.deepcopy(owner.ledger.frontier(owner.t)),
   'git_exports':copy.deepcopy(owner.exports),'registered_refs':list(owner.refs),'member_cap':owner.member_cap,'setting':owner.setting,'mainline_release_required':True,'K_at16':0}
  validate(owner.cas,source,parent=owner.t)
  path=owner.root/NAME
  if path.exists():need(strict(path.read_bytes())==source,'FORK_SOURCE_IMMUTABLE_NO_REPLACE')
  else:publish(path,wire(source),mode=0o400)
  return source

def read(cas,path,**expected):
 source=strict(Path(path).read_bytes());validate(cas,source,**expected);return source
