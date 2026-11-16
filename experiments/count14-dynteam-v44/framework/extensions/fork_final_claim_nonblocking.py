"""Preserve original queue.claim I/O lock split, with atomic cross-queue cap.

The legacy wrapper held queue.mutex across original claim's unlocked verify_input.
Here only the original metadata candidate checks are extended. Its second check
is inside the original claim transaction, so concurrent verifications cannot
oversubscribe the shared cap. No input verification or authority guard is skipped.
"""
from pathlib import Path
import hashlib,inspect
from common import need,hash_file
import final_queue as fq
import final_attempts as attempts
QUEUE_SHA='3b7b5041b7156a98e48ad6b5b65da483ddfd68113d6e52c9586983a219059881'
CAPACITY_SHA='e6099f5ab547639c28a9df1769651400220ab97ec51509748919a2df251b478c'
WRAPPER_SHA='5fdf7e462f2d61dfd2e70b65e4e3a485934ee4fadfee247279b850c2f1d4b1fc'
CANDIDATE_SHA='1f4bac5e0d86ead0afa11ff8d1108a678dcbb1516b708f4808f505a9b3ce4e39'
CLAIM_SHA='98c3066eea3fd85f03a47932cc8fa1df144fff0c8424d866cbafc2dd3cc11c38'
GROUPS={};_candidate_original=None

def _source_sha(fn):return hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()

def candidate(queue):
 group=GROUPS.get(queue)
 if group is None:return _candidate_original(queue)
 # This scope contains only metadata/SQLite reads; no archive/hash/verify_input.
 with group['lock']:
  main,branch=group['queues']
  need(main.mutex is branch.mutex is group['lock'],'FORK_FINAL_CAP_SHARED_ORIGINAL_MUTEX')
  count=sum(sum(r['state']in fq.ACTIVE for r in attempts.live_rows(q))for q in(main,branch))
  if count>=group['cap']:return None
  return _candidate_original(queue)

def install_pair(main,branch,*,cap=12):
 global _candidate_original
 need(type(main)is type(branch)is fq.FinalQueue and main is not branch and main.home!=branch.home
      and main.mutex is branch.mutex and 1<=cap<=12,'FORK_FINAL_CAP_EXACT_SEPARATE_QUEUE_PAIR')
 need(hash_file(Path(fq.__file__))['sha256']==QUEUE_SHA and _source_sha(fq.FinalQueue.claim)==CLAIM_SHA,
      'FORK_FINAL_CAP_ORIGINAL_UNLOCKED_CLAIM_SOURCE')
 need(fq._claim_candidate is not candidate and _source_sha(fq._claim_candidate)==CANDIDATE_SHA
      and not GROUPS,'FORK_FINAL_CAP_ORIGINAL_CANDIDATE_ONCE')
 restored={}
 for q in(main,branch):
  wrapper=q.claim;closure=inspect.getclosurevars(wrapper).nonlocals
  need(hash_file(Path(inspect.getsourcefile(wrapper)))['sha256']==CAPACITY_SHA
       and _source_sha(wrapper)==WRAPPER_SHA and wrapper.__qualname__=='share_final_slots.<locals>.claim'
       and closure['main']is main and closure['branch']is branch and closure['lock']is main.mutex
       and closure['cap']==cap,'FORK_FINAL_CAP_EXACT_OLD_SHARED_WRAPPER')
  defaults=wrapper.__defaults__
  need(type(defaults)is tuple and len(defaults)==1 and getattr(defaults[0],'__self__',None)is q
       and getattr(defaults[0],'__func__',None)is fq.FinalQueue.claim,'FORK_FINAL_CAP_ORIGINAL_BOUND_CLAIM')
  restored[q]=defaults[0]
 with main.mutex:
  _candidate_original=fq._claim_candidate
  group={'queues':(main,branch),'lock':main.mutex,'cap':cap}
  GROUPS.update({main:group,branch:group})
  fq._claim_candidate=candidate
  for q,original in restored.items():q.claim=original
 return {'schema':'agensh-fork-final-shared-cap-unlocked-input-v1','global_final_subtask_cap':cap,
  'original_claim_and_verify_input_unchanged':True,'fresh_shared_cap_at_candidate_and_atomic_claim':True,
  'archive_IO_under_shared_queue_mutex':False,'original_authority_and_accounting_unchanged':True,
  'queues_claims_children_or_accounts_recreated':False,'old_activation_rewritten':False,'requests_replayed':False}
