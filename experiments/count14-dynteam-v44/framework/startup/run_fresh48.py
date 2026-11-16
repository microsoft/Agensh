#!/usr/bin/env python3
"""One fixed launcher, mode selected before any native runtime import.

OPS-only. prepare/run are explicit; no automatic retry or production request
until the separate dry root's actual full-launcher receipt has been checked.
"""
from pathlib import Path
import argparse,hashlib,os,sys
HERE=Path(__file__).resolve().parent
BASE=Path('/mnt/ptb-scratch2/ag28v2a4/c/parallel-v599999-agensh-count14-adapter-20261026')
# Bootstrap dependency closure only; scientific runtime is imported in child.
if __name__=='__main__'and(sys.argv[1:2]!=['_owner']):
 for p in reversed([HERE,HERE/'deps',BASE]):sys.path.insert(0,str(p))
from common import need,hash_file,strict,wire,publish
from fresh48_scope import selected


def bundle_fingerprint():
 p=HERE/'BUNDLE_FILES.json';m=strict(p.read_bytes())
 need(m['schema']=='agensh-v2-fresh48-public-cold-files-v1','FRESH48_BUNDLE_MAP_SCHEMA')
 for name,pin in m['files'].items():
  q=HERE/name;need(q.resolve()==q and q.is_relative_to(HERE),'FRESH48_BUNDLE_CANONICAL_PUBLIC_LEAF')
  need(hash_file(q)==pin,'FRESH48_BUNDLE_EXACT_PUBLIC_LEAF_PIN')
 return hash_file(p)['sha256']


def check_dry(proof,fingerprint):
 need(proof['schema']=='agensh-v2-fresh48-same-launcher-real-cli-zero-model-v1'and proof['PASS']is True
  and proof['models']==0 and proof['FINAL_calls']==0 and len(proof['teams'])==2
  and proof['bundle_fingerprint']==fingerprint
  and {r['workers']for r in proof['teams']}=={4,8}
  and all(r['native_controller_resumed']and r['inventory_collect_whole_freeze_snapshot_thaw']for r in proof['teams']),
  'FRESH48_ACTUAL_SAME_LAUNCHER_DRY_PASS_REQUIRED')


def run_child(mode):
 from fresh48_bootstrap import child_path
 root,eid=selected(mode);root=Path(root)
 meta=strict((root/'config/FIXED_LAUNCH_V4.json').read_bytes())
 need(meta['mode']==mode and meta['root']==str(root)and meta['experiment_id']==eid,'FRESH48_FIXED_PREPARED_LAUNCH_MODE')
 need(meta['pythonpath']==child_path(root),'FRESH48_EXACT_MINIMAL_CHILD_PATH')
 env=dict(os.environ);env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=child_path(root))
 os.execve(sys.executable,[sys.executable,'-B',str(HERE/'run_fresh48.py'),'_owner','--mode',mode],env)


def owner(mode):
 from expansion100_contract import NEW_ROOT,NEW_EID
 root,eid=selected(mode);root=Path(root)
 need(str(root)==NEW_ROOT and eid==NEW_EID,'FRESH48_MODE_CONTRACT_BEFORE_NATIVE_IMPORT')
 from run_native_scientific6 import read_configuration,load_host
 from fresh48_owner import Owner
 from fresh48_bootstrap import child_path
 meta=strict((root/'config/FIXED_LAUNCH_V4.json').read_bytes())
 need(os.environ['PYTHONPATH']==child_path(root),'FRESH48_NO_DEVELOPER_BROAD_PATH')
 c=read_configuration(meta['configuration'],meta['configuration_sha256'])
 need(hash_file(meta['branch_configuration'])['sha256']==meta['branch_configuration_sha256'],'FRESH48_PREPARED_BRANCH_PIN')
 branch=strict(Path(meta['branch_configuration']).read_bytes())
 if mode=='production':
  # This is actual OPS evidence from the separate fixed dry root, never the
  # offline object fixture or a flag in a preparation receipt.
  dry=Path(selected('zero-model')[0])/'d/ZERO_MODEL_FULL_LAUNCHER_PASS.json'
  proof=strict(dry.read_bytes())
  check_dry(proof,bundle_fingerprint())
 else:
  need(c['upstream']['base']=='http://127.0.0.1:12578/v1','FRESH48_DRY_FIXED_NO_PROVIDER_ENDPOINT')
  from fresh48_zero import install
  server=install()
 host=load_host(c['host_module'],c['host_module_sha256'])
 obj=Owner(c,host,branch,health_path=meta['health_events'],reader_path=meta['reader'])
 publish(obj.home/'OWNER_PROCESS_IDENTITY.json',wire({'schema':'agensh-v2-fresh48-owner-identity-v1',
  **obj.identity,'root':str(root),'experiment_id':eid,'mode':mode,'configuration_sha256':meta['configuration_sha256']}))
 if mode=='zero-model':
  from fresh48_zero import rehearsal
  return rehearsal(obj,server)
 return obj.run()


def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=('preflight','prepare','run','_owner'))
 p.add_argument('--mode',choices=('production','zero-model'),required=True)
 p.add_argument('--reader-metadata');p.add_argument('--reader-metadata-sha256');a=p.parse_args()
 need(os.geteuid()==0,'FRESH48_OPS_ROOT_LAUNCH_ONLY')
 bundle_fingerprint()
 if a.command=='preflight':
  from fresh48_backend_inputs import qualify_sources
  result=qualify_sources(raise_on_error=False)
  print(wire(result).decode());return 0 if not result['errors']else 1
 if a.command=='prepare':
  need(a.reader_metadata and a.reader_metadata_sha256,'FRESH48_READER_PUBLIC_METADATA_REQUIRED')
  from prepare_fresh48 import prepare
  result=prepare(mode=a.mode,port_base=12400 if a.mode=='production'else 12560,
   reader_metadata=a.reader_metadata,reader_metadata_sha=a.reader_metadata_sha256)
  print(wire(result).decode());return 0
 if a.command=='run':return run_child(a.mode)
 return owner(a.mode)
if __name__=='__main__':
 try:result=main()
 except BaseException as e:
  if isinstance(e,SystemExit):raise
  # Only public type/code. Native/private frames stay in OPS-restricted logs.
  import traceback
  frames=[{'file':f.filename,'line':f.lineno,'function':f.name}for f in traceback.extract_tb(e.__traceback__)]
  print(wire({'status':'FAILED_RETAIN_NO_RETRY','exception_type':type(e).__name__,
   'frames':frames,'messages_locals_omitted':True}).decode(),file=sys.stderr)
  raise SystemExit(1)
 raise SystemExit(result if type(result)is int else 0)
