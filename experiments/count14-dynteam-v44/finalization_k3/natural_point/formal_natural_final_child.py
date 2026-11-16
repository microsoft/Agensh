#!/usr/bin/env python3
"""CURRENT original isolated FINAL/allowance child plus typed natural scope.

Only three fixed original framework sources are permitted; all original private
config/input/allowance/header/evaluator/failure handlers remain in that source.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

PARENTS={
 'formal100m-scope-wip-v1/formal_final_child.py':'9bfa1bbb0a5a8b677c956e3d7c0ce577a575f20f569ae0c4ba41417ccf2af0b6',
 'formal100m-allowance-native-wip-v1/allowance_final_child.py':'e4384eeb3f277ef779de76bc1f7998068f9320b46ee109181fc965bc28bfa8af',
 'formal100m-allowance-queue-proposal-v1/queue_child.py':'5c99227268367fb77ceb161968cfe9860733613906c8649ba773e4f759aadf66',
}


def load_original():
    root=Path(__file__).resolve().parents[1]
    path=Path(os.environ.get('COUNT14_NATURAL_PARENT_CHILD',str(root/'formal100m-scope-wip-v1/formal_final_child.py')))
    relative=str(path.relative_to(root))
    if not(path.resolve()==path and not path.is_symlink() and relative in PARENTS and
        hashlib.sha256(path.read_bytes()).hexdigest()==PARENTS[relative] and
        os.environ.get('COUNT14_NATURAL_PARENT_CHILD_SHA256',PARENTS[relative])==PARENTS[relative]):
        raise ValueError('FORMAL_NATURAL_EXACT_CURRENT_ORIGINAL_CHILD_PIN')
    spec=importlib.util.spec_from_file_location('count14_natural_original_final_child',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,relative


def main():
    original,relative=load_original()
    original.bootstrap() # authorize all actual modules before importing them
    from formal_natural_compile import redirect
    if relative.startswith('formal100m-scope-wip-v1/'):
        original.main=redirect(original.main,expected_imports=1,
            old='formal_runtime',new='formal_natural_scope')
    else:
        old='queue_native'if relative.endswith('/queue_child.py')else'allowance_native'
        original.main=redirect(original.main,expected_imports=1,
            old=old,new='formal_natural_child_ports')
    return original.entry()


if __name__=='__main__':
    try:raise SystemExit(main())
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        frames=[];tb=error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FORMAL_NATURAL_CHILD_BOOTSTRAP_FAILED',exception_type=type(error).__name__,locations=frames)),file=sys.stderr)
        raise SystemExit(2)
