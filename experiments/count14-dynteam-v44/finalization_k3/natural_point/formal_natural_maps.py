"""New source root only on CURRENT fixed-code framework/execution maps."""
from pathlib import Path
IMPORT_PIN='c5e096d292d0ed64382dc638d0654f3ebbba1803067ad3e2a7998033b4c28890'
EXECUTION_PIN='2620c1d49593f55df3f94654831b1469532799b4fa9ae5c7ab419949f2d98d55'


def build(destination):
    import hashlib
    from formal_public_factory import base_helper
    from formal_public_common import save
    root=Path(__file__).resolve().parent;d=root.parent;previous=d/'formal100m-fixed-code-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/maps-wip-v1'
    guard=base_helper();imports=guard.public(previous/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',IMPORT_PIN,8*1024*1024)
    guard.verify_framework_imports(previous/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',IMPORT_PIN,code_root=d)
    execution=guard.public(previous/'FROZEN_FILES_PUBLIC.json',EXECUTION_PIN,8*1024*1024)
    files={}
    for p in sorted(root.glob('*.py')):
        if p.resolve()!=p or p.is_symlink():raise ValueError('FORMAL_NATURAL_CANONICAL_FRAMEWORK_SOURCE_ONLY')
        raw=p.read_bytes();pin=hashlib.sha256(raw).hexdigest();files[p.name]=pin
        key=str(p.relative_to(d));entry=dict(bytes=len(raw),sha256=pin)
        if key in execution['files']and execution['files'][key]!=entry:raise ValueError('FORMAL_NATURAL_OLD_SOURCE_MAP_UNCHANGED')
        execution['files'][key]=entry
    imports['roots'].insert(0,dict(path=str(root),files=files))
    dst=Path(destination);dst.mkdir(mode=0o700)
    return dict(import_registry=save(dst/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',imports),
        execution_map=save(dst/'FROZEN_FILES_PUBLIC.json',execution),new_roots=1,
        prompt_assets_opened_or_hashed=False,actual_runtime_qualified=False)
