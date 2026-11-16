"""Complete public Agensh backend inputs, before any ledger or Docker start.

Only fixed original PUBLIC framework assets and their117 hash-pinned source
files. No CyberGym project/task/candidate/model/session/credential bodies.
New roots come solely from the exact selected manifest scope; no path options.
"""
from pathlib import Path
import os,stat
from common import need,hash_file,strict,wire,publish,Refused
import fresh48_scope as S
HERE=Path(__file__).resolve().parent
ORIGIN=Path('/mnt/ptb-scratch2/agensh-comparison-20261026/gate4-prminfix-newquota-r1')
ASSETS=Path('/mnt/ptb-scratch2/agensh-comparison-20261026/v2-20261028-a4/agensh1-b1/backend-prestage-v1')
PLUGINS=ORIGIN.parent/'gate4-native-team2-v2/run/data/mattermost/client-plugins'
INDEX_SHA='9fba104baa959985b46838bd56d98db340ac560234a4ee735fd93406fa423018'
HOST_INDEX_SHA='2b9a92171488d972331f79d8fc49183c25954d86053d88348b2d73b3ce979179'
LEAVES=('NATIVE12_BOUNDED_TEMPLATE.json','context/Dockerfile','context/bootstrap.sh')
HELPERS=('prepare_first_scientific_backend_infra_once.py','scientific_backend_config.py','whole_team_backend_inventory.py')


def expected():
 a=HERE/'backend-assets/EXPECTED_SOURCE117.json';b=HERE/'backend-assets/ORIGINAL_PUBLIC_HOST_INPUTS_INDEX.json'
 need(hash_file(a)['sha256']==INDEX_SHA and hash_file(b)['sha256']==HOST_INDEX_SHA,'FRESH48_PUBLIC_BACKEND_ORIGINAL_INDICES')
 rows=strict(a.read_bytes());index=strict(b.read_bytes())
 need(len(rows)==117 and len({r['path']for r in rows})==117,'FRESH48_EXACT_PUBLIC117_ROSTER')
 for r in rows:
  p=Path(r['path']);need(not p.is_absolute()and all(x not in('','..','.')for x in r['path'].split('/')),'FRESH48_PUBLIC117_RELATIVE')
 need(set(index['files'])==set(LEAVES)|set(HELPERS),'FRESH48_ORIGINAL_PUBLIC_BACKEND_SIX_ASSETS')
 return rows,{name:{'size':index['files'][name]['bytes'],'sha256':index['files'][name]['sha256']}for name in LEAVES}


def qualify_sources(*,raise_on_error=True):
 rows,pins=expected();errors=[];passed=0
 def check(p,pin,kind):
  try:
   need(hash_file(p)==pin,'PUBLIC_ASSET_PIN')
  except (OSError,ValueError,Refused)as e:errors.append({'category':kind,'path':str(p),'exception_type':type(e).__name__});return False
  return True
 check(ORIGIN/'EXPECTED_SOURCE117.json',{'size':17737,'sha256':INDEX_SHA},'original117-index')
 check(ASSETS/'PUBLIC_HOST_INPUTS_INDEX.json',{'size':950,'sha256':HOST_INDEX_SHA},'original-host-index')
 for r in rows:
  passed+=check(ORIGIN/'source'/r['path'],{'size':r['bytes'],'sha256':r['sha256']},'public117-source')
 for name,pin in pins.items():check(ASSETS/name,pin,'public-backend-leaf')
 try:
  need(PLUGINS.is_dir()and not PLUGINS.is_symlink(),'PUBLIC_PLUGIN_DIRECTORY')
 except (OSError,ValueError,Refused)as e:errors.append({'category':'public-plugin-directory','path':str(PLUGINS),'exception_type':type(e).__name__})
 result={'schema':'agensh-v2-fresh48-complete-public-backend-inputs-preflight-v1',
  'public117_checked':117,'public117_valid':passed,'backend_leaf_checked':len(pins),'errors':errors,
  'scientific_or_private_body_read':False,'models':0,'Docker_calls':0,'credentials_read':False,'mutations':0}
 if raise_on_error:need(not errors,'FRESH48_FULL_PUBLIC_BACKEND_PREFLIGHT_FAILED_USE_AGGREGATE_RECEIPT')
 return result


def roots(mode):
 port=12400 if mode=='production'else 12560
 values=S.binding(S.public_scope(mode,port),mode)
 return [Path(values['BACKEND_PREFIX'])/f'agensh{w}-b{b}'/'backend-prestage-v1'for w in(4,8)for b in(1,2,3)]


def mapping(rows,destination):
 return [{'source':str(ORIGIN/'source'/r['path']),'destination':str(destination/'source'/r['path']),
  'size':r['bytes'],'sha256':r['sha256']}for r in rows]


def stage_one(destination,host_directory,*,rows,pins):
 destination=Path(destination);host_directory=Path(host_directory)
 need(not destination.exists()and not destination.is_symlink(),'FRESH48_NEW_PUBLIC_BACKEND_INPUT_ROOT_ONLY')
 # Hash/read all selected inputs before publishing this new root. Public bytes
 # only; the117 original source is copied later by the unchanged native helper.
 raw={name:(ASSETS/name).read_bytes()for name in LEAVES}
 import hashlib
 need(all({'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}==pins[name]for name,data in raw.items()),
  'FRESH48_PUBLIC_BACKEND_LEAVES_BEFORE_STAGE')
 helpers={name:{'path':str(host_directory/name),**hash_file(host_directory/name)}for name in HELPERS}
 destination.mkdir(parents=True,mode=0o700);(destination/'context').mkdir(mode=0o700)
 for name,data in raw.items():publish(destination/name,data,mode=0o600)
 index={'schema':'ops-public-backend-prestage-host-inputs-v1','files':{name:{'bytes':pin['size'],'sha256':pin['sha256']}for name,pin in pins.items()},
  'rendered_orchestration_metadata_only':helpers,'original_public_host_index_sha256':HOST_INDEX_SHA,
  'source117_index_sha256':INDEX_SHA,'no_model_or_experiment_payloads':True}
 publish(destination/'PUBLIC_HOST_INPUTS_INDEX.json',wire(index))
 publish(destination/'PUBLIC117_SOURCE_TO_NEW_ROOT.json',wire({'schema':'agensh-v2-public117-input-mapping-v1',
  'root':str(destination),'files':mapping(rows,destination),'scientific_body_read':False}))
 return {'root':str(destination),'public_inputs':hash_file(destination/'PUBLIC_HOST_INPUTS_INDEX.json'),
  'mapping':hash_file(destination/'PUBLIC117_SOURCE_TO_NEW_ROOT.json'),'source_files':117,
  'source_copy_deferred_to_unchanged_native_helper':True,'models':0}


def stage(mode,host_directory):
 qualify_sources();rows,pins=expected();destinations=roots(mode)
 need(all(not p.exists()and not p.is_symlink()for p in destinations),'FRESH48_ALL_SIX_BACKEND_INPUT_ROOTS_MUST_BE_NEW')
 return {'schema':'agensh-v2-fresh48-all-six-public-backend-inputs-staged-v1',
  'roots':[stage_one(p,host_directory,rows=rows,pins=pins)for p in destinations],
  'same_public117':True,'models':0,'Docker_calls':0}


def verify_one(destination,host_directory):
 destination=Path(destination);host_directory=Path(host_directory);_,pins=expected()
 need(destination.resolve()==destination and destination.is_dir()and not(destination/'run').exists(),
  'FRESH48_NATIVE_BACKEND_PRESEEDED_BEFORE_RUN')
 index=strict((destination/'PUBLIC_HOST_INPUTS_INDEX.json').read_bytes())
 need(set(index['files'])==set(LEAVES)and index['source117_index_sha256']==INDEX_SHA,
  'FRESH48_COMPLETE_THREE_PRESEEDED_LEAVES_AND117_MAP')
 for name,pin in pins.items():
  need(hash_file(destination/name)==pin and index['files'][name]=={'bytes':pin['size'],'sha256':pin['sha256']},
   'FRESH48_PRESEEDED_BACKEND_INPUT_PIN')
 for name in HELPERS:
  need(index['rendered_orchestration_metadata_only'][name]=={'path':str(host_directory/name),**hash_file(host_directory/name)},
   'FRESH48_SAME_CURRENT_RENDERED_BACKEND_HELPERS')
 rows,_=expected();mapped=strict((destination/'PUBLIC117_SOURCE_TO_NEW_ROOT.json').read_bytes())
 need(mapped['root']==str(destination)and mapped['files']==mapping(rows,destination),'FRESH48_SAME117_SOURCE_DESTINATION_MAPPING')
 return True
