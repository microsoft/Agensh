#!/usr/bin/env python3
"""Map an already-frozen code-only package manifest to exact install paths.

No owner, key, task, container, ledger, source archive or model is opened.
Only listed framework code and its PUBLIC package layout are verified. This is
not a scientific preflight, resource fact or a permission to activate.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import stat


def build(code_root,manifest_sha256):
    root=Path(code_root)
    if not(root.is_absolute() and root.resolve()==root and root.is_dir()):
        raise ValueError('SMOKE_INSTALL_CANONICAL_FROZEN_PACKAGE_ROOT')
    path=root/'FROZEN_FILES_PUBLIC.json';raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest_sha256:
        raise ValueError('SMOKE_INSTALL_FROZEN_MANIFEST_PIN')
    manifest=json.loads(raw);files=manifest['files']
    for name,pin in files.items():
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('SMOKE_INSTALL_RELATIVE_PACKAGE_MEMBERS_ONLY')
        item=root/relative;s=item.lstat()
        if not(stat.S_ISREG(s.st_mode) and not item.is_symlink() and item.resolve()==item and
               not s.st_mode&0o022 and s.st_uid in (0,os.geteuid()) and
               s.st_size==pin['bytes'] and hashlib.sha256(item.read_bytes()).hexdigest()==pin['sha256']):
            raise ValueError('SMOKE_INSTALL_PACKAGE_SOURCE_CHANGED')
    layout=json.loads((root/'PACKAGE_LAYOUT_PUBLIC.json').read_bytes())
    roots=[]
    for prefix in layout['python_import_roots']:
        directory=root/prefix
        selected={str(Path(name).relative_to(prefix)):pin['sha256'] for name,pin in files.items()
                  if Path(name).is_relative_to(prefix) and Path(name).suffix in ('.py','.mjs','.js')}
        if not directory.is_dir() or not selected:
            raise ValueError('SMOKE_INSTALL_COMPLETE_FRAMEWORK_CODE_ROOT')
        roots.append({'path':str(directory),'files':selected})
    value={'schema':'count14-dynteam-framework-import-pins-v1','code_root':str(root),'roots':roots}
    output=root/'FRAMEWORK_IMPORT_PINS_PUBLIC.json'
    raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
    try:
        with os.fdopen(fd,'wb',closefd=False) as out:out.write(raw);out.flush();os.fsync(fd)
        os.fchmod(fd,0o444)
    finally:os.close(fd)
    return {'path':str(output),'sha256':hashlib.sha256(raw).hexdigest(),
            'import_roots':len(roots),'owner_created':False,'models':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--code-root',required=True)
    parser.add_argument('--manifest-sha256',required=True);args=parser.parse_args()
    print(json.dumps(build(args.code_root,args.manifest_sha256),sort_keys=True))
