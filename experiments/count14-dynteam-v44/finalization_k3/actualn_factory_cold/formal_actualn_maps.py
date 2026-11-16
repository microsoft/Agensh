#!/usr/bin/env python3
"""Extend exact idle V2 import/execution maps; no old source/map is edited."""
from pathlib import Path
import argparse,copy,hashlib,json,stat,sys
sys.path[:0]=[str(Path(__file__).resolve().parent),
              str(Path(__file__).resolve().parents[1]/'formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1')]
from formal_public_common import need,sha,save
from formal_public_factory import base_helper

IDLE_IMPORT_SHA='9c14cadc7563668d4bca3b4becf56bac19dad757e98f395dc54a8ebb9d83c014'
IDLE_EXECUTION_SHA='dbdae581ac128efa261f2732fefeca8c250a13b294412d119a37631f96a0c479'
NEW_ROOTS=('formal100m-actualn-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1','formal100m-nlt3-wip-v1',
           'formal100m-allowance-native-wip-v1','formal100m-allowance-queue-proposal-v1')


def build(*,destination):
    own=Path(__file__).resolve().parent;root=own.parent;helper=base_helper()
    old=root/'formal100m-idle-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/maps-wip-v2'
    inherited=helper.public(old/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',IDLE_IMPORT_SHA,8*1024*1024)
    helper.verify_framework_imports(old/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',IDLE_IMPORT_SHA,code_root=root)
    execution=helper.public(old/'FROZEN_FILES_PUBLIC.json',IDLE_EXECUTION_SHA,8*1024*1024)
    need(execution['schema']=='count14-frozen-package-files-v1','FORMAL_ACTUALN_ORIGINAL_EXECUTION_MAP_SCHEMA')
    frozen=copy.deepcopy(execution['files']);added=[]
    for name in NEW_ROOTS:
        directory=root/name
        need(directory.resolve()==directory and directory.is_dir() and not directory.is_symlink(),
             'FORMAL_ACTUALN_EXACT_NEW_IMPORT_ROOT')
        files={}
        for path in sorted(directory.rglob('*')):
            if path.is_dir():
                need(not path.is_symlink(),'FORMAL_ACTUALN_NO_CODE_SYMLINK_DIRECTORY');continue
            if path.suffix not in('.py','.js','.mjs'):continue
            info=path.lstat()
            need(path.resolve()==path and stat.S_ISREG(info.st_mode) and not path.is_symlink() and len(files)<128,
                 'FORMAL_ACTUALN_BOUNDED_PUBLIC_CODE_ONLY_IMPORT_ENUMERATION')
            pin=sha(path);files[path.relative_to(directory).as_posix()]=pin
            frozen[path.relative_to(root).as_posix()]=dict(sha256=pin,bytes=info.st_size)
        need(files,'FORMAL_ACTUALN_NONEMPTY_CODE_ROOT');added.append(dict(path=str(directory),files=files))
    roots=added+copy.deepcopy(inherited['roots'])
    need(len({r['path']for r in roots})==len(roots),'FORMAL_ACTUALN_UNIQUE_IMPORT_ROOTS')
    dest=Path(destination)
    need(dest.is_absolute() and dest.parent.resolve()==dest.parent and dest.is_relative_to(own) and
         not dest.exists(),'FORMAL_ACTUALN_NEW_OWN_MAP_DIRECTORY_ONLY')
    dest.mkdir(mode=0o700)
    imports=save(dest/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',dict(schema=inherited['schema'],code_root=str(root),roots=roots))
    sources=save(dest/'FROZEN_FILES_PUBLIC.json',dict(schema=execution['schema'],files=frozen))
    provenance=save(dest/'MAP_PROVENANCE_PUBLIC.json',dict(schema='count14-formal100m-actualn-prospective-maps-v1',
        imports=imports,execution_sources=sources,inherited_idle_import_sha256=IDLE_IMPORT_SHA,
        inherited_idle_execution_sha256=IDLE_EXECUTION_SHA,final_freeze_or_install_receipt=False,
        inherited_prompt_asset_bodies_opened_or_hashed=False,original_import_reader_or_suffix_guard_changed=False,
        source_companion_and_generated_factory_not_in_source_map=True,models=0,owner_created=False,formal_delivery=False))
    return dict(import_registry=imports,frozen_execution_source_map=sources,provenance=provenance,
        roots=len(roots),import_code_pins=sum(len(r['files'])for r in roots),final_freeze_claimed=False)


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--destination',required=True);a=p.parse_args(argv)
    print(json.dumps(build(destination=a.destination),sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
