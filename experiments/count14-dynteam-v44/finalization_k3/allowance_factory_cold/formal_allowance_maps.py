"""Extend exact prior PUBLIC imports/execution maps with new host-side code.

No new source glob or suffix widening; only explicit new Python source files.
Tester .cjs/protocol pins remain in prior execution map, not import registry.
"""
from pathlib import Path
import hashlib,json
PARENT_IMPORT_SHA='792985c501e56e1bbfa0693ca1ca0a1ae5c107c7280616b51ac35a189347e6f3'
PARENT_EXEC_SHA='fcc9477de275caf057123525ff4c602d7569b928e0a2bf0585fec4ef4774b551'
NAMES=('formal_allowance_cold.py','formal_allowance_factory.py','formal_allowance_emit.py',
    'formal_allowance_maps.py','qualify_allowance_factory.py')


def build(destination):
    from formal_public_factory import base_helper
    from formal_public_common import save
    d=Path(__file__).resolve().parents[1];own=Path(__file__).resolve().parent
    prior=d/'formal100m-actualn-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/maps-wip-v2';guard=base_helper()
    imports=guard.public(prior/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',PARENT_IMPORT_SHA,8*1024*1024)
    guard.verify_framework_imports(prior/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',PARENT_IMPORT_SHA,code_root=d)
    execution=guard.public(prior/'FROZEN_FILES_PUBLIC.json',PARENT_EXEC_SHA,8*1024*1024)
    groups=[(own,NAMES),(d/'formal100m-failure-continuation-wip-v1',('failure_continuation.py','failure_public_projection.py'))]
    roots=[]
    for root,names in groups:
        files={}
        for name in names:
            p=root/name
            if p.resolve()!=p or p.is_symlink()or p.suffix!='.py':raise ValueError('ALLOWANCE_MAP_EXPLICIT_FRAMEWORK_CODE_ONLY')
            raw=p.read_bytes();pin=hashlib.sha256(raw).hexdigest();files[name]=pin
            key=str(p.relative_to(d));entry=dict(bytes=len(raw),sha256=pin)
            if key in execution['files']and execution['files'][key]!=entry:raise ValueError('ALLOWANCE_EXEC_MAP_NO_REWRITE')
            execution['files'][key]=entry
        roots.append(dict(path=str(root),files=files))
    imports['roots']=roots+imports['roots']
    dst=Path(destination);dst.mkdir(mode=0o700)
    return dict(import_registry=save(dst/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',imports),
        execution_map=save(dst/'FROZEN_FILES_PUBLIC.json',execution),
        inherited_import_sha256=PARENT_IMPORT_SHA,inherited_execution_sha256=PARENT_EXEC_SHA,
        explicit_new_execution_sources=sum(len(n)for _,n in groups),import_suffix_policy_unchanged=True)
