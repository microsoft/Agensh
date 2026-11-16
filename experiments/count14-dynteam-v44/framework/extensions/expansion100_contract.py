"""User-authorized, additive Agensh v2 100M policy. No runtime resurrection.

OPS-only write methods use an already exclusively owned native Ledger. They do
not create/open a ledger, alter prior targets/usage/requests/claims, release a
frozen cgroup or claim that a dead scientific owner is alive.
"""
from pathlib import Path
import copy,json
from common import need,digest,wire,publish,strict

SEEDS=(4287909351,1636023914,2619738241)
REGULAR=(10_000_000,20_000_000,50_000_000,100_000_000)
LIMIT=REGULAR[-1]
NAME='USER_100M_EXPANSION_AUTHORIZATION_V1.json'
OLD_ROOT='/mnt/ptb-scratch2/ag28v2a4'
OLD_EID='agensh-v2-20261028-a4'
NEW_ROOT='/mnt/ptb-scratch2/ag30v2x48'
NEW_EID='agensh-v2-20261030-x48'
# Conserved across separate owners, INCLUDING all historical uncertain slots.
QUOTAS={'existing-1-16':{'global':60,'search':54,'auxiliary':6,'final':6},
        'new-4-8':{'global':36,'search':30,'auxiliary':6,'final':6}}

def group(manifest):
 root,eid=manifest['root'],manifest['experiment_id']
 need((root,eid)in((OLD_ROOT,OLD_EID),(NEW_ROOT,NEW_EID)),'EXP100_EXACT_REGISTERED_ROOT_AND_EID')
 return 'existing-1-16' if root==OLD_ROOT else 'new-4-8'

def roster(manifest):
 g=group(manifest);sizes=(16,1)if g=='existing-1-16'else(4,8)
 need(manifest['settings']==[{'id':f'Agensh-{n}','family':'agensh','workers':n,'path':'team','process_feedback':'disabled'}for n in sizes],
      'EXP100_EXACT_AUTHORIZED_SETTING_PAIR')
 need(manifest['blocks']==[{'block':i,'seed':s}for i,s in enumerate(SEEDS,1)],'EXP100_PAIRED_SEEDS')
 return {f"{manifest['experiment_id']}/Agensh-{n}/block-{b}/seed-{s}":
         {'workers':n,'block':b,'seed':s,'roles':[f'worker-{i:02d}'for i in range(n)]}
         for b,s in enumerate(SEEDS,1)for n in sizes}

def authorization(manifest):
 g=group(manifest);rows=roster(manifest)
 need(manifest['budget']=={'search_tokens':20_000_000,'checkpoints':[10_000_000,20_000_000],
   'feedback_charge':0,'barrier_policy':'no_overshoot_reserve_then_drain','finalization_protocol':'v2.1','K':3},
   'EXP100_ORIGINAL_STARTUP_MANIFEST_ABI_UNCHANGED')
 return {'schema':'agensh-v2-user100m-additive-authorization-v1','manifest_sha256':digest(manifest),
  'root':manifest['root'],'experiment_id':manifest['experiment_id'],'trajectories':sorted(rows),
  'search_tokens':LIMIT,'regular_checkpoints':list(REGULAR),'K':3,
  'diagnostic_snapshot_tokens':16_000_000,'independent_fork_tokens':4_000_000,'forks_per_trajectory':1,
  'branch_billing':'independent-search-and-AUX','timeline_interval_tokens':1_000_000,
  'direct_evaluation':{'every_search_tokens':2_000_000,'every_seconds':1800,'concurrency':4,'agent_feedback':False},
  'natural_idle_seconds':600,'neutral_until_search_tokens':LIMIT,'reader_lease_seconds':120,
  'fd_limit':65536,'memory_reserve_GiB':64,'quota_group':g,'quota':dict(QUOTAS[g]),
  'global_all_roots_fp8_cap':96,'global_all_roots_final_cap':12,
  'unchanged_manifest':True,'same_session_continuation':g=='existing-1-16',
  'replay_requests':False,'redo_original_forks':False,'user_authorized':True}

def write_authorization(manifest):
 """Immutable additive file, not a rewrite of the original manifest."""
 policy=authorization(manifest);p=Path(manifest['root'])/NAME
 need(p.parent.resolve()==p.parent and p.parent.is_dir(),'EXP100_CANONICAL_EXISTING_ROOT')
 if p.exists()or p.is_symlink():
  need(not p.is_symlink()and p.is_file()and strict(p.read_bytes())==policy,'EXP100_AUTHORIZATION_CONFLICT')
 else:publish(p,wire(policy),mode=0o400)
 return policy

def check(manifest):
 p=Path(manifest['root'])/NAME
 need(p.is_file()and not p.is_symlink()and p.resolve()==p,'EXP100_FIXED_AUTHORIZATION_REQUIRED')
 result=strict(p.read_bytes());need(result==authorization(manifest),'EXP100_EXACT_IMMUTABLE_AUTHORIZATION')
 return result

def append_existing_targets(ledger,manifest):
 """All-six atomic append only. DOES NOT transition generation/state or thaw.

 A failed all-six validation leaves every account unchanged. Reentry after the
 durable append is read-only, even if the native continuation has since run.
 """
 policy=check(manifest);need(group(manifest)=='existing-1-16','EXP100_EXISTING_SIX_ONLY')
 rows=roster(manifest);plans=[]
 with ledger.tx():
  # The private mainline DB must not accidentally include a foreign/new team.
  need({r[0]for r in ledger.db.execute('SELECT trajectory FROM accounts')}==set(rows),'EXP100_EXACT_SIX_ACCOUNT_DATABASE')
  for t,row in rows.items():
   a=dict(ledger.account(t));old=json.loads(a['targets']);f=ledger.frontier(t)
   need(a['manifest_sha']==digest(manifest)and json.loads(a['roles'])==row['roles'],'EXP100_ORIGINAL_ACCOUNT_IDENTITY')
   need(old==sorted(set(old))and set((10_000_000,16_000_000,20_000_000,50_000_000))<=set(old),
        'EXP100_PRESERVE_PRIOR_REGULAR_AND_DIAGNOSTIC_TARGETS')
   if old[-1]==LIMIT:
    # Idempotent after release: never reset state/stage or produce a second event.
    prior=ledger.db.execute("SELECT metadata FROM events WHERE trajectory=? AND kind='USER_AUTHORIZED_MAINLINE_EXTEND_TO_100M'",(t,)).fetchall()
    need(len(prior)==1 and strict(prior[0][0].encode())['authorization_sha256']==digest(policy),
         'EXP100_ALREADY_EXTENDED_REQUIRES_ORIGINAL_APPEND_EVENT')
    continue
   need(old[-1]==50_000_000 and a['stage']==len(old)-1 and a['state']=='COMMITTED_PARKED'
        and 0<=a['actual']<=50_000_000,'EXP100_ORIGINAL_FINAL50_PARKED_ONLY')
   need(f['unresolved']==f['reserved']==f['active_operations']==0 and not ledger.admission_fault(t),
        'EXP100_DRAINED_NO_REAL_TRAJECTORY_FAULT')
   snapshot=ledger.db.execute('SELECT target,ref_sha FROM snapshots WHERE trajectory=? AND generation=?',
                              (t,a['generation'])).fetchone()
   need(snapshot is not None and snapshot['target']==50_000_000,'EXP100_ORIGINAL_50M_COMMIT_REQUIRED')
   plans.append((t,a,old,snapshot['ref_sha']))
  for t,a,old,ref in plans:
   new=old+[LIMIT]
   ledger.db.execute('UPDATE accounts SET targets=? WHERE trajectory=?',(wire(new).decode(),t))
   ledger.event(t,'USER_AUTHORIZED_MAINLINE_EXTEND_TO_100M',{
    'authorization_sha256':digest(policy),'previous_targets':old,'execution_targets':new,
    'original_50m_snapshot_sha256':ref,'actual_unchanged':a['actual'],'stage_unchanged':a['stage'],
    'generation_unchanged':a['generation'],'state_unchanged':a['state'],'requests_replayed':0,
    'runtime_continuation':'REQUIRES_REAL_ORIGINAL_SESSION_REBIND_AND_NATIVE_RELEASE'})
 return {'updated':sorted(t for t,*_ in plans),'authorization_sha256':digest(policy),
         'runtime_released':False,'requests_replayed':0}

def append_new_targets(ledger,manifest,t):
 """First-start constructor remains10/20; append50/100 before CLI release."""
 policy=check(manifest);rows=roster(manifest)
 need(group(manifest)=='new-4-8'and t in rows,'EXP100_NEW48_SCOPE')
 with ledger.tx():
  a=ledger.account(t);old=json.loads(a['targets'])
  need(a['manifest_sha']==digest(manifest)and json.loads(a['roles'])==rows[t]['roles'],'EXP100_NEW48_ACCOUNT_IDENTITY')
  need(a['generation']==1 and a['stage']==0 and a['state']=='RUNNING'and a['actual']==0
       and not ledger.db.execute('SELECT 1 FROM requests WHERE trajectory=?',(t,)).fetchone(),
       'EXP100_NEW48_BEFORE_FIRST_MODEL_ONLY')
  updated=[10_000_000]+([16_000_000]if 16_000_000 in old else [])+list(REGULAR[1:])
  if old==updated:return False
  need(old in ([10_000_000,20_000_000],[10_000_000,16_000_000,20_000_000]),'EXP100_NEW48_ORIGINAL_CONSTRUCTOR_TARGETS')
  ledger.db.execute('UPDATE accounts SET targets=? WHERE trajectory=?',(wire(updated).decode(),t))
  ledger.event(t,'USER_AUTHORIZED_NEW48_TARGETS_TO_100M',{'authorization_sha256':digest(policy),
       'previous_targets':old,'execution_targets':updated,'requests_replayed':0})
 return True

def new_manifest(original):
 """Public manifest only; no private config/credentials/task text cloning."""
 need(group(original)=='existing-1-16','EXP100_ORIGINAL_V2_MANIFEST_REQUIRED')
 roster(original);m=copy.deepcopy(original);m.update(root=NEW_ROOT,experiment_id=NEW_EID,revision=original['revision']+1)
 m['settings']=[{'id':f'Agensh-{n}','family':'agensh','workers':n,'path':'team','process_feedback':'disabled'}for n in(4,8)]
 q=QUOTAS['new-4-8'];m['scheduling']={'global_gateway_cap':q['global'],'search_cap':q['search'],
  'auxiliary_cap':q['auxiliary'],'final_global_cap':q['final'],'memory_reserve_GiB':64}
 authorization(m);return m
