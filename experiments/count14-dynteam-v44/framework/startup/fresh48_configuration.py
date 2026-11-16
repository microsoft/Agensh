"""OPS-only private configuration derivation; developer tests synthetic shapes.

No network/credential/source-body decoding or runtime launch. The production
helper reads the one hash-pinned original private configuration, never emits it.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import copy,importlib.util,os,stat
from common import need,digest,wire,publish,hash_file,strict,regular_fd
import expansion100_contract as C
import fresh48_scope as S

OLD_CONFIG=Path(C.OLD_ROOT)/'config/private-launch-v2.json'
OLD_CONFIG_SHA='c9b359f812c4b2b2601312ec566dfb091fc070354c39d9c0e223d7e57688882e'
OLD_HOST=Path(C.OLD_ROOT)/'j/OPS_HOST_CONFIGURATION.json'
OLD_HOST_SHA='55410c2204b1ffd7c36b4892d1926218542f9ce06f0223d8526d982be1bd2d50'
TASK_SHA='5b0fe066c5a34fa3d995eacd47f9cbc03e12742236551c186ef7a6c3939f5441'
CLI_PINS={'cli_overlay_app_sha256':'cb5087c60e67ad545c83ba0d91b9a3edcdec5be16c7d981d4ecbe6c21dfb4dba',
 'cli_overlay_wrapper_sha256':'5fb99d565665e855a79cc955a627ddd8cf38819b422a45f8b5bed02a74a43f84',
 'cli_overlay_client_sha256':'e5d54b57e7a67a9d60ca33bf2d97b034c34aba0b0573b17bbf7d6d5c14c47a76'}
AUTHORIZATION_SHA='7768ef54d6e94c0ec6cfa9c4dd7393fb55799803782dacaf992309fd9c08885e'
CLI_ROOT=(_C14_SCRATCH + '/agensh-comparison-20261026/native-unmanaged-cli-backup-fixed-cold-v1/qualified-original-native-cli-unmanaged')

def derive(original,host,host_files,*,mode,runtime_directory):
 """No IO. Keep model/task/body/bounds/FINAL logic and seed bytes unchanged."""
 root,eid=S.selected(mode);root=Path(root);rt=Path(runtime_directory)
 need(C.group(original['manifest'])=='existing-1-16','FRESH48_CLONE_ORIGINAL_ONLY')
 C.roster(original['manifest'])
 need(original['manifest']['protocol']['task_description']==TASK_SHA,'FRESH48_ACTUAL_V2_OUTPUT_TASK_PIN')
 need(host['schema']=='agensh-ops-fixed-native-host-v1'and host['manifest_root']==C.OLD_ROOT,
      'FRESH48_ORIGINAL_HOST_CONFIGURATION')
 need(rt.is_absolute()and rt.is_relative_to(root),'FRESH48_PHYSICAL_NEW_PUBLIC_RUNTIME')
 need(type(host_files)is dict and 'scientific_native_host.py'in host_files and
      {'count14-v2-prompts/agents.txt','count14-v2-prompts/pbench-brief.txt'}<=set(host_files),
      'FRESH48_RENDERED_SAME_V2_HOST_ASSETS')
 c=copy.deepcopy(original);m=C.new_manifest(original['manifest']);m.update(root=str(root),experiment_id=eid)
 c.update(manifest=m,host_module=str(root/'h/scientific_native_host.py'),
   host_module_sha256=host_files['scientific_native_host.py'],driver_directory=str(root/'d'))
 c['launch_order']=[f'{eid}/Agensh-{w}/block-{b}/seed-{seed}'for w in(4,8)for b,seed in enumerate(C.SEEDS,1)]
 c['upstream']['token_file']=str(root/_count14_os.environ.get('COUNT14_GLM_KEY_RELPATH', 'config/glm-provider-key'))
 f=c['final']
 for name in('native_directory','framework_root','docker_config'):f[name]=str(root/'final-runtime'/name)
 f['credential_source']=str(root/_count14_os.environ.get('COUNT14_GLM_KEY_RELPATH', 'config/glm-provider-key'))
 # The qualified caller supplies the complete public overlay closure before the
 # original frozen adapter. Do not retain an old copied shell's broad PYTHONPATH.
 f['environment']['PYTHONPATH']=str(rt)
 h=copy.deepcopy(host);h.update(manifest_root=str(root),repository='main-v2-x48'+(''if mode=='production'else'-dry4'),
   host_files=copy.deepcopy(host_files),authorization_sha256=AUTHORIZATION_SHA,planned_search_and_aux_cap=36,initial_admission_headroom=1,
   qualified_current_cli_overlay=CLI_ROOT,**CLI_PINS)
 # Ensure only explicitly enumerated deployment/protocol-authorized fields vary.
 comparable=copy.deepcopy(c)
 for k in('manifest','host_module','host_module_sha256','driver_directory','launch_order'):comparable[k]=original[k]
 comparable['upstream']['token_file']=original['upstream']['token_file'];comparable['final']=original['final']
 need(comparable==original,'FRESH48_NO_OTHER_PRIVATE_CONFIG_DELTA')
 need(c['source']==original['source']and c['model_policy']==original['model_policy']and
      c['bounds']==original['bounds']and c['maximum_output']==original['maximum_output'],
      'FRESH48_SAME_SCIENCE_BODY_MODEL_OUTPUT_BOUND')
 return c,h

def _private(path,pin):
 path=Path(path);need(path.is_absolute()and path.resolve()==path,'FRESH48_PINNED_PRIVATE_CANONICAL')
 with regular_fd(path)as fd:
  s=os.fstat(fd);need(s.st_uid==0 and stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1 and s.st_size<=2**20,
   'FRESH48_PRIVATE_ROOT_OWNED0600')
  raw=bytearray()
  while True:
   part=os.read(fd,65536)
   if not part:break
   raw.extend(part);need(len(raw)<=2**20,'FRESH48_PRIVATE_CONFIG_BOUND')
  end=os.fstat(fd)
  need((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==
       (end.st_dev,end.st_ino,end.st_size,end.st_mtime_ns,end.st_ctime_ns),'FRESH48_PRIVATE_CONFIG_UNCHANGED')
 need(__import__('hashlib').sha256(raw).hexdigest()==pin,'FRESH48_ORIGINAL_PRIVATE_CONFIGURATION_PIN')
 return strict(bytes(raw))


def render_private(host_files,*,mode,runtime_directory):
 """OPS root only; no result body/config contents returned or printed."""
 need(os.geteuid()==0,'FRESH48_OPS_ONLY_PRIVATE_HELPER')
 c,h=derive(_private(OLD_CONFIG,OLD_CONFIG_SHA),_private(OLD_HOST,OLD_HOST_SHA),host_files,
  mode=mode,runtime_directory=runtime_directory)
 root=Path(c['manifest']['root']);need(root.resolve()==root and root.is_dir(),'FRESH48_EXISTING_CANONICAL_NEW_ROOT')
 dest=root/'config/private-launch-x48.json';hd=root/'h/OPS_HOST_CONFIGURATION.json'
 publish(dest,wire(c));publish(hd,wire(h))
 # Only public file identity and science pins, no credential digest/secret values.
 return {'schema':'agensh-v2-fresh48-private-clone-receipt-v1','mode':mode,'configuration':str(dest),
  'configuration_sha256':hash_file(dest)['sha256'],'host_configuration_sha256':hash_file(hd)['sha256'],
  'source_description_sha256':c['manifest']['protocol']['task_description'],
  'model_policy_sha256':digest(c['model_policy']),'same_seeds':list(C.SEEDS),'models':0,
  'requires_original_opaque_FINAL_directory_copies':True,'compiled_or_launched':False}
