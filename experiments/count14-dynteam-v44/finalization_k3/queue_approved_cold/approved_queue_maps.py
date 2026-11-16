"""Exact supplement to SDK4 maps; two approved PUBLIC authority metadata files."""
from pathlib import Path
IMPORT_PIN='cf14ccc38a39f31fa45f445bd40c4edca9e7d80031e1b0aa57beacdb05dc9bc9'
EXECUTION_PIN='4f433a1b16440ea4b63f049c7ebc5902d57b6fc7a6cb630073a2aeaf03016a2f'


def build(destination):
    import hashlib
    from formal_public_factory import base_helper
    from formal_public_common import save
    root=Path(__file__).resolve().parent;d=root.parent;previous=d/'formal100m-sdk-restore-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/maps-wip-v4'
    guard=base_helper();imports=guard.public(previous/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',IMPORT_PIN,8*1024*1024)
    guard.verify_framework_imports(previous/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',IMPORT_PIN,code_root=d)
    execution=guard.public(previous/'FROZEN_FILES_PUBLIC.json',EXECUTION_PIN,8*1024*1024)
    files={}
    for p in sorted(root.glob('*.py')):
        if p.resolve()!=p or p.is_symlink():raise ValueError('APPROVED_CARRIER_CANONICAL_FRAMEWORK_SOURCE_ONLY')
        raw=p.read_bytes();pin=hashlib.sha256(raw).hexdigest();files[p.name]=pin
        key=str(p.relative_to(d));entry=dict(bytes=len(raw),sha256=pin)
        if key in execution['files']and execution['files'][key]!=entry:raise ValueError('APPROVED_CARRIER_OLD_SOURCE_MAP_UNCHANGED')
        execution['files'][key]=entry
    from approved_queue_install import PROPOSAL,SQL_DIFF
    extras={}
    for name,pin in(('FILES_AND_DELTA_PUBLIC.json',PROPOSAL),('SQL_DIFF_PUBLIC.json',SQL_DIFF)):
        p=d/'formal100m-allowance-queue-proposal-v1'/name;raw=p.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('APPROVED_CARRIER_EXACT_APPROVAL_PUBLIC_METADATA_PIN')
        key=str(p.relative_to(d));entry=dict(bytes=len(raw),sha256=pin)
        if key in execution['files']and execution['files'][key]!=entry:raise ValueError('APPROVED_CARRIER_NO_METADATA_OVERWRITE')
        execution['files'][key]=entry;extras[key]=entry
    imports['roots'].insert(0,dict(path=str(root),files=files))
    dst=Path(destination);dst.mkdir(mode=0o700)
    return dict(import_registry=save(dst/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',imports),
        execution_map=save(dst/'FROZEN_FILES_PUBLIC.json',execution),new_roots=1,explicit_PUBLIC_metadata=extras,
        actual_runtime_qualified=False)
