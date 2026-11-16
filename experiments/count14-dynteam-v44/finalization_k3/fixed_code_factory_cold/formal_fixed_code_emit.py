"""Original emitter route with fixed-code outer private helper selector only."""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util
ALLOWANCE_EMITTER_SHA='d5bd9bb1a7537e9481c094e5de62313ce9f2bf0ffa5de8b369b66a07eda7a499'


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-allowance-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_allowance_emit.py'
    if p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=ALLOWANCE_EMITTER_SHA:
        raise ValueError('FIXED_CODE_EMITTER_EXACT_ALLOWANCE_PARENT')
    spec=importlib.util.spec_from_file_location('count14_fixed_code_private_allowance_emitter',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
    m=parent().private_emitter(tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256)
    own=Path(__file__).resolve().parent
    m._idle_helper_path=own/'formal_fixed_code_factory.py'
    m._idle_pin_paths=tuple(dict.fromkeys((*m._idle_pin_paths,own/'formal_fixed_code_factory.py',
        own/'formal_fixed_code_cold.py',Path(__file__).resolve(),
        own.parent/'formal100m-fixed-public-code-wip-v1/fixed_public_code_producer.py')))
    return m


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,tester_bindings_sha256=None):
    m=parent();original=m.emit;space=dict(vars(m),private_emitter=private_emitter)
    fn=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__
    return fn(bindings_path,bindings_sha256,destination=destination,
        tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256)
