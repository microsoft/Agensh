"""Explicit host-only sources on prior import/execution maps; NO OWN fixtures."""
from pathlib import Path
PARENT_IMPORT_SHA='5ba05b19e424a4c374cfcb175f8b968d349fe63a012de0a020c60a5737e0a430'
PARENT_EXEC_SHA='f0f7b1d06028fc5d7ed976cafc5c65d1f3795b7d56b93a38ad4e75a0b9cf76e9'
NAMES=('formal_fixed_code_cold.py','formal_fixed_code_factory.py','formal_fixed_code_emit.py',
 'formal_fixed_code_maps.py','qualify_fixed_code_factory.py')


def build(destination):
    import hashlib
    from formal_public_factory import base_helper
    from formal_public_common import save
    d=Path(__file__).resolve().parents[1];own=Path(__file__).resolve().parent
    prior=d/'formal100m-allowance-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/maps-wip-v1';guard=base_helper()
    imports=guard.public(prior/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',PARENT_IMPORT_SHA,8*1024*1024)
    guard.verify_framework_imports(prior/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',PARENT_IMPORT_SHA,code_root=d)
    execution=guard.public(prior/'FROZEN_FILES_PUBLIC.json',PARENT_EXEC_SHA,8*1024*1024)
    roots=[]
    for root,names in ((own,NAMES),(d/'formal100m-fixed-public-code-wip-v1',('fixed_public_code_producer.py',))):
        files={}
        for name in names:
            p=root/name
            if p.resolve()!=p or p.is_symlink()or p.suffix!='.py':raise ValueError('FIXED_CODE_MAP_FRAMEWORK_ONLY')
            raw=p.read_bytes();pin=hashlib.sha256(raw).hexdigest();files[name]=pin
            key=str(p.relative_to(d));entry=dict(bytes=len(raw),sha256=pin)
            if key in execution['files']and execution['files'][key]!=entry:raise ValueError('FIXED_CODE_MAP_NO_REWRITE')
            execution['files'][key]=entry
        roots.append(dict(path=str(root),files=files))
    imports['roots']=roots+imports['roots'];dst=Path(destination);dst.mkdir(mode=0o700)
    return dict(import_registry=save(dst/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',imports),
        execution_map=save(dst/'FROZEN_FILES_PUBLIC.json',execution),explicit_new_sources=6,
        producer_OWN_fixture_included=False,import_suffix_policy_unchanged=True)
