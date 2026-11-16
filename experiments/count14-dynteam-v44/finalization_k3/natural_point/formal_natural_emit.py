"""Original current emitter, one natural outer-helper selector only."""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util
PIN='9019f4d218700db3bfc69c59e83b3d752ee53fc4983914a355806bf4e9c05894'


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-fixed-code-factory-cold-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_fixed_code_emit.py'
    if p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=PIN:
        raise ValueError('FORMAL_NATURAL_CURRENT_EMITTER_PARENT_PIN')
    spec=importlib.util.spec_from_file_location('count14_natural_private_fixed_code_emit',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
    m=parent().private_emitter(tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256)
    own=Path(__file__).resolve().parent;m._idle_helper_path=own/'formal_natural_factory.py'
    m._idle_pin_paths=tuple(dict.fromkeys((*m._idle_pin_paths,*sorted(own.glob('*.py')))))
    return m


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,tester_bindings_sha256=None):
    m=parent();original=m.emit;space=dict(vars(m),private_emitter=private_emitter)
    fn=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__
    return fn(bindings_path,bindings_sha256,destination=destination,tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
