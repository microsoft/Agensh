#!/usr/bin/env python3
"""NEW import registry + separate original-schema execution/FROZEN source map.

No existing map is edited. Import suffix policy remains py/js/mjs. Tester cjs
runner and fixed protocol md are execution pins ONLY. Old prompt/assets retain
exact frozen manifest metadata without coordinator opening/hashing their body.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import stat
import sys
sys.path[:0]=[str(Path(__file__).resolve().parent),
              str(Path(__file__).resolve().parents[1]/'formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1')]
from formal_public_common import need,sha,save
from formal_public_factory import base_helper

INHERITED_IMPORT_SHA='3d533547035064c74b143eb6824ded6e3ca924514a8f9809074ddc884b69fc00'
INHERITED_FROZEN_SHA='df40a2f41dd686b3a267b338ad7934fcdcdeebb7808fd0d38b13bab80528396a'
NEW_ROOTS=('formal100m-idle-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1','formal100m-idle-watchdog-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1',
           'formal100m-tester-public-binding-wip-v1-msg237-held20-v1-msg237-prefix21-v1','formal100m-tester-tool-scope-wip-v1-msg237-held20-v1-msg237-testersuffix-v1-msg237-prefix21-v1')
TESTER_EXECUTION={
 'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/smoke_racing_tools_public_exec.py':'573fcdae1a1c847300cfaedbf498f41849a532400600528ebb2bf86223e217ea',
 'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/formal_count14_tester_public.py':'d930818edd3e30d0adf3039b2274a50ec8a83c133fee8b1d35c5ec051aeb78d6',
 'formal100m-tester-public-binding-wip-v1-msg237-held20-v1-msg237-prefix21-v1/formal_tester_public_binding.py':'cce864f6961d96e2135ccc5fa15e7b52fc6537d729761aa3fc77e65581818666',
 'formal100m-tester-public-binding-wip-v1-msg237-held20-v1-msg237-prefix21-v1/PROGRAM_REGISTRATION_PROTOCOL.md':'fb067afe2791ed00c609f42ab3b5aef5acfa759fb8e1218d40595848fe785e51',
 'formal100m-tester-public-binding-wip-v1-msg237-held20-v1-msg237-prefix21-v1/tester-native-runner/smoke_racing_tools_public_runner.cjs':'8c4a1194bd925f730ade182cb7f6e4c2c37844d77b368ba09340f241744f97dc',
}


def build(*,destination):
    own=Path(__file__).resolve().parent;root=own.parent;helper=base_helper()
    inherited_path=root/'formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1/FORMAL_FRAMEWORK_IMPORT_PINS_V2_PUBLIC.json'
    inherited=helper.public(inherited_path,INHERITED_IMPORT_SHA,8*1024*1024)
    need(inherited['code_root']==str(root),'FORMAL_IDLE_SAME_CODE_ROOT_AS_PRIOR_FORMAL_IMPORT_MAP')
    # Exact original reader: do not expand accepted suffixes for an import.
    helper.verify_framework_imports(inherited_path,INHERITED_IMPORT_SHA,code_root=root)
    frozen_path=root/'racing-complete-cold-tree-v4-msg237-held20-v1-msg237-prefix21-v1/FROZEN_FILES_PUBLIC.json'
    frozen=helper.public(frozen_path,INHERITED_FROZEN_SHA,8*1024*1024)
    need(frozen['schema']=='count14-frozen-package-files-v1' and type(frozen['files'])is dict,
         'FORMAL_IDLE_EXACT_ORIGINAL_FROZEN_SOURCE_METADATA_SCHEMA')
    prefix=Path('racing-complete-cold-tree-v4-msg237-held20-v1-msg237-prefix21-v1')
    frozen_files={str(prefix/name):copy.deepcopy(record)for name,record in frozen['files'].items()}
    new=[]
    for name in NEW_ROOTS:
        directory=root/name
        need(directory.resolve()==directory and directory.is_dir() and not directory.is_symlink(),
             'FORMAL_IDLE_EXACT_NEW_FRAMEWORK_ROOT')
        files={}
        for path in sorted(directory.rglob('*')):
            if path.is_dir():
                need(not path.is_symlink(),'FORMAL_IDLE_NO_FRAMEWORK_SYMLINK_DIRECTORY');continue
            if path.suffix not in('.py','.js','.mjs'):continue
            info=path.lstat()
            need(path.resolve()==path and stat.S_ISREG(info.st_mode) and not path.is_symlink() and len(files)<128,
                 'FORMAL_IDLE_BOUNDED_CODE_ONLY_IMPORT_ENUMERATION')
            value=sha(path);files[path.relative_to(directory).as_posix()]=value
            frozen_files[path.relative_to(root).as_posix()]=dict(sha256=value,bytes=info.st_size)
        need(files,'FORMAL_IDLE_NEW_FRAMEWORK_ROOT_NOT_EMPTY')
        new.append(dict(path=str(directory),files=files))
    roots=new+copy.deepcopy(inherited['roots'])
    need(len({r['path']for r in roots})==len(roots),'FORMAL_IDLE_UNIFIED_IMPORT_ROOTS_UNIQUE')
    for row in inherited['roots']:
        directory=Path(row['path']);need(directory.is_relative_to(root),'FORMAL_IDLE_INHERITED_ROOT_SCOPE')
        for name,value in row['files'].items():
            path=directory/name;relative=path.relative_to(root).as_posix()
            if relative in frozen_files:
                need(frozen_files[relative]['sha256']==value,'FORMAL_IDLE_INHERITED_CODE_AND_EXECUTION_MAP_AGREE')
            else:frozen_files[relative]=dict(sha256=value,bytes=path.stat().st_size)
    metadata_compiler=root/'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/racing_public_tool_scope_compile_v1.py'
    need(sha(metadata_compiler)=='6dcf60b98f1fe05e3cc605958e26d17ff5234e4fed003246f3f8c93cbd9be1f7',
         'FORMAL_TESTER_ORIGINAL_PURE_METADATA_COMPILER_PIN')
    frozen_files['runtime-v1-msg237-held20-v1-msg237-prefix21-v1/racing_public_tool_scope_compile_v1.py']=dict(sha256=sha(metadata_compiler),bytes=metadata_compiler.stat().st_size)
    for name,expected in TESTER_EXECUTION.items():
        path=root/name;info=path.lstat()
        need(path.resolve()==path and stat.S_ISREG(info.st_mode) and not path.is_symlink() and sha(path)==expected,
             'FORMAL_IDLE_EXACT_FIVE_TESTER_EXECUTION_SOURCES')
        frozen_files[name]=dict(sha256=expected,bytes=info.st_size)
    dest=Path(destination)
    need(dest.is_absolute() and dest.parent.resolve()==dest.parent and dest.is_relative_to(own) and
         not dest.exists(),'FORMAL_IDLE_NEW_OWN_MAP_DIRECTORY_ONLY')
    dest.mkdir(mode=0o700)
    imports=save(dest/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',dict(schema=inherited['schema'],code_root=str(root),roots=roots))
    execution=save(dest/'FROZEN_FILES_PUBLIC.json',dict(schema=frozen['schema'],files=frozen_files))
    receipt=save(dest/'MAP_PROVENANCE_PUBLIC.json',dict(schema='count14-formal-native-idle-maps-WIP-v1',
        imports=imports,execution_sources=execution,execution_code_root=str(root),prospective_source_anchor_only=True,
        final_package_freeze_or_install_receipt=False,old_import_registry=dict(path=str(inherited_path),sha256=INHERITED_IMPORT_SHA),
        old_frozen_manifest=dict(path=str(frozen_path),sha256=INHERITED_FROZEN_SHA),
        inherited_prompt_asset_bodies_opened_or_hashed=False,original_import_reader_or_suffix_guard_changed=False,
        import_suffixes=['.py','.js','.mjs'],runner_cjs_and_protocol_md_not_import_modules=True,
        tester_execution_sources_sha256=TESTER_EXECUTION,formal_tester_two_cold_factory_seams_implemented=True,
        actual_six_scope_companion_and_public_program_execution_still_unqualified=True,
        real_programs_scopes_and_actual_mounts_still_remaining=True,native_idle_factory_hook=True,
        first_formal_natural_point_K3_remaining=True,zero_live_without_pending_no_forced_spawn=True,
        owner_created=False,models=0,formal_delivery=False))
    return dict(import_registry=imports,frozen_execution_source_map=execution,provenance=receipt,
        roots=len(roots),import_code_pins=sum(len(r['files'])for r in roots),tester_execution_sources=5,
        final_package_freeze_claimed=False,owner_created=False,models=0)


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--destination',required=True);a=p.parse_args(argv)
    try:print(json.dumps(build(destination=a.destination),sort_keys=True));return 0
    except Exception as error:
        locations,tb=[],error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FORMAL_IDLE_MAP_BUILD_REFUSED',exception_type=type(error).__name__,locations=locations),sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
