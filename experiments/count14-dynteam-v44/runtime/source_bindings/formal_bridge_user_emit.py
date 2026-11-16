"""Frozen-source formal emitter selecting the genuine new-root gateway plus approved bridge-USER graph.

No owner, queue, ledger, source asset, Docker action or admission is created by
emission. Templates remain templates; real bindings use the original full
validator and RAM adapter. The original constructor/binder chain is retained.
"""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util
import os
import stat

HERE = Path(__file__).resolve().parent
GATEWAY = ('formal-newroot-bridge-user-cold-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1-msg237-locatorsuffix-v1-msg237-prefix22-v1/formal_bridge_user_cold.py',
           '55612175644f8f7981d769ed4dda154f7070f6ce0cfc1ea536b129f635518035')
_GATEWAY = None


def need(ok, code):
    if not ok:
        raise ValueError(code)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gateway():
    global _GATEWAY
    path = HERE.parent / GATEWAY[0]
    s = path.lstat()
    need(path.resolve() == path and not path.is_symlink() and stat.S_ISREG(s.st_mode)
         and s.st_nlink == 1 and s.st_uid in (0, os.geteuid()) and not s.st_mode & 0o022
         and sha(path) == GATEWAY[1], 'FORMAL_GATEWAY_EMIT_EXACT_NEW_CONSTRUCTOR_PIN')
    if _GATEWAY is None:
        spec = importlib.util.spec_from_file_location('count14_formal_emitted_gateway_graph', path)
        _GATEWAY = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_GATEWAY)
    return _GATEWAY


def previous():
    g = gateway()
    return g.load(HERE.parent / g.PREVIOUS[0], g.PREVIOUS[1], 'count14_gateway_prior_no_reference_emitter')


def select_new_source_module(module, level=0):
    return gateway().select_new_source_module(module, level)


def insert_selection(original):
    parent = previous()
    selected = parent.insert_selection(original)
    before = selected.__code__
    constants = list(before.co_consts)
    rows = [(i, s) for i, s in enumerate(constants) if type(s) is str and
            s.startswith('# Prospective formal SAME-owner factory: import never creates owner.\n')]
    need(len(rows) == 1, 'FORMAL_GATEWAY_EMIT_ONE_ORIGINAL_GENERATED_SOURCE_CONSTANT')
    i, source = rows[0]
    old_path, new_path = str(Path(parent.__file__).resolve()), str(Path(__file__).resolve())
    old_pin, new_pin = gateway().PREVIOUS[1], sha(new_path)
    need(source.count(old_path) == source.count(old_pin) == 1,
         'FORMAL_GATEWAY_EMIT_EXACT_EXISTING_SELECTION_PATH_PIN')
    changed = source.replace(old_path, new_path, 1).replace(old_pin, new_pin, 1)
    need(changed.replace(new_path, old_path, 1).replace(new_pin, old_pin, 1) == source,
         'FORMAL_GATEWAY_EMIT_ONLY_GENERATED_SELECTION_PATH_PIN_BYTE_INVERSE')
    constants[i] = changed
    code = before.replace(co_consts=tuple(constants))
    need(code.co_code == before.co_code and code.replace(co_consts=before.co_consts) == before,
         'FORMAL_GATEWAY_EMIT_ALL_OTHER_ORIGINAL_EXECUTABLE_FIELDS_UNCHANGED')
    value = FunctionType(code, selected.__globals__, selected.__name__, selected.__defaults__, selected.__closure__)
    value.__kwdefaults__ = selected.__kwdefaults__
    return value


def _emit(bindings_path, bindings_sha256, *, destination, tester_bindings_path=None,
          tester_bindings_sha256=None, new_bindings=None):
    g, p = gateway(), previous()
    old = p.load(p.FORMAL)
    top = old.load(old.EMITTER)

    def private_emitter(**kwargs):
        value = top.private_emitter(**kwargs)
        value.emit = insert_selection(value.emit)
        required = (Path(__file__).resolve(), HERE.parent / GATEWAY[0],
                    HERE.parent / g.PREVIOUS[0],
                    *(Path(g.__file__).parent / name for name in g.ORIGINAL_GATEWAY_PINS),
                    *(Path(g.__file__).parent / name for name in g.USER_SOURCES),
                    HERE.parent / g.GATEWAY[0],
                    *(HERE.parent / r[0] for r in (old.RAM, old.TEAM)))
        value._idle_pin_paths = tuple(dict.fromkeys((*value._idle_pin_paths, *required)))
        return value

    fn = old.clone(top.emit, dict(vars(top), private_emitter=private_emitter))
    return fn(bindings_path, bindings_sha256, destination=destination,
              tester_bindings_path=tester_bindings_path, tester_bindings_sha256=tester_bindings_sha256,
              new_bindings=new_bindings)


def emit_template(bindings_path, bindings_sha256, **kwargs):
    from formal_public_factory import base_helper
    need(base_helper().public(bindings_path, bindings_sha256).get('template_only') is True,
         'FORMAL_GATEWAY_TEMPLATE_PATH_NEVER_CLAIMS_REAL_HOST_BINDINGS')
    return _emit(bindings_path, bindings_sha256, **kwargs)


def emit_formal(bindings_path, bindings_sha256, *, ram_bindings_path, **kwargs):
    p = previous()
    old = p.load(p.FORMAL)
    ram = old.load(old.RAM)
    correction = ram.derive_bindings(bindings_path, bindings_sha256,
                                     destination=ram_bindings_path, scope='FORMAL_SIX')
    ref = correction['bindings']
    emitted = _emit(ref['path'], ref['sha256'], **kwargs)
    return dict(original_emission=emitted, prospective_RAM_binding=correction,
                original_full_real_binding_validators_and_binders_retained=True,
                frozen_newroot_gateway_constructor_selected=True,
                frozen_all_native_management_bridges_UID0_scientific_CLI_router_UID10000_selected=True,
                owners_created=0, models=0, formal_delivery=False,
                actual_host_resources_SDK_Tester_K3_smoke_or_activation_qualified=False)
