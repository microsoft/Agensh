"""Current formal exact51/private-config emitter, final HELPER only changed."""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

PIN='11d4f6648c5fb5a537a2721a13cbc1b6c96b251bb5af050ee08ef9da98c6865c'


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-private-config-cold-wip-v2-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_exact_alias_emit.py'
    if p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=PIN:
        raise ValueError('NORMAL_SEALER_CURRENT_EXACT_ALIAS_PRIVATE_CONFIG_EMITTER_PIN')
    spec=importlib.util.spec_from_file_location('count14_normal_sealer_current_formal_emitter',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
    module=parent().private_emitter(tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
    own=Path(__file__).resolve().parent
    if module._idle_helper_path!=own.parent/'formal100m-full-used-domain-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_full_used_factory.py':
        raise ValueError('NORMAL_SEALER_CURRENT_FULLUSED_HELPER_REQUIRED_BEFORE_FINAL_SEAM')
    module._idle_helper_path=own/'normal_sealer_factory.py'
    barrier=own.parent/'formal100m-normal-cold-barrier-wip-v1-msg237-held20-v1-msg237-prefix21-v1'
    module._idle_pin_paths=tuple(dict.fromkeys((*module._idle_pin_paths,*sorted(own.glob('*.py')),
        barrier/'normal_cold_barrier.py',barrier/'normal_cold_barrier_cold.py')))
    return module


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,
         tester_bindings_sha256=None,new_bindings=None):
    module=parent();original=module.emit
    fn=FunctionType(original.__code__,dict(vars(module),private_emitter=private_emitter),
        original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__
    return fn(bindings_path,bindings_sha256,destination=destination,tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256,new_bindings=new_bindings)
