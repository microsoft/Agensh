"""Current emitter unchanged code; final helper route and new source pins only."""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

PIN = 'e31280fff899e8ea879b1511df71544d310a23969a046c6424d1481a095034ec'


def parent():
    p = Path(__file__).resolve().parents[1]/'formal100m-normal-cold-sealer-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/normal_sealer_emit.py'
    if p.resolve() != p or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != PIN:
        raise ValueError('NORMAL_TRANSPORT_CHAIN_CURRENT_SEALER_EMITTER_PIN')
    spec = importlib.util.spec_from_file_location('count14_transport_current_normal_sealer_emitter', p)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def private_emitter(*, tester_bindings_path=None, tester_bindings_sha256=None):
    module = parent().private_emitter(tester_bindings_path=tester_bindings_path,
                                    tester_bindings_sha256=tester_bindings_sha256)
    own = Path(__file__).resolve().parent
    if module._idle_helper_path != own.parent/'formal100m-normal-cold-sealer-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/normal_sealer_factory.py':
        raise ValueError('NORMAL_TRANSPORT_CHAIN_CURRENT_SEALER_HELPER_BEFORE_LAST_SEAM')
    module._idle_helper_path = own/'transport_sealer_factory.py'
    transport = own.parent/'formal100m-normal-transport-retirement-wip-v1-msg237-held20-v1-msg237-prefix21-v1/normal_transport_retirement.py'
    bounded = own.parent/'formal100m-normal-sealer-ro-deadline-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1'
    module._idle_pin_paths = tuple(dict.fromkeys((*module._idle_pin_paths,
        *sorted(own.glob('*.py')), transport, bounded/'bounded_metadata_cold.py', bounded/'bounded_metadata_ro.py')))
    return module


def emit(bindings_path, bindings_sha256, *, destination, tester_bindings_path=None,
         tester_bindings_sha256=None, new_bindings=None):
    module = parent(); original = module.emit
    fn = FunctionType(original.__code__, dict(vars(module), private_emitter=private_emitter),
        original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn(bindings_path, bindings_sha256, destination=destination,
        tester_bindings_path=tester_bindings_path, tester_bindings_sha256=tester_bindings_sha256,
        new_bindings=new_bindings)
