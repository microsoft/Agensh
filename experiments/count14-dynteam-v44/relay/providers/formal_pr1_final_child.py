#!/usr/bin/env python3
"""New isolated provider entry over the exact ORIGINAL formal/natural child.

Preserves all three existing FINAL/allowance/queue parent paths and original
natural import-name selectors. Adds no private config reader or model client.
The original bootstrap authorizes imports before the private options hook.
"""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util,json,os,stat,sys

NATURAL_SHA='f6e32964856b6516342075ae352ea00f23015a7b674facd61306162b9c5f6e66'
APPROVED_SHA='983f8aa0517b895355376a5f41d36b0b907f2cdc86556bc811354ee5740837ed'
OPTIONS_SHA='5d4dd236a30166e7257f6853f4fe7d9cb10c84aa3ebeb337745184910713a1a7'

def need(ok,code):
    if not ok:raise ValueError('MSG220_FORMAL_CHILD_'+code)

def load(path,pin,name):
    p=Path(path);s=p.lstat()
    need(p.is_absolute() and p.resolve()==p and not p.is_symlink() and
         stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid in (0,os.geteuid()) and
         not stat.S_IMODE(s.st_mode)&0o222 and hashlib.sha256(p.read_bytes()).hexdigest()==pin and
         name not in sys.modules,'FROZEN_PRIVATE_ENTRY_SOURCE_AND_SINGLE_IMPORT')
    spec=importlib.util.spec_from_file_location(name,p)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def selected_main(natural,parent,relative,*,install):
    """Preserve complete actual main CodeType, replace only private load port."""
    original_bootstrap=parent.bootstrap
    installed=False
    def bootstrap():
        nonlocal installed
        result=original_bootstrap() # ORIGINAL exact import sets/hash checks first
        if not installed:
            install()
            installed=True
        return result
    parent.bootstrap=bootstrap # this new child-local module instance only
    main=natural.main
    selected=FunctionType(main.__code__,dict(main.__globals__,load_original=lambda:(parent,relative)),
        main.__name__,main.__defaults__,main.__closure__)
    selected.__kwdefaults__=main.__kwdefaults__
    need(selected.__code__ is main.__code__,'ORIGINAL_COMPLETE_NATURAL_MAIN_CODETYPE')
    return selected

def main():
    need(sys.flags.isolated,'ORIGINAL_ISOLATED_CHILD_ONLY')
    home=Path(__file__).resolve().parent;root=home.parent
    approved=load(root/'formal100m-queue-approved-cold-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/approved_queue_child.py',APPROVED_SHA,
        'count14_msg239_original_approved_carrier_child')
    def install():
        options=load(home/'formal_provider_options.py',OPTIONS_SHA,'count14_msg220_formal_AUX_options')
        return options.install(root/'PRODUCTION_PUBLIC_CONTRACT.json')
    return approved.main(after_original_bootstrap=install)

if __name__=='__main__':
    try:raise SystemExit(main())
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        frames=[];tb=error.__traceback__
        while tb:
            frames.append(dict(file=Path(tb.tb_frame.f_code.co_filename).name,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='MSG220_FORMAL_CHILD_BOOTSTRAP_FAILED',exception_type=type(error).__name__,locations=frames)),file=sys.stderr)
        raise SystemExit(2)
