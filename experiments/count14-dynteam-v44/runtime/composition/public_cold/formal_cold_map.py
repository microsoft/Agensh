#!/usr/bin/env python3
"""NEW prospective import map over exact existing cold bytes + formal adapters.

No old map/package is changed, no full smoke package rebuilt, no task/private
assets read. Original recursive nloop map is inherited, not root.glob('*.py').
Only explicitly registered NEW framework directories are recursively enumerated.
"""
from pathlib import Path, PurePosixPath
import argparse
import copy
import json
import stat
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from formal_public_common import need, sha, save
from formal_public_factory import base_helper

BASE_IMPORTS_SHA = '3ce2c1a9d7d1aa82c2a1a6132cbd2a7581bede9f0ce08416f71312f35c561a1a'
FORMAL_ROOTS = ('formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1', 'formal100m-owner-wip-v1-msg237-held20-v1-msg237-prefix21-v1',
    'formal100m-scope-wip-v1', 'formal100m-terminal-source-wip-v1',
    'formal100m-retirement-wip-v1-msg237-held20-v1-msg237-prefix21-v1')


def build(*, code_root, baseline_registry, baseline_registry_sha256, destination):
    root, dest = Path(code_root), Path(destination)
    need(root.is_absolute() and root.resolve()==root and root.is_dir() and
         dest.is_absolute() and dest.parent.resolve()==dest.parent and dest.is_relative_to(root) and
         not dest.exists() and baseline_registry_sha256==BASE_IMPORTS_SHA,
         'FORMAL_IMPORT_MAP_NEW_CANONICAL_FROZEN_CODE_SCOPE_ONLY')
    helper=base_helper()
    base=helper.public(baseline_registry,baseline_registry_sha256,8*1024*1024)
    need(set(base)=={'schema','code_root','roots'} and base['schema']=='count14-dynteam-framework-import-pins-v1' and
         Path(base['code_root']).is_relative_to(root), 'FORMAL_EXACT_EXISTING_COMPLETE_COLD_MAP_INPUT')
    rows=[]; mutable_WIP_code_files=0
    for name in FORMAL_ROOTS:
        directory=root/name
        need(directory.resolve()==directory and directory.is_dir() and not directory.is_symlink(),
             'FORMAL_EXPLICIT_NEW_FRAMEWORK_ROOT_EXISTS')
        files={}
        # Bounded recursion only within these exact framework-only directories.
        for path in sorted(directory.rglob('*')):
            if path.is_dir():
                need(not path.is_symlink(),'FORMAL_NEW_FRAMEWORK_NO_SYMLINK_DIRECTORY')
                continue
            if path.suffix not in ('.py','.js','.mjs'):
                continue
            info=path.lstat()
            need(path.resolve()==path and not path.is_symlink() and stat.S_ISREG(info.st_mode) and
                 len(files)<128,'FORMAL_NEW_FRAMEWORK_BOUNDED_CODE_ONLY')
            mutable_WIP_code_files += bool(info.st_mode&0o022)
            files[path.relative_to(directory).as_posix()]=sha(path)
        need(files,'FORMAL_NEW_FRAMEWORK_ROOT_NOT_EMPTY')
        rows.append(dict(path=str(directory),files=files))
    for row in base['roots']:
        directory=Path(row['path'])
        need(directory.resolve()==directory and directory.is_dir() and directory.is_relative_to(root),
             'FORMAL_BASE_IMPORT_ROOTS_RETAINED_INSIDE_DECLARED_CODE_SCOPE')
        for name,expected in row['files'].items():
            relative=PurePosixPath(name)
            need(not relative.is_absolute() and '..' not in relative.parts and relative.suffix in ('.py','.mjs','.js'),
                 'FORMAL_BASE_REGISTRY_CODE_ONLY_RECURSIVE_RELATIVE_NAMES')
            path=directory/name
            need(path.resolve()==path and not path.is_symlink() and path.is_file() and sha(path)==expected,
                 'FORMAL_BASE_COLD_BYTE_PIN_UNCHANGED')
        rows.append(copy.deepcopy(row))
    need(len({r['path'] for r in rows})==len(rows),'FORMAL_UNIFIED_IMPORT_ROOTS_UNIQUE')
    nloop=[r for r in rows if any(n.startswith('nloop/') for n in r['files'])]
    need(len(nloop)==1 and 'nloop/game.py' in nloop[0]['files'] and 'nloop/prompts.py' in nloop[0]['files'],
         'FORMAL_RECURSIVE_ORIGINAL_NLOOP_IMPORT_PACKAGE_RETAINED')
    desc=save(dest,dict(schema='count14-dynteam-framework-import-pins-v1',code_root=str(root),roots=rows))
    return dict(schema='count14-formal100m-new-prospective-import-map-v1',descriptor=desc,
        old_registry=dict(path=str(baseline_registry),sha256=baseline_registry_sha256),
        root_count=len(rows),code_file_pin_count=sum(len(r['files'])for r in rows),
        mutable_WIP_code_files=mutable_WIP_code_files, formal_frozen_file_modes_proven=False,
        recursive_nloop_files=len(nloop[0]['files']),original_base_files_changed=False,
        original_code_map_overwritten=False,owner_created=False,models=0,
        future_freeze_requires_fresh_code_hashes=True,formal_runtime_qualification=False,formal_delivery=False)


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--code-root',required=True);p.add_argument('--baseline-registry',required=True)
    p.add_argument('--baseline-registry-sha256',required=True);p.add_argument('--destination',required=True);a=p.parse_args(argv)
    try:
        print(json.dumps(build(code_root=a.code_root,baseline_registry=a.baseline_registry,
            baseline_registry_sha256=a.baseline_registry_sha256,destination=a.destination),sort_keys=True));return 0
    except Exception as error:
        frames,tb=[],error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FORMAL_IMPORT_MAP_REFUSED',exception_type=type(error).__name__,locations=frames),sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
