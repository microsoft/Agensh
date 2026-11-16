"""New branch-only FINAL RNG domain, original binding/verification unchanged.

Both trusted parent and child install this wrapper. Every original manifest seed
remains the paired pilot seed. Only this explicitly tagged new FINAL branch
uses a deterministic derived RNG seed; mainline requests are byte-unchanged.
"""
import functools
from common import need,digest
from scientific_profile import action_seed
DOMAIN='AGENSH_V2_FORK16_AGGREGATE4_FINAL_V1'
def seed(original_seed,source_sha,trajectory):
 key=[DOMAIN,original_seed,source_sha,trajectory]
 return {'domain':DOMAIN,'original_paired_seed':original_seed,'derived_final_seed':int(digest(key)[:8],16),'key_sha256':digest(key)}

def install():
 from final_binding import FinalBinding as B
 if getattr(B,'_fork_aggregate_rng_installed',False):return
 original=B.__init__
 @functools.wraps(original)
 def init(self,*a,**k):
  original(self,*a,**k);m=self.policy.get('late_aggregate')
  if m is None or m.get('schema')!='agensh-v2-fork16plus4-final-v1':return
  need(m['branch_manifest_sha256']==self.manifest_sha and m['aggregate_phase']==self.trajectory,'BRANCH_FINAL_MANIFEST_IDENTITY')
  rng=seed(self.row['seed'],m['original16_snapshot']['sha256'],self.trajectory)
  self.row['seed']=rng['derived_final_seed'];self.identity.update(aggregate_branch_rng=rng,billing_domain='AUX_FINALIZATION_AGGREGATE_BRANCH')
 B.__init__=init;B._fork_aggregate_rng_installed=True
