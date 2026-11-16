#!/usr/bin/env python3
"""Original FINAL child, with qualified alias resolver ahead of original imports."""
from pathlib import Path
import importlib.util,os,sys,hashlib

def main():
    original=Path(os.environ['R16_ORIGINAL_FINAL_ENTRY'])
    expected=os.environ['R16_ORIGINAL_FINAL_ENTRY_SHA']
    if not(original.is_absolute()and original.resolve()==original and original.name=='run_native_final_child.py'
           and hashlib.sha256(original.read_bytes()).hexdigest()==expected):
        raise RuntimeError('R16_ORIGINAL_FINAL_ENTRY_PIN')
    sys.path.insert(1,str(original.parent))
    from common import strict
    config=strict(Path(sys.argv[1]).read_bytes())
    entry=Path(__file__).with_name('run_native_final_child.py') if config.get('replicate_attempt',1)>1 else original
    spec=importlib.util.spec_from_file_location('_r16_original_final_entry',entry)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.main()
if __name__=='__main__':sys.exit(main())
