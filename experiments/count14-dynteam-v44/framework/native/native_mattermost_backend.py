"""Host-only original-image Python/MM launch, private env, no worker endpoint.

This reuses the already supplied public image SDK closure; it neither discovers
new metadata nor downloads dependencies. It is not a service/worker-netns gate.
"""
from dataclasses import dataclass
from pathlib import Path
import json,os,shutil
from common import need,hash_file,private_dir,digest
BASE=Path(__file__).resolve().parent
SUPPLIED=BASE.parent/'operations-agensh-comparison-20261026/mcp-public-inputs-from-stopped-image-v1'
MANIFEST_PIN={'size':889989,'sha256':'9f9f0af109ee3a829008bdaecb572fea7a0cdb18cbb44006be8fef679ec6c121'}
@dataclass(frozen=True)
class ImageRuntime:
 root:Path
 manifest:Path
 @classmethod
 def supplied(cls):return cls(SUPPLIED/'public-python311-image-runtime',SUPPLIED/'PUBLIC_PYTHON311_RUNTIME_INPUT_MANIFEST.json')
 def verify(self):
  need(self.root.is_absolute()and self.root.resolve()==self.root,'MM_BACKEND_CANONICAL_RUNTIME')
  need(hash_file(self.manifest)==MANIFEST_PIN,'MM_BACKEND_ORIGINAL_RUNTIME_MANIFEST_PIN')
  rows=json.loads(self.manifest.read_text())['entries'];need(len(rows)==4948,'MM_BACKEND_RUNTIME_INPUT_COUNT')
  result={}
  from common import parts
  for row in rows:
   parts(row['path']);path=self.root/row['path'];pin=hash_file(path)
   need(pin=={'size':row['bytes'],'sha256':row['sha256']},'MM_BACKEND_ORIGINAL_RUNTIME_INPUT_CHANGED');result[row['path']]=pin['sha256']
  return result
 def command(self,overlay,home,*,origin,token,agent,board_origin,node_binary=None,sandbox=None,sdk_identity=None):
  runtime=self
  if sdk_identity is not None:
   from native_sandbox import NativeSdkIdentity
   need(type(sdk_identity)is NativeSdkIdentity,'SDK_UID_HOST_ADMISSION_OBJECT');sdk_identity.verify();runtime=ImageRuntime(sdk_identity.public_runtime/'python',self.manifest)
  runtime.verify();home=private_dir(home);overlay=private_dir(overlay)
  metadata=json.loads((overlay/'origin.json').read_text());pin=metadata['files']['mcp-notice-shim.cjs']['installed']
  need(hash_file(overlay/'mcp-notice-shim.cjs')==pin,'MM_BACKEND_NOTICE_OVERLAY_CHANGED')
  node=Path(node_binary or shutil.which('node')or'');need(node.is_absolute()and node.is_file(),'MM_BACKEND_NODE_REQUIRED');node=node.resolve(strict=True)
  from native_sandbox import admitted_sandbox
  sandbox=admitted_sandbox(sandbox);sandbox_pin=sandbox.verify()
  # Keep network for the host-only fixed service origin. A caller must separately
  # qualify the actual service/broker network; this is not worker only-relay.
  # Filesystem/user/PID isolation exposes public runtime+system libs only.
  sandbox_argv=[str(sandbox.path),'--unshare-user','--unshare-pid','--unshare-uts','--unshare-ipc','--unshare-cgroup','--die-with-parent','--new-session',
   '--ro-bind',str(runtime.root/'bin/python3.11'),'/usr/bin/python3.11',
   '--ro-bind',str(runtime.root/'python3.11'),'/usr/lib/python3.11',
   '--ro-bind',str(runtime.root/'site-packages'),'/site-packages',
   '--ro-bind','/lib/x86_64-linux-gnu','/lib/x86_64-linux-gnu','--ro-bind','/lib64','/lib64',
   '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--chdir','/tmp','--unsetenv','AGENSH_MCP_CONTROL_FD',
   '--','/usr/bin/python3.11','-B','-m','mcp_server_mattermost']
  from native_sandbox import sdk_uid_command
  sandbox_argv,uid_receipt=sdk_uid_command(sandbox_argv,sdk_identity,'mattermost',sandbox)
  command=[str(node),str(overlay/'mcp-notice-shim.cjs'),'--',*sandbox_argv]
  # Credentials are NEVER bwrap --setenv argv, logs or worker config. The
  # complete inherited env is this trusted map, not os.environ/proxy settings.
  env={'PATH':'/usr/bin:/bin','HOME':'/tmp','PYTHONHOME':'/usr','PYTHONPATH':'/site-packages','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1',
   'MATTERMOST_URL':origin,'MATTERMOST_TOKEN':token,'MATTERMOST_AUTH_MODE':'static_token','MATTERMOST_MAX_RETRIES':'0',
   'MATTERMOST_LOG_LEVEL':'WARNING','MATTERMOST_LOG_FORMAT':'text','AGENT_NAME':agent,'BOARD_SERVICE_URL':board_origin}
  receipt={'schema':'agensh-native-mm-backend-public-inputs-v1','runtime_manifest_pin':MANIFEST_PIN,'runtime_files':4948,'native_package_version':'0.5.1','node':hash_file(node),'sandbox_executable':sandbox_pin,'sdk_uid_launch':uid_receipt,'notice_shim':pin,'command_sha256':digest(command),'credential_in_argv':False,'worker_netns_or_actual_service_qualification':False}
  return command,env,receipt

 def verify_command(self,command,home,environment,*,sandbox=None,sdk_identity=None):
  need(type(command)is list and len(command)>3 and command[2]=='--','MM_BACKEND_FIXED_COMMAND')
  expected,env,_=self.command(Path(command[1]).parent,home,origin=environment.get('MATTERMOST_URL',''),token=environment.get('MATTERMOST_TOKEN',''),agent=environment.get('AGENT_NAME',''),board_origin=environment.get('BOARD_SERVICE_URL',''),node_binary=Path(command[0]),sandbox=sandbox,sdk_identity=sdk_identity)
  need(command==expected and environment==env,'MM_BACKEND_EXACT_JAIL_AND_ENV')
