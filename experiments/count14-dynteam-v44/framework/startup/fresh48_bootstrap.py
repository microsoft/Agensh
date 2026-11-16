"""Fixed-scope launch metadata and OPS-only private branch derivation."""
from pathlib import Path
import copy,os,stat
from common import need,digest,wire,publish,hash_file
from fresh48_configuration import _private
from fresh48_scope import selected
HERE=Path(__file__).resolve().parent
OLD_BRANCH=Path('/mnt/ptb-scratch2/ag28v2a4/d/FORK_AGGREGATE_RUNTIME.json')
OLD_BRANCH_SHA='68efe88c0098d96da8475435c1126d941cf7a9a7ba60caad06331f3940831720'
HEALTH=Path('/mnt/ptb-scratch2/ag28v2a4/config/ops-glm-outage-health-20261029/events.jsonl')


def branch(original,*,mode):
 from aggregate_install import FIELDS
 from aggregate_prompt import PILOT_SHA
 need(set(original)==FIELDS and original['schema']=='agensh-fork-aggregate-runtime-v1','FRESH48_ORIGINAL_BRANCH_EXACT_FIELDS')
 need(original['pilot_campaign_sha256']==PILOT_SHA,'FRESH48_BRANCH_SAME_PILOT_AGGREGATOR')
 root,_=selected(mode);v=copy.deepcopy(original)
 v['host_socket']=str(Path(root)/'d/af.sock')
 v['pilot_campaign']=str(HERE/'deps/pilot-campaign.py')
 need(hash_file(v['pilot_campaign'])['sha256']==PILOT_SHA,'FRESH48_BRANCH_PUBLIC_PROMPT_PIN')
 return v


def prepare_branch(*,mode):
 """Only OPS executes: private input never returned or printed."""
 need(os.geteuid()==0,'FRESH48_OPS_ONLY_BRANCH_PRIVATE_CONFIG')
 old=_private(OLD_BRANCH,OLD_BRANCH_SHA);v=branch(old,mode=mode)
 root,_=selected(mode);p=Path(root)/'config/FORK_AGGREGATE_RUNTIME_V4.json';publish(p,wire(v))
 return {'path':str(p),'sha256':hash_file(p)['sha256'],'same_original_fields_except_pilot_path_and_host_socket':True}


def child_path(root):
 root=Path(root)
 return os.pathsep.join(map(str,[root/'q/mode',root/'q/runtime',HERE,HERE/'deps',
  Path('/mnt/ptb-scratch2/ag28v2a4/c/parallel-v599999-agensh-count14-adapter-20261026'),
  Path('/mnt/ptb-scratch2/ag28v2a4/final-public-runtime/venv/lib/python3.12/site-packages')]))


def launch_metadata(*,mode,compiled_sha):
 root,eid=selected(mode);root=Path(root)
 return {'schema':'agensh-v2-fresh48-fixed-launch-v1','mode':mode,'root':str(root),'experiment_id':eid,
  'configuration':str(root/'config/private-launch-x48-v4.json'),'configuration_sha256':compiled_sha,
  'branch_configuration':str(root/'config/FORK_AGGREGATE_RUNTIME_V4.json'),
  'branch_configuration_sha256':hash_file(root/'config/FORK_AGGREGATE_RUNTIME_V4.json')['sha256'],
  'reader':str(root/'config/reader120/budget_pause_clock.js'),'health_events':str(HEALTH),
  'pythonpath':child_path(root),'SEARCH_released':False,'models':0}
