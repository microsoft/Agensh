"""CURRENT natural source map plus new SDK source/overlay, no old map edit."""
from pathlib import Path
import copy,hashlib
IMPORT_SHA='7a9c7df05fdff4c06fe4c3f332fa03123bdbee1c5e3fa94644ac09e2200b30ab'
EXEC_SHA='04459a361e7b22836e6d6b5202661090a22be12fd19b1b681a5cf1783a1bb845'


def build(destination):
    from formal_public_factory import base_helper
    from formal_public_common import save
    own=Path(__file__).resolve().parent;d=own.parent;old=d/'formal100m-natural-point-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/maps-wip-v3';guard=base_helper()
    imports=guard.public(old/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',IMPORT_SHA,8*1024*1024)
    guard.verify_framework_imports(old/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',IMPORT_SHA,code_root=d)
    execution=guard.public(old/'FROZEN_FILES_PUBLIC.json',EXEC_SHA,8*1024*1024)
    files={}
    paths=[*sorted(own.glob('*.py')),*sorted(own.glob('*.mjs')),*sorted((own/'native-cold-overlay-v3').iterdir())]
    for path in paths:
        if path.suffix not in('.py','.js','.mjs','.json'):continue
        if path.resolve()!=path or path.is_symlink():raise ValueError('SDK_RESTORE_CANONICAL_PUBLIC_CODE_ONLY')
        raw=path.read_bytes();pin=hashlib.sha256(raw).hexdigest();relative=str(path.relative_to(own))
        if path.suffix in('.py','.js','.mjs'):files[relative]=pin
        execution['files'][str(path.relative_to(d))]=dict(bytes=len(raw),sha256=pin)
    imports['roots']=[dict(path=str(own),files=files)]+imports['roots']
    dst=Path(destination)
    if dst.exists()or dst.parent.resolve()!=dst.parent or not dst.is_relative_to(own):raise ValueError('SDK_RESTORE_ABSENT_NEW_MAP_DIRECTORY_ONLY')
    dst.mkdir(mode=0o700)
    return dict(import_registry=save(dst/'FRAMEWORK_IMPORT_PINS_PUBLIC.json',imports),
        execution_map=save(dst/'FROZEN_FILES_PUBLIC.json',execution),roots=len(imports['roots']),
        code_pins=sum(len(r['files'])for r in imports['roots']),final_freeze_or_install_receipt=False)
