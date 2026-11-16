"""Host-only original static Go MCP binary in a one-workspace filesystem jail.

No /proc, /sys, host root, ambient HOME, credentials files or other worker paths
are mounted. Native download methods retain their writable /work semantics but
cannot follow a raced symlink into another host directory. Network qualification
is still OPS-owned; only this trusted backend sees native endpoints/credentials.
"""
from pathlib import Path
import json,os,shutil
from common import need,hash_file,private_dir,digest
from native_mcp_overlay import BASE
SUPPLIED=BASE.parent/'operations-agensh-comparison-20261026/mcp-public-inputs-from-stopped-image-v1'
BINARY=SUPPLIED/'public-image-inputs/gitea-mcp'
def binary_pin(binary=None):
 metadata=json.loads((BASE/'NATIVE_MCP_DECLARATIONS_CONSUMED.json').read_text());expected=metadata['servers']['gitea']['binary_sha256'];pin=hash_file(BINARY if binary is None else binary);need(pin['sha256']==expected,'GITEA_BACKEND_ORIGINAL_BINARY_CHANGED');return pin

def build_gitea_backend(overlay,workspace,*,origin,token,agent,board_origin,node_binary=None,sandbox=None,sdk_identity=None):
 binary=BINARY
 if sdk_identity is not None:
  from native_sandbox import NativeSdkIdentity
  need(type(sdk_identity)is NativeSdkIdentity,'SDK_UID_HOST_ADMISSION_OBJECT');sdk_identity.verify();binary=sdk_identity.public_runtime/'gitea-mcp'
 pin=binary_pin(binary);overlay=private_dir(overlay);workspace=Path(workspace);need(workspace.is_absolute()and workspace.resolve()==workspace and workspace.is_dir()and not workspace.is_symlink(),'GITEA_BACKEND_WORKSPACE_CANONICAL')
 metadata=json.loads((overlay/'origin.json').read_text());need(metadata.get('native_text_prefix_integrity')is True,'GITEA_BACKEND_NATIVE_TEXT_PROOF_REQUIRED');notice=metadata['files']['mcp-notice-shim.cjs']['installed'];need(hash_file(overlay/'mcp-notice-shim.cjs')==notice,'GITEA_BACKEND_NOTICE_CHANGED')
 node=Path(node_binary or shutil.which('node')or'');need(node.is_absolute()and node.is_file(),'GITEA_BACKEND_NODE_REQUIRED');node=node.resolve(strict=True)
 from native_sandbox import admitted_sandbox
 sandbox=admitted_sandbox(sandbox);sandbox_pin=sandbox.verify()
 sandbox_argv=[str(sandbox.path),'--unshare-user','--unshare-pid','--unshare-uts','--unshare-ipc','--unshare-cgroup','--die-with-parent','--new-session','--ro-bind',str(binary),'/gitea-mcp','--bind',str(workspace),'/work','--tmpfs','/tmp','--chdir','/work','--unsetenv','AGENSH_MCP_CONTROL_FD','--','/gitea-mcp','-t','stdio']
 from native_sandbox import sdk_uid_command
 sandbox_argv,uid_receipt=sdk_uid_command(sandbox_argv,sdk_identity,'gitea',sandbox)
 command=[str(node),str(overlay/'mcp-notice-shim.cjs'),'--',*sandbox_argv]
 env={'PATH':'/usr/bin:/bin','HOME':'/tmp','GITEA_HOST':origin,'GITEA_ACCESS_TOKEN':token,'GITEA_INSECURE':'false','AGENT_NAME':agent,'BOARD_SERVICE_URL':board_origin}
 # TLS gets the host's public trust store, never a worker-selected CA/config.
 # The fixed HTTP service used by native compose needs no trust-store mount;
 # HTTPS is deliberately unqualified in this first actual static-binary port.
 need(origin.startswith('http://'),'GITEA_BACKEND_HTTP_NATIVE_SERVICE_ONLY')
 receipt={'schema':'agensh-native-gitea-backend-v1','binary':pin,'node':hash_file(node),'sandbox_executable':sandbox_pin,'sdk_uid_launch':uid_receipt,'notice_shim':notice,'command_sha256':digest(command),'writable_host_mounts':1,'proc_or_other_worker_mounts':False,'credential_in_argv':False,'actual_service_or_worker_netns_qualification':False}
 return command,env,receipt

def verify_command(command,workspace,environment,*,sandbox=None,sdk_identity=None):
 # Rebuild exact trusted shape using the same already pinned overlay/node. No
 # alternative executable/extra mount/options/host-selected env is smuggled in.
 need(type(command)is list and len(command)>3 and command[2]=='--','GITEA_BACKEND_FIXED_COMMAND')
 node=Path(command[0]);overlay=Path(command[1]).parent
 expected,env,_=build_gitea_backend(overlay,workspace,origin=environment.get('GITEA_HOST',''),token=environment.get('GITEA_ACCESS_TOKEN',''),agent=environment.get('AGENT_NAME',''),board_origin=environment.get('BOARD_SERVICE_URL',''),node_binary=node,sandbox=sandbox,sdk_identity=sdk_identity)
 need(command==expected and environment==env,'GITEA_BACKEND_EXACT_JAIL_AND_ENV')
