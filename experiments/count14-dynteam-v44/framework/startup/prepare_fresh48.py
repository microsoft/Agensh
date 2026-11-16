"""OPS-only fresh scope preparation. No models, Docker, worker or SEARCH start.

Private old inputs are consumed internally only; source/model/task bytes stay
unchanged. Does not read original candidate/project/response contents. Original
FINAL directories are copied opaquely; credentials are never hashed or printed.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_BOOT = _count14_os.environ.get('COUNT14_HOST_BOOT_ID', '00000000-0000-0000-0000-000000000000')
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import copy,importlib.util,os,shutil,stat,subprocess,sys
from common import need,digest,wire,publish,hash_file,strict,regular_fd
from fresh48_configuration import _private,OLD_CONFIG,OLD_CONFIG_SHA,OLD_HOST,OLD_HOST_SHA,derive
from fresh48_scope import selected,public_scope,host,contract
from build_fresh48_runtime import build as overlay
HERE=Path(__file__).resolve().parent
BASE=Path((_C14_SCRATCH + '/ag28v2a4/c/parallel-v599999-agensh-count14-adapter-20261026'))
BOOT=(_C14_BOOT)


def verify_public_base():
 pins=strict((HERE/'BASE_PUBLIC_RUNTIME_PINS.json').read_bytes())
 need(len(pins)==239 and BASE.resolve()==BASE,'FRESH48_ACTUAL239_PUBLIC_BASE_PATH')
 for name,pin in pins.items():
  p=BASE/name
  need(p.resolve()==p and p.is_relative_to(BASE)and hash_file(p)==pin,'FRESH48_ACTUAL_PUBLIC_BASE_PIN')
 return {'verified_public_files':len(pins),'private_bodies_read':False}


def opaque_key(source,destination):
 source=Path(source);destination=Path(destination)
 need(source.resolve()==source and destination.parent.resolve()==destination.parent,'FRESH48_KEY_CANONICAL')
 with regular_fd(source)as fd:
  old=os.fstat(fd);need(old.st_uid==0 and stat.S_IMODE(old.st_mode)==0o600 and old.st_nlink==1 and 0<old.st_size<=16384,
   'FRESH48_APPROVED_NEW_PRIVATE_KEY_SOURCE')
  out=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  try:
   os.fchmod(out,0o600);count=0
   while True:
    raw=os.read(fd,4096)
    if not raw:break
    count+=len(raw);need(count<=16384,'FRESH48_KEY_SIZE_BOUND');data=memoryview(raw)
    while data:data=data[os.write(out,data):]
   os.fsync(out)
  finally:os.close(out)
  end=os.fstat(fd);need((old.st_dev,old.st_ino,old.st_size,old.st_mtime_ns,old.st_ctime_ns)==
   (end.st_dev,end.st_ino,end.st_size,end.st_mtime_ns,end.st_ctime_ns),'FRESH48_KEY_SOURCE_UNCHANGED')
 return {'opaque_copy':True,'key_digest_computed':False,'mode':'0600'}


def prepare(*,mode,port_base,reader_metadata,reader_metadata_sha):
 need(os.geteuid()==0 and os.uname().nodename==(_C14_HOSTNAME)and
  Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'FRESH48_OPS_EXACT_HOST_BOOT')
 root,_=selected(mode);root=Path(root);need(root.parent.resolve()==root.parent and not root.exists()and not root.is_symlink(),
  'FRESH48_NEW_EXACT_SCOPE_NO_RESTART')
 verify_public_base()
 from fresh48_backend_inputs import qualify_sources,stage
 qualify_sources() # all117 + fixed original assets before new-root mutation
 original=_private(OLD_CONFIG,OLD_CONFIG_SHA);oldhost=_private(OLD_HOST,OLD_HOST_SHA)
 # The metadata file is public; validate before any new-root mutation.
 meta=Path(reader_metadata);need(hash_file(meta)['sha256']==reader_metadata_sha,'FRESH48_READER_METADATA_PIN')
 from fresh48_reader import check_metadata
 check_metadata(strict(meta.read_bytes()))
 root.mkdir(mode=0o700);(root/'config').mkdir(mode=0o700);(root/'q').mkdir(mode=0o700)
 publish(root/'config/PUBLIC_READER_SOURCE.json',meta.read_bytes())
 contract(root/'q/mode',mode=mode);overlay(BASE,root/'q/runtime',mode=mode)
 rendered=host(HERE/'renderer',root/'h',public_scope(mode,port_base),mode=mode)
 spec=importlib.util.spec_from_file_location('fresh48_same_qualified_v2_prompts',HERE/'prompts/prepare_v2_cold.py')
 cold=importlib.util.module_from_spec(spec);spec.loader.exec_module(cold)
 # Exactly the existing v2 one-statement prompt adaptation, with original assets.
 hp=root/'h/scientific_native_host.py';patched=cold.patch_host(hp.read_bytes());hp.write_bytes(patched)
 asset=cold.load_assets();ap=root/'h/count14-v2-prompts';ap.mkdir(mode=0o755)
 for name in('agents.txt','pbench-brief.txt'):
  publish(ap/name,asset[name],mode=0o444);(ap/name).chmod(0o444)
 ap.chmod(0o555)
 files={name:hash_file(root/'h'/name)['sha256']for name in rendered['host_files']}
 files.update({f'count14-v2-prompts/{name}':hash_file(ap/name)['sha256']for name in('agents.txt','pbench-brief.txt')})
 backend_inputs=stage(mode,root/'h')
 publish(root/'config/PUBLIC_ALL_BACKEND_INPUTS_STAGED.json',wire(backend_inputs))
 c,h=derive(original,oldhost,files,mode=mode,runtime_directory=root/'q/runtime')
 from fresh48_bootstrap import child_path,prepare_branch
 c['final']['environment']['PYTHONPATH']=child_path(root)
 if mode=='zero-model':
  # Only the fixed dry interpreter may connect to the loopback synthetic
  # service. It has a dummy key and FINAL dispatch is disabled at runtime.
  c['upstream']['base']='http://127.0.0.1:12578/v1'
  h['gateway_base']='http://127.0.0.1:12578'
 prepare_branch(mode=mode)
 if mode=='production':opaque_key(Path(_count14_os.environ.get('COUNT14_GLM_KEY_SOURCE_FILE', '/path/to/glm-provider-key')),root/_count14_os.environ.get('COUNT14_GLM_KEY_RELPATH', 'config/glm-provider-key'))
 else:publish(root/_count14_os.environ.get('COUNT14_GLM_KEY_RELPATH', 'config/glm-provider-key'),b'OWN-ZERO-MODEL-NOT-PROVIDER-KEY',mode=0o600)
 (root/'final-runtime').mkdir(mode=0o700)
 for name in('native_directory','framework_root','docker_config'):
  src=Path(original['final'][name]);dest=Path(c['final'][name])
  need(src.is_absolute()and src.resolve()==src and src.is_dir()and not dest.exists(),'FRESH48_OPAQUE_FINAL_DIRECTORY_SCOPE')
  subprocess.run(['/usr/bin/cp','-a','--reflink=auto','--',str(src),str(dest)],check=True,
   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 publish(root/'config/private-derived-x48.json',wire(c));publish(root/'h/OPS_HOST_CONFIGURATION.json',wire(h))
 # A new interpreter ensures the exact dry/production contract and13-module
 # overlay are loaded BEFORE any scientific import. No global root monkeypatch.
 env=dict(os.environ);env.update(c['final']['environment']);env['PYTHONDONTWRITEBYTECODE']='1'
 subprocess.run([sys.executable,'-B',str(HERE/'compile_fresh48.py'),mode],env=env,check=True,
  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 return {'schema':'agensh-v2-fresh48-private-preparation-v1','mode':mode,'root':str(root),
  'same_source_task_model_and_seeds':True,'new_provider_key':True,'models':0,'workers_started':0,
  'ready_for_zero_model_launcher_rehearsal':True,'full_launcher_rehearsal_pass':False,'SEARCH_released':False}
