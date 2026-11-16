"""Same original emitter+companion calls; prospective allowance helper only."""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util
ACTUALN_EMITTER_SHA='08d8bb0b8f8530677f5da1ce2b1f77ac9f88bd0cae97b444ac98529c0d0a6328'


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-actualn-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_actualn_emit.py'
    if p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=ACTUALN_EMITTER_SHA:
        raise ValueError('ALLOWANCE_EMITTER_PINNED_NEW_ACTUALN_PARENT')
    spec=importlib.util.spec_from_file_location('count14_allowance_private_actualn_emitter',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
    module=parent().private_emitter(tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
    own=Path(__file__).resolve().parent
    module._idle_helper_path=own/'formal_allowance_factory.py'
    module._idle_pin_paths=tuple(dict.fromkeys((*module._idle_pin_paths,own/'formal_allowance_factory.py',
        own/'formal_allowance_cold.py',Path(__file__).resolve(),
        own.parent/'formal100m-failure-continuation-wip-v1/failure_continuation.py',
        own.parent/'formal100m-failure-continuation-wip-v1/failure_public_projection.py')))
    module._allowance_emitter_proof=dict(parent_actualn_emitter_sha256=ACTUALN_EMITTER_SHA,
        original_helper_pinset_private_selectors_only=True,
        original_companion_schema_calls_and_native_entry_unchanged=True)
    return module


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,tester_bindings_sha256=None):
    module=parent();original=module.emit;space=dict(vars(module),private_emitter=private_emitter)
    fn=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__
    return fn(bindings_path,bindings_sha256,destination=destination,
        tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256)
