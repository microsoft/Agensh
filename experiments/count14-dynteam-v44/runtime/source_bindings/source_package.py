"""Static source-only plan/freezer. No generated deployment/scientific state.

Native asset members are pinned, opaque archive bytes, never parsed as task,
candidate, private state or logs. SOURCE layout contains no local absolute root.
"""
from pathlib import Path,PurePosixPath
import hashlib,json,os,re,stat,tarfile

ARCHIVE_SHA='24c318bbf810f9a0366b440c43297b7ecf84195450fa2c261578f0c6031651a1'
IMPORT_SHA='c5e096d292d0ed64382dc638d0654f3ebbba1803067ad3e2a7998033b4c28890'
EXECUTION_SHA='2620c1d49593f55df3f94654831b1469532799b4fa9ae5c7ab419949f2d98d55'
TREE='racing-complete-cold-tree-v4-msg237-held20-v1-msg237-prefix21-v1'
EXCLUSIONS=(
 'formal100m-retirement-wip-v1-msg237-held20-v1-msg237-prefix21-v1/OWN_ORIGINAL_ENTRY_I/count14_native_owner_factory.py',
 'formal100m-tester-public-binding-wip-v1-msg237-held20-v1-msg237-prefix21-v1/OWN_ORIGINAL_ENTRY_I/count14_native_owner_factory.py')
ASSET_PREFIXES=(
 'upstream-70e2ca54/','native-racing/','native-guarded-control-source-v2/',
 'native-clock-overlay-v1/','native-host-orchestration-v4/','racing-guest-code/',
 'original-framework-msg237-held20-v1/','invocation-projector-v1-msg237-held20-v1-msg237-prefix21-v1/','original-v2-dispositions-v1/',
 'original-v2-model-policy-v1/','original-v2-resource-policy-v1/',
 'original-v2-system-probe-v1/','original-v2-resource-observer-v1/')
METADATA={
 'ORIGINAL_FINAL_PROFILE_8530_PUBLIC.json':'8530bb5026d7ad9a77a5aa78a92d9d18426fb97b5236de75ccb6c278ae28aeba',
 'contracts-two-arm-v4/PRODUCTION_PUBLIC_CONTRACT.json':'9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391',
 'contracts-two-arm-v4/CONTRACT_AND_NATIVE_ROLE_DIRECTORY_PINS_PUBLIC.json':'e5a3b28f64b5f423e4ec2c1fee8191204be6b55e3f09222232a5820a7722a08d'}
EXTRA_PROTOCOLS=('formal100m-tester-public-binding-wip-v1-msg237-held20-v1-msg237-prefix21-v1/PROGRAM_REGISTRATION_PROTOCOL.md',)
APPROVED_SOURCE_METADATA={
 'formal100m-allowance-queue-proposal-v1/FILES_AND_DELTA_PUBLIC.json':dict(bytes=2459,sha256='ccf9588789d3f14ea99e82a25a6608c8d45c4c5e4c3d3dacefc68c1d52c42258'),
 'formal100m-allowance-queue-proposal-v1/SQL_DIFF_PUBLIC.json':dict(bytes=2801,sha256='1bf3bbe52f4c486cd0bb977d419c7ea905207a7f4c8fd3296901821be7df3a90')}
GUARD=TREE+'/runtime-v1-msg237-held20-v1/smoke_bootstrap_task_factory.py'
LAYOUT_SCHEMA='count14-formal-relative-import-layout-v1'
SOURCE_SCHEMA='count14-formal-static-source-files-v1'


def need(ok,code):
 if not ok:raise ValueError(code)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def wire(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()


def relative(value,*,root=False):
 need(type(value)is str and value and '\x00'not in value,'SOURCE_RELATIVE_STRING')
 if root and value=='.':return value
 p=PurePosixPath(value)
 need(not p.is_absolute()and '..'not in p.parts and str(p)==value and value!='.',
      'SOURCE_CANONICAL_RELATIVE_LAYOUT_NOT_LOCAL_HOST_PATH')
 return value


def generated(value):
 p=PurePosixPath(value)
 return (any(x.startswith('OWN')or x in('own-evidence','__pycache__','.git','evaluator-private','private-context')for x in p.parts)
  or p.name=='count14_native_owner_factory.py' or p.suffix in('.pkl','.pickle','.sqlite','.log','.stdout','.stderr'))


def pinned_json(path,pin):
 p=Path(path);s=p.lstat()
 need(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and s.st_size<=16*1024*1024,
      'SOURCE_FIXED_PUBLIC_METADATA_REGULAR_BOUNDED')
 raw=p.read_bytes();need(sha(raw)==pin,'SOURCE_PUBLIC_METADATA_PIN');return json.loads(raw)


def relative_import_layout(value,*,original_code_root,explicit_exclusions=()):
 root=PurePosixPath(str(original_code_root));need(root.is_absolute(),'SOURCE_OLD_METADATA_ABSOLUTE_CODE_ROOT')
 need(value.get('schema')=='count14-dynteam-framework-import-pins-v1'and value.get('code_root')==str(root)
      and type(value.get('roots'))is list,'SOURCE_ORIGINAL_IMPORT_SCHEMA')
 allowed=set(explicit_exclusions)
 need(allowed<=set(EXCLUSIONS),'SOURCE_ONLY_TWO_EXACT_APPROVED_OWN_LEAVES_EXCLUDABLE')
 excluded=[];roots=[];files={}
 for row in value['roots']:
  old=PurePosixPath(row['path']);need(old.is_absolute()and old.is_relative_to(root),'SOURCE_IMPORT_ROOT_INSIDE_CODE')
  directory='.' if old==root else relative(str(old.relative_to(root)))
  selected={}
  for name,pin in row['files'].items():
   relative(name);need(PurePosixPath(name).suffix in('.py','.js','.mjs'),'SOURCE_ORIGINAL_IMPORT_SUFFIX_POLICY')
   key=relative(str(PurePosixPath(directory)/name))
   if generated(key):
    need(key in allowed,'SOURCE_UNAPPROVED_GENERATED_IMPORT_MEMBER_REFUSED')
    excluded.append(dict(path=key,original_member_sha256=pin,input_import_registry_sha256=IMPORT_SHA,
      reason='EXACT_PREVIOUSLY_GENERATED_OWN_FACTORY_NOT_SOURCE_MODULE'));continue
   need(key not in files or files[key]==pin,'SOURCE_OVERLAPPING_ROOT_PIN_CONFLICT')
   files[key]=pin;selected[name]=pin
  need(selected,'SOURCE_NO_EMPTY_IMPORT_ROOT')
  roots.append(dict(relative_root=directory,files=selected))
 need({r['path']for r in excluded}==allowed,'SOURCE_EVERY_EXPLICIT_EXCLUSION_MUST_MATCH')
 return dict(schema=LAYOUT_SCHEMA,code_directory='CODE',roots=roots),files,excluded


def build_plan(code_root,archive,*,explicit_exclusions=(),supplements=()):
 d=Path(code_root).resolve();archive=Path(archive)
 maps=d/'formal100m-fixed-code-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/maps-wip-v1'
 imports=pinned_json(maps/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',IMPORT_SHA)
 execution=pinned_json(maps/'FROZEN_FILES_PUBLIC.json',EXECUTION_SHA)['files']
 layout,code,excluded=relative_import_layout(imports,original_code_root=d,explicit_exclusions=explicit_exclusions)
 need(sha(archive.read_bytes())==ARCHIVE_SHA,'SOURCE_EXACT_FROZEN_NATIVE_ARCHIVE')
 with tarfile.open(archive)as tar:
  members=tar.getmembers();need(len({m.name for m in members})==len(members),'SOURCE_ARCHIVE_NO_DUPLICATE_MEMBERS')
  by={relative(m.name):m for m in members}
  need(all(m.isfile()and not m.issym()and not m.islnk()for m in members),'SOURCE_ARCHIVE_REGULAR_ONLY_NO_LINKS')
  inventory=json.loads(tar.extractfile(by['FROZEN_FILES_PUBLIC.json']).read())['files']
  need(set(inventory)==set(by)-{'FROZEN_FILES_PUBLIC.json'},'SOURCE_ARCHIVE_COMPLETE_FROZEN_MEMBER_INDEX')
  selected={}
  def archive_file(name,destination=None,kind='OPAQUE_FROZEN_NATIVE_SOURCE_CLOSURE'):
   relative(name);dest=relative(destination or TREE+'/'+name)
   need(name in inventory and name in by and not generated(dest),'SOURCE_FIXED_ARCHIVE_MEMBER_NOT_GENERATED')
   pin=inventory[name];need(by[name].size==pin['bytes'],'SOURCE_ARCHIVE_MEMBER_SIZE')
   entry=dict(sha256=pin['sha256'],bytes=pin['bytes'],source_kind=kind,archive_member=name,source_mode=by[name].mode)
   if dest in selected:need(selected[dest]['sha256']==entry['sha256'],'SOURCE_DESTINATION_PIN_CONFLICT')
   else:selected[dest]=entry
  for name in inventory:
   if name.startswith(ASSET_PREFIXES):
    archive_file(name)
    archive_file(name,name,'FROZEN_NATIVE_DIRECT_LAYOUT_ROOT_ALIAS')
   if name.startswith('runtime-v1-msg237-held20-v1-msg237-prefix21-v1/')and PurePosixPath(name).suffix in('.py','.js','.mjs','.cjs'):
    # Existing direct loaders resolve CODE/runtime-v1 siblings, not the
    # registered tree/runtime import root. Exact tar whitelist, no local glob.
    archive_file(name,name,'FROZEN_RUNTIME_DIRECT_LOADER_ROOT_ALIAS')
  # All exact frozen production native-role/CLI descriptor bytes, not a
  # guessed subset of prompts/templates. No body of these assets is decoded.
  index_name='contracts-two-arm-v4/CONTRACT_AND_NATIVE_ROLE_DIRECTORY_PINS_PUBLIC.json'
  index=json.loads(tar.extractfile(by[index_name]).read())
  for name,pin in index['files'].items():
   member='contracts-two-arm-v4/'+relative(name)
   need(inventory[member]==pin,'SOURCE_PRODUCTION_ROLE_INDEX_MEMBER_PIN')
   archive_file(member);archive_file(member,member,'FROZEN_PUBLIC_CONTRACT_ROLE_LAYOUT_ALIAS')
  archive_file(index_name);archive_file(index_name,index_name,'FROZEN_PUBLIC_CONTRACT_ROLE_LAYOUT_ALIAS')
  for name,pin in METADATA.items():
   need(inventory[name]['sha256']==pin,'SOURCE_MANDATORY_PROFILE_PRODUCTION_CONTRACT_INDEX_PIN')
   archive_file(name)
  archive_file('ORIGINAL_FINAL_PROFILE_8530_PUBLIC.json','ORIGINAL_FINAL_PROFILE_8530_PUBLIC.json','FROZEN_PUBLIC_PROFILE_TOP_CODE_ALIAS')
  archive_file('contracts-two-arm-v4/PRODUCTION_PUBLIC_CONTRACT.json','PRODUCTION_PUBLIC_CONTRACT.json','FROZEN_PUBLIC_PRODUCTION_CONTRACT_TOP_CODE_ALIAS')
  archive_file(index_name,'CONTRACT_AND_NATIVE_ROLE_DIRECTORY_PINS_PUBLIC.json','FROZEN_PUBLIC_ROLE_INDEX_TOP_CODE_ALIAS')
  archive_file('DYNTEAM_ORIGINAL_SOURCE_PATH_BINDING_PUBLIC.json',kind='FROZEN_PUBLIC_ORIGINAL_ASSET_LOCATOR_UNMODIFIED')
  archive_file('DYNTEAM_ORIGINAL_SOURCE_PATH_BINDING_PUBLIC.json','DYNTEAM_ORIGINAL_SOURCE_PATH_BINDING_PUBLIC.json',kind='FROZEN_PUBLIC_ORIGINAL_ASSET_LOCATOR_ROOT_ALIAS')
  for key,pin in code.items():
   if key.startswith(TREE+'/')and key[len(TREE)+1:]in inventory:
    archive_file(key[len(TREE)+1:])
    need(selected[key]['sha256']==pin,'SOURCE_IMPORT_AND_ARCHIVE_BYTES_MUST_AGREE')
   elif key in selected:need(selected[key]['sha256']==pin,'SOURCE_IMPORT_BYTE_CONFLICT')
   else:
    source=d/key;s=source.lstat();need(source.resolve()==source and stat.S_ISREG(s.st_mode),'SOURCE_LOCAL_REGISTERED_CODE_REGULAR')
    selected[key]=dict(sha256=pin,bytes=s.st_size,source_kind='PINNED_LOCAL_FRAMEWORK_SOURCE',source_relative=key,source_mode=stat.S_IMODE(s.st_mode))
  for key in (*EXTRA_PROTOCOLS,*[name for name in execution if name.endswith('.cjs')]):
   relative(key);need(not generated(key),'SOURCE_PROTOCOL_NOT_GENERATED')
   entry=execution[key]
   if key in selected:need(selected[key]['sha256']==entry['sha256'],'SOURCE_NATIVE_PROTOCOL_PIN_CONFLICT');continue
   s=(d/key).lstat();selected[key]=dict(**entry,source_kind='PINNED_LOCAL_ADAPTER_EXECUTION_PROTOCOL',source_relative=key,source_mode=stat.S_IMODE(s.st_mode))
  # Explicit future natural/SDK roots/files ONLY; never glob or infer science
  # assets or widen the original framework import reader's suffix policy.
  for supplement in supplements:
   need(type(supplement)is dict and set(supplement)=={'relative_root','imports','execution'},'SOURCE_EXPLICIT_SUPPLEMENT_FIELDS')
   root=relative(supplement['relative_root']);need(root.startswith('formal100m-')and not generated(root),'SOURCE_SUPPLEMENT_ONLY_NEW_ADAPTER_ROOT')
   imported={}
   for name,pin in supplement['imports'].items():
    relative(name);need(PurePosixPath(name).suffix in('.py','.js','.mjs'),'SOURCE_SUPPLEMENT_ORIGINAL_IMPORT_SUFFIX')
    imported[name]=pin
   if imported:
    layout['roots'].insert(0,dict(relative_root=root,files=imported))
   else:
    # Only the TWO frozen review/DDL approval-source JSONs needed by the now
    # approved cold installer; no runtime controls or arbitrary metadata port.
    need(root in {r['relative_root']for r in layout['roots']} and
     {root+'/'+n:v for n,v in supplement['execution'].items()}==APPROVED_SOURCE_METADATA,
     'SOURCE_METADATA_ONLY_PORT_EXACT_REGISTERED_ROOT_AND_TWO_APPROVED_STATIC_ANCHORS')
   for name,entry in supplement['execution'].items():
    relative(name);key=relative(root+'/'+name);need(not generated(key),'SOURCE_NO_GENERATED_SUPPLEMENT')
    need(type(entry)is dict and set(entry)=={'sha256','bytes'},'SOURCE_SUPPLEMENT_EXACT_CODE_PIN')
    if name in imported:need(imported[name]==entry['sha256'],'SOURCE_SUPPLEMENT_IMPORT_EXECUTION_PIN_AGREE')
    need(key not in selected,'SOURCE_SUPPLEMENT_NO_HISTORY_REWRITE_OR_OVERLAP')
    s=(d/key).lstat();selected[key]=dict(**entry,source_kind='EXPLICIT_NEW_ADAPTER_SOURCE_SUPPLEMENT'if imported else'PINNED_APPROVED_STATIC_SOURCE_METADATA',source_relative=key,source_mode=stat.S_IMODE(s.st_mode))
   need(set(imported)<=set(supplement['execution']),'SOURCE_SUPPLEMENT_EVERY_IMPORT_HAS_EXECUTION_SOURCE')
  need(GUARD in selected,'SOURCE_ORIGINAL_GUARD_EXPLICITLY_FROZEN')
  selected_members={r['archive_member']for r in selected.values()if 'archive_member'in r}
  omitted=[dict(member=n,sha256=v['sha256'],reason='NOT_NATIVE_SOURCE_OR_FORMAL_IMPORT_OR_PRODUCTION_DESCRIPTOR;HISTORICAL_OR_GENERATED_METADATA_NOT_PORTED')for n,v in inventory.items()if n not in selected_members]
 return dict(schema='count14-formal-static-source-plan-v1',source_only=True,formal_delivery=False,
  native_archive_sha256=ARCHIVE_SHA,input_import_registry_sha256=IMPORT_SHA,input_execution_map_sha256=EXECUTION_SHA,
  code_directory='CODE',layout=layout,files=selected,exclusions=excluded,omitted_archive_members=omitted,
  asset_policy='WHOLE_PINNED_NATIVE_SOURCE_CLOSURE_OPAQUE_NO_PROMPT_SUBSET_GUESS',
  source_asset_or_experiment_roots_changed=False,generated_scopes_companion_factory_phase='AFTER_STATIC_SOURCE_FREEZE_OUTSIDE_CODE',
  framework_guard=dict(relative_path=GUARD,sha256=selected[GUARD]['sha256']),
  actual_Dev4_or_scientific_runtime_qualified=False)


def frozen_mode(mode):
 need(type(mode)is int and mode>=0 and not mode&0o7000,'SOURCE_NO_SPECIAL_MODE_BITS')
 return 0o444|(mode&0o111)


def exclusive(path,raw,mode=0o444):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
 try:
  with os.fdopen(os.dup(fd),'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 finally:os.close(fd)


def freeze(plan,*,code_root,archive,destination):
 need(plan.get('schema')=='count14-formal-static-source-plan-v1','SOURCE_EXACT_PLAN_REQUIRED')
 dst=Path(destination);d=Path(code_root).resolve();archive=Path(archive)
 need(dst.is_absolute()and not dst.exists()and dst.parent.resolve()==dst.parent,'SOURCE_NEW_ABSENT_PACKAGE_ONLY')
 need(sha(archive.read_bytes())==plan['native_archive_sha256']==ARCHIVE_SHA,'SOURCE_ORIGINAL_ARCHIVE_PIN_BEFORE_OPAQUE_COPY')
 dst.mkdir(mode=0o700);(dst/'CODE').mkdir(mode=0o700)
 with tarfile.open(archive)as tar:
  for key,entry in plan['files'].items():
   relative(key);need(not generated(key),'SOURCE_NO_GENERATED_PACKAGE_MEMBERS')
   if 'archive_member'in entry:
    member=tar.getmember(entry['archive_member']);need(member.isfile(),'SOURCE_FIXED_REGULAR_ARCHIVE_MEMBER')
    raw=tar.extractfile(member).read() # opaque original bytes; never parse/print
   else:
    source=d/relative(entry['source_relative']);need(source.resolve()==source and not source.is_symlink(),'SOURCE_EXACT_LOCAL_SOURCE_PATH')
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
     need(stat.S_ISREG(os.fstat(fd).st_mode),'SOURCE_LOCAL_OPAQUE_COPY_REGULAR_FD_NO_FIFO_OR_UNKNOWN_TYPE')
     with os.fdopen(os.dup(fd),'rb')as stream:raw=stream.read(entry['bytes']+1)
    finally:os.close(fd)
   need(len(raw)==entry['bytes']and sha(raw)==entry['sha256'],'SOURCE_PINNED_BYTES_CHANGED')
   exclusive(dst/'CODE'/key,raw,frozen_mode(entry['source_mode']))
 layout=wire(plan['layout']);exclusive(dst/'SOURCE_IMPORT_LAYOUT_PUBLIC.json',layout)
 manifest=dict(schema=SOURCE_SCHEMA,code_directory='CODE',files={key:{k:entry[k]for k in('sha256','bytes')}for key,entry in plan['files'].items()},
  relative_import_layout_sha256=sha(layout),framework_guard=plan['framework_guard'],source_only=True,
  generated_runtime_inputs_in_source=False,formal_delivery=False)
 exclusive(dst/'SOURCE_FILES_PUBLIC.json',wire(manifest))
 exclusive(dst/'SOURCE_EXCLUSIONS_PUBLIC.json',wire(dict(exclusions=plan['exclusions'],input_import_registry_sha256=IMPORT_SHA)))
 return dict(root=str(dst),source_manifest_sha256=sha(wire(manifest)),source_files=len(manifest['files']),formal_delivery=False)
