#!/usr/bin/env python3
"""Same unique original emitter/companion protocol with a private helper path."""
from pathlib import Path
from types import FunctionType
import argparse,hashlib,importlib.util,json,sys
sys.path[:0]=[str(Path(__file__).resolve().parent),
              str(Path(__file__).resolve().parents[1]/'formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1')]

IDLE_EMITTER_SHA='5a4eeaa695fbb70af0974ec283b6b46f7ce708d446bd488a9a56fd1e944d3467'


def need(ok,code):
    if not ok:raise ValueError(code)


def _idle_emitter():
    path=Path(__file__).resolve().parents[1]/'formal100m-idle-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_idle_emit.py'
    need(path.resolve()==path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest()==IDLE_EMITTER_SHA,
         'FORMAL_ACTUALN_EXACT_IDLE_EMITTER_SOURCE_PIN')
    spec=importlib.util.spec_from_file_location('count14_actualn_private_idle_emitter',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
    own=Path(__file__).resolve().parent;idle=_idle_emitter()
    module=idle.private_emitter(tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
    # These are the already inverse-checked private emitter selectors, not
    # source/schema/CLI edits. The generated companion call stays byte-for-byte.
    module._idle_helper_path=own/'formal_actualn_factory.py'
    module._idle_pin_paths=(own/'formal_actualn_factory.py',Path(__file__).resolve(),
        own/'formal_actualn_cold.py',
        own.parent/'formal100m-idle-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_idle_factory.py',
        own.parent/'formal100m-idle-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_idle_emit.py',
        own.parent/'formal100m-public-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-prefix21-v1/formal_public_common.py')
    module._actualn_emitter_proof=dict(original_idle_emitter_sha256=IDLE_EMITTER_SHA,
        original_emitter_AST_proof=module._idle_emitter_proof,
        only_private_helper_and_pinset_bindings_changed=True,
        original_companion_call_and_bindings_schema_unchanged=True)
    return module


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,tester_bindings_sha256=None):
    idle=_idle_emitter();original=idle.emit
    namespace=dict(vars(idle),private_emitter=private_emitter)
    same_emit=FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
    same_emit.__kwdefaults__=original.__kwdefaults__
    value=same_emit(bindings_path,bindings_sha256,destination=destination,
        tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256)
    from formal_public_common import save
    provenance=save(Path(destination)/'ACTUALN_COLD_BINDING_PUBLIC.json',dict(
        schema='count14-formal100m-actualn-cold-factory-WIP-v1',
        cold_order=['outer ensure same-owner allowance control','same original bind_formal_cohort',
            'original watchdog','tester two-point cold plan','actual-n typed source','original retirement plus typed cold aliases'],
        no_new_controller_dispatcher_or_control_ctor_in_terminal_seam=True,
        same_control_all_and_effective_row_ports=True,production_carrier_installer_still_refuses=True,
        actual_natural_point_COMMITTED_and_retirement_binding_qualified=False,
        first_formal_natural_point_K3_remaining=True,models=0,owner_created=False,formal_delivery=False))
    value.update(actualn_cold_provenance=provenance,actualn_cold_source_retirement_hook_implemented=True,
        actualn_runtime_qualification=False,formal_delivery=False)
    return value


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--bindings',required=True);p.add_argument('--bindings-sha256',required=True)
    p.add_argument('--destination',required=True);p.add_argument('--tester-bindings');p.add_argument('--tester-bindings-sha256');a=p.parse_args(argv)
    try:
        print(json.dumps(emit(a.bindings,a.bindings_sha256,destination=a.destination,
            tester_bindings_path=a.tester_bindings,tester_bindings_sha256=a.tester_bindings_sha256),sort_keys=True));return 0
    except Exception as error:
        locations,tb=[],error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FORMAL_ACTUALN_COLD_EMITTER_REFUSED',exception_type=type(error).__name__,locations=locations),sort_keys=True));return 2
if __name__=='__main__':raise SystemExit(main())
