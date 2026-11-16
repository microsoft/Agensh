#!/usr/bin/env python3
"""Isolated deployment installer: relative SOURCE layout -> fresh host CODE paths.

Stdlib only. No local original /srv path, owner, factory, scope, model or private
asset is reconstructed. Generated registry MUST remain outside frozen CODE.
"""
from pathlib import Path,PurePosixPath
import argparse,hashlib,importlib.util,json,os,stat,sys


def need(ok,code):
 if not ok:raise ValueError(code)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def wire(v):return (json.dumps(v,indent=2,sort_keys=True)+'\n').encode()


def rel(value,root=False):
 need(type(value)is str and value and '\x00'not in value,'INSTALL_RELATIVE_PATH')
 if root and value=='.':return value
 p=PurePosixPath(value);need(not p.is_absolute()and '..'not in p.parts and str(p)==value and value!='.','INSTALL_NO_LOCAL_ABSOLUTE_OR_TRAVERSAL')
 return value


def read(path,pin=None):
 p=Path(path);s=p.lstat();need(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode),'INSTALL_CANONICAL_PUBLIC_FILE')
 raw=p.read_bytes()
 if pin is not None:need(sha(raw)==pin,'INSTALL_SOURCE_MANIFEST_OR_LAYOUT_PIN')
 return json.loads(raw)


REQUIRED_PUBLIC={
 'ORIGINAL_FINAL_PROFILE_8530_PUBLIC.json':'8530bb5026d7ad9a77a5aa78a92d9d18426fb97b5236de75ccb6c278ae28aeba',
 'PRODUCTION_PUBLIC_CONTRACT.json':'9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391',
 'CONTRACT_AND_NATIVE_ROLE_DIRECTORY_PINS_PUBLIC.json':'e5a3b28f64b5f423e4ec2c1fee8191204be6b55e3f09222232a5820a7722a08d'}


def install(root,manifest_sha256,output):
 root=Path(root);need(root.is_absolute()and root.resolve()==root and root.is_dir(),'INSTALL_CANONICAL_NEW_SOURCE_ROOT')
 manifest=read(root/'SOURCE_FILES_PUBLIC.json',manifest_sha256)
 need(manifest.get('schema')=='count14-formal-static-source-files-v1'and manifest.get('code_directory')=='CODE'
  and manifest.get('source_only')is True and manifest.get('generated_runtime_inputs_in_source')is False,
  'INSTALL_STATIC_SOURCE_NOT_RUNNING_STATE')
 code=root/'CODE';need(code.resolve()==code and code.is_dir(),'INSTALL_CANONICAL_CODE_ROOT')
 for name,pin in REQUIRED_PUBLIC.items():
  need(name in manifest['files']and manifest['files'][name]['sha256']==pin,'INSTALL_REQUIRED_TOP_CODE_PROFILE_CONTRACT_INDEX')
 actual={str(p.relative_to(code))for p in code.rglob('*')if p.is_file()or p.is_symlink()}
 need(actual==set(manifest['files']),'INSTALL_CODE_IS_STATIC_SOURCE_ONLY_NO_GENERATED_STATE')
 for name,entry in manifest['files'].items():
  p=code/rel(name);s=p.lstat();need(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)
   and s.st_size==entry['bytes']and sha(p.read_bytes())==entry['sha256'],'INSTALL_EXACT_FROZEN_SOURCE_MEMBER')
 layout=read(root/'SOURCE_IMPORT_LAYOUT_PUBLIC.json',manifest['relative_import_layout_sha256'])
 need(layout.get('schema')=='count14-formal-relative-import-layout-v1'and layout.get('code_directory')=='CODE','INSTALL_RELATIVE_LAYOUT_SCHEMA')
 rows=[]
 for row in layout['roots']:
  directory=rel(row['relative_root'],True);path=code if directory=='.'else code/directory
  need(path.resolve()==path and path.is_dir(),'INSTALL_RELOCATED_ROOT_NOT_ALIAS')
  files={}
  for name,pin in row['files'].items():
   rel(name);need(PurePosixPath(name).suffix in('.py','.js','.mjs'),'INSTALL_ORIGINAL_IMPORT_READER_SUFFIX_ONLY')
   key=str(PurePosixPath(directory)/name)
   need(key in manifest['files']and manifest['files'][key]['sha256']==pin,'INSTALL_IMPORT_MEMBER_IN_STATIC_SOURCE')
   files[name]=pin
  need(files,'INSTALL_NONEMPTY_IMPORT_MODULE_SET');rows.append(dict(path=str(path),files=files))
 value=dict(schema='count14-dynteam-framework-import-pins-v1',code_root=str(code),roots=rows)
 output=Path(output);need(output.is_absolute()and output.resolve()==output and not output.is_relative_to(code)
  and output.name.endswith('PUBLIC.json')and not output.exists(),'INSTALL_FRESH_EXTERNAL_REGISTRY_NOT_HASH_CYCLE')
 output.parent.mkdir(mode=0o700,parents=True,exist_ok=True);raw=wire(value)
 fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
 try:
  with os.fdopen(os.dup(fd),'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 finally:os.close(fd)
 guard=manifest['framework_guard'];name=rel(guard['relative_path']);p=code/name
 need(name in manifest['files']and manifest['files'][name]['sha256']==guard['sha256'],'INSTALL_ORIGINAL_GUARD_SOURCE_PIN')
 spec=importlib.util.spec_from_file_location('count14_source_relocated_original_guard',p)
 helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 helper.verify_framework_imports(output,sha(raw),code_root=code)
 return dict(PUBLIC_code='RELOCATED_SOURCE_IMPORT_REGISTRY_PASS',isolated=bool(sys.flags.isolated),
  path=str(output),sha256=sha(raw),code_root=str(code),root_count=len(rows),owner_created=False,
  generated_scopes_or_companion_or_factory_created=False,models=0,source_only=True,formal_delivery=False)


def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--source-manifest-sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 try:
  print(json.dumps(install(a.root,a.source_manifest_sha256,a.output),sort_keys=True));return 0
 except Exception as error:
  frames,tb=[],error.__traceback__
  while tb:frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
  print(json.dumps(dict(PUBLIC_code='SOURCE_IMPORT_INSTALL_REFUSED',exception_type=type(error).__name__,locations=frames),sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
