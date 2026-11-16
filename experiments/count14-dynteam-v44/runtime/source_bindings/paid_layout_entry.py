#!/usr/bin/env python3
"""Import-only isolated component entry; no whole-owner/runtime activation CLI."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import stat
import sys

OLD_ENTRY_SHA='38bae87b286057b2397b5a4610508a622e82440b2f3a7a661a10d7cf00fd11ae'
FILES={'paid_layout_adopt.py','paid_layout_entry.py','test_paid_layout_OWN.py','qualify_paid_layout.py'}


def read_public(path,pin):
    p=Path(path);s=p.lstat()
    if not (p.is_absolute() and p.resolve()==p and not p.is_symlink() and
            stat.S_ISREG(s.st_mode) and s.st_uid in (0,os.geteuid()) and
            not s.st_mode&0o022 and s.st_nlink==1 and s.st_size<=2*1024*1024):
        raise ValueError('PAID_LAYOUT_ENTRY_EXACT_PUBLIC_SOURCE_FILE')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError('PAID_LAYOUT_ENTRY_EXACT_SOURCE_RAW_PIN')
    return raw


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--component-manifest',required=True)
    p.add_argument('--component-manifest-sha256',required=True)
    p.add_argument('--paid-code-manifest',required=True)
    p.add_argument('--paid-code-manifest-sha256',required=True)
    p.add_argument('--verify-code-only',action='store_true')
    a=p.parse_args(argv)
    try:
        if not a.verify_code_only:
            raise ValueError('PAID_LAYOUT_PRODUCTION_NORMAL_SEAL_AND_RUNTIME_NOT_IMPLEMENTED')
        own=json.loads(read_public(a.component_manifest,a.component_manifest_sha256))
        root=Path(__file__).resolve().parent
        if (own.get('schema')!='count14-paid-layout-component-source-v1' or
            own.get('code_root')!=str(root) or set(own.get('files',{}))!=FILES):
            raise ValueError('PAID_LAYOUT_ENTRY_COMPONENT_SOURCE_MANIFEST')
        for name,pin in own['files'].items():
            read_public(root/name,pin)
        paid=json.loads(read_public(a.paid_code_manifest,a.paid_code_manifest_sha256))
        old=Path(paid['code_root'])/'paid_cold_entry.py'
        read_public(old,OLD_ENTRY_SHA)
        spec=importlib.util.spec_from_file_location('count14_original_paid_layout_import_entry',old)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.load_code(a.paid_code_manifest,a.paid_code_manifest_sha256)
        # -I does not imply the script directory is an import search root.
        # The exact component source was pinned above; bind that explicit path.
        sys.path.insert(0,str(root))
        from paid_layout_adopt import verify_sources,restored_current
        verify_sources();restored_current()
        print(json.dumps(dict(PASS=True,isolated=bool(sys.flags.isolated),
            actual_original_paid_and_layout_classes_imported=True,
            exact_current_one_constant_inverse_verified=True,restore_called=False,
            normal_production_sealer_implemented=False,whole_paid_restore_implemented=False,
            models=0),sort_keys=True));return 0
    except Exception as error:
        locations=[];tb=error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,
                                  function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='PAID_LAYOUT_IMPORT_ONLY_ENTRY_REFUSED',
            exception_type=type(error).__name__,locations=locations,models=0),sort_keys=True));return 2


if __name__=='__main__':
    raise SystemExit(main())
