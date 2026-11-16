"""Explicit host-root deployment of exact supplied public SDKs, never private state.

Fix owner-only 0500/0400 transfer modes by COPYING into a new root, never chmod
original source, workspace, credentials or host configuration. SHA/bytes unchanged.
"""
from pathlib import Path
import json,os,stat
from common import need,hash_file,publish,wire

def stage_public_runtime(destination):
 need(os.getuid()==0 and os.geteuid()==0,'SDK_PUBLIC_TRUSTED_ROOT')
 root=Path(destination);need(root.is_absolute()and root.resolve()==root and not root.exists(),'SDK_PUBLIC_NEW_CANONICAL_ROOT');root.mkdir(mode=0o700)
 from native_gitea_backend import BINARY,binary_pin
 from native_mattermost_backend import ImageRuntime
 runtime=ImageRuntime.supplied();runtime.verify();entries=[(BINARY,'gitea-mcp',binary_pin(),0o555)]
 for row in json.loads(runtime.manifest.read_text())['entries']:entries.append((runtime.root/row['path'],'python/'+row['path'],{'size':row['bytes'],'sha256':row['sha256']},0o555 if row['path']=='bin/python3.11'else 0o444))
 rows=[]
 for source,name,pin,mode in entries:
  target=root/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True);need(hash_file(source)==pin,'SDK_PUBLIC_SOURCE_CHANGED');publish(target,source.read_bytes(),mode=mode);target.chmod(mode);need(hash_file(target)==pin and target.stat().st_uid==0,'SDK_PUBLIC_COPY_CHANGED');rows.append({'path':name,**pin,'mode':mode})
 for path in sorted((p for p in root.rglob('*')if p.is_dir()),key=lambda p:len(p.parts),reverse=True):path.chmod(0o555)
 receipt={'schema':'agensh-native-sdk-public-deployment-v1','files':len(rows),'rows':rows,'originals_modified':False,'private_inputs_copied':False};publish(root/'PUBLIC_SDK_DEPLOYMENT.json',wire(receipt),mode=0o444);(root/'PUBLIC_SDK_DEPLOYMENT.json').chmod(0o444);root.chmod(0o555);return receipt

def admitted_public_root(path):
 need(isinstance(path,Path),'SDK_PUBLIC_PATH_OBJECT');p=Path(path);need(p.is_absolute()and p.resolve()==p and not p.is_symlink(),'SDK_PUBLIC_CANONICAL_ROOT');s=p.stat();need(stat.S_ISDIR(s.st_mode)and s.st_uid==0 and s.st_mode&0o777==0o555,'SDK_PUBLIC_IMMUTABLE_ROOT')
 from native_mattermost_backend import ImageRuntime
 runtime=ImageRuntime.supplied();expected={'gitea-mcp':0o555,'PUBLIC_SDK_DEPLOYMENT.json':0o444}
 for row in json.loads(runtime.manifest.read_text())['entries']:expected['python/'+row['path']]=0o555 if row['path']=='bin/python3.11'else 0o444
 files={};directories=set()
 for name in expected:
  q=p/name
  for d in q.parents:
   if d==p:break
   directories.add(d)
  require=q.lstat();need(stat.S_ISREG(require.st_mode)and require.st_uid==0 and require.st_mode&0o7777==expected[name],'SDK_PUBLIC_EXACT_FILE_OWNER_MODE');files[name]=q
 for d in directories:
  ds=d.lstat();need(stat.S_ISDIR(ds.st_mode)and ds.st_uid==0 and ds.st_mode&0o7777==0o555,'SDK_PUBLIC_EXACT_DIRECTORY_OWNER_MODE')
 need(set(p.rglob('*'))==set(files.values())|directories,'SDK_PUBLIC_EXACT_PUBLIC_CLOSURE');return p
