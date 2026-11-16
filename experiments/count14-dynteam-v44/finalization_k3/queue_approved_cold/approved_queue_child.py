#!/usr/bin/env python3
"""CURRENT original queue child, actual approved reader, original natural ABI.

No OWN authority is accepted by production. Original private config, native
binding/model/header/RNG/evaluator/physical terminal paths remain unchanged.
"""
from pathlib import Path
import hashlib,importlib.util,json,os,sys
NATURAL_CHILD_SHA='f6e32964856b6516342075ae352ea00f23015a7b674facd61306162b9c5f6e66'
QUEUE_CHILD_SHA='5c99227268367fb77ceb161968cfe9860733613906c8649ba773e4f759aadf66'


def main(*, after_original_bootstrap=None):
    d=Path(__file__).resolve().parents[1]
    path=d/'formal100m-natural-point-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_natural_final_child.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=NATURAL_CHILD_SHA:
        raise ValueError('APPROVED_CARRIER_CURRENT_NATURAL_CHILD_SOURCE_PIN')
    q=d/'formal100m-allowance-queue-proposal-v1/queue_child.py'
    os.environ.setdefault('COUNT14_NATURAL_PARENT_CHILD',str(q))
    os.environ.setdefault('COUNT14_NATURAL_PARENT_CHILD_SHA256',QUEUE_CHILD_SHA)
    if os.environ.get('COUNT14_NATURAL_PARENT_CHILD')!=str(q)or os.environ.get('COUNT14_NATURAL_PARENT_CHILD_SHA256')!=QUEUE_CHILD_SHA:
        raise ValueError('APPROVED_CARRIER_EXPLICIT_ORIGINAL_QUEUE_CHILD_ONLY')
    spec=importlib.util.spec_from_file_location('count14_approved_carrier_natural_child',path)
    native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    original,_=native.load_original();original.bootstrap()
    # Registered PR1 wrapper installs transport options only AFTER the
    # complete original import bootstrap, before any original config/job.
    # Direct approved-child execution has no callback and is unchanged.
    if after_original_bootstrap is not None:
        from types import FunctionType
        if type(after_original_bootstrap) is not FunctionType:
            raise ValueError('APPROVED_CARRIER_EXACT_COLD_AFTER_BOOTSTRAP_FUNCTION')
        after_original_bootstrap()
    from formal_natural_compile import redirect
    # Production cold preflight has not built a dispatcher environment yet.
    # Derive only this fixed registered PUBLIC descriptor; never a job/body.
    if 'COUNT14_FORMAL_QUEUE_CONTROL_DOMAIN_PUBLIC'not in os.environ:
        from formal_scope import read_registered_contract
        from common import hash_file
        contract=read_registered_contract(d/'contracts-two-arm-v4/PRODUCTION_PUBLIC_CONTRACT.json')
        descriptor=Path(contract['arms'][0]['root'])/'owner/final-control-carrier-approved-v1/QUEUE_CONTROL_DOMAIN_PUBLIC.json'
        if descriptor.exists()or sys.argv[1:]!=['--verify-imports']:
            os.environ['COUNT14_FORMAL_QUEUE_CONTROL_DOMAIN_PUBLIC']=str(descriptor)
            os.environ['COUNT14_FORMAL_QUEUE_CONTROL_DOMAIN_SHA256']=hash_file(descriptor)['sha256']
    fn=redirect(original.main,expected_imports=1,old='queue_control',new='approved_queue_reader')
    fn=redirect(fn,expected_imports=1,old='queue_native',new='approved_queue_child_ports')
    original.main=fn
    return original.entry()


if __name__=='__main__':
    try:raise SystemExit(main())
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        frames=[];tb=error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='APPROVED_CARRIER_CHILD_BOOTSTRAP_FAILED',exception_type=type(error).__name__,locations=frames)),file=sys.stderr)
        raise SystemExit(2)
