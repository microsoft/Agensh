"""Preserve a genuine source's already-installed exact control whitelist.

Source fields are sealed by the original native-control supplement. Receiving
metadata is bound only to its genuine T/services/new-stage registry before
original container adoption. No fresh whitelist constructor, empty-source guess,
alias exchange, mount, Docker action or scientific runtime grant is provided.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType, MethodType, FunctionType, CodeType
import copy
import hashlib
import importlib
import os
import stat
import threading

PINS = {
    'native_racing_phase_client': 'c675f876e90e270ed15d2231c2ec278819a1e45f40bd1828ca8b971537c71cc6',
    'native_exact_control_bind': '54ee9dd7eb09268ca86ac6f7ca43153ddc0d1fd5e22572a830801515de166fe2',
    'native_container_retirement': '9cba289507f8fe65da64b75d737595585e08a58241d1badda88effc9f43926a3',
    'financial_runtime_source_control': '5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906',
}
SCHEMA = 'count14-original-frozen-native-control-whitelist-source-v2'
_SEAL = object()
_CAPS = {}
_RESTORES = {}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def _budget(value, core=None):
    from bounded_metadata_ro import ReadBudget
    need(type(value) is ReadBudget, 'CONTROL_WHITELIST_ORIGINAL_FINITE_METADATA_BUDGET')
    value.check()
    if core is not None:
        need(not core.ledger.mutex._is_owned() and not core.queue.mutex._is_owned(),
             'CONTROL_WHITELIST_NO_IO_UNDER_SCIENCE_LOCKS')


def _module(namespace=None):
    # Original newroot binders may load the same frozen module under a private
    # name. Inspect the actual installed function's globals, not a second class.
    m = vars(importlib.import_module('native_exact_control_bind')) if namespace is None else namespace
    need(type(m) is dict and all(type(k) is str for k in m) and
         type(m.get('__file__')) is str and type(m.get('__name__')) is str,
         'CONTROL_WHITELIST_EXACT_BUILTIN_NAMESPACE_AND_SOURCE_NAME')
    p = Path(m['__file__'])
    s = p.lstat()
    need(p.is_absolute() and p.resolve() == p and stat.S_ISREG(s.st_mode) and
         s.st_nlink == 1 and not s.st_mode & 0o022 and
         hashlib.sha256(p.read_bytes()).hexdigest() == PINS['native_exact_control_bind'],
         'CONTROL_WHITELIST_EXACT_ORIGINAL_FROZEN_VALIDATOR_MODULE')
    code = compile(p.read_bytes(), str(p), 'exec', dont_inherit=True)
    functions = {c.co_name: c for c in code.co_consts if hasattr(c, 'co_name')}
    compiler = m.get('compile_validate')
    need(type(compiler) is FunctionType and compiler.__globals__ is m and
         _same_code(compiler.__code__, functions['compile_validate']),
         'CONTROL_WHITELIST_ORIGINAL_COMPILER_NOT_CALLER_FUNCTION')
    cls = functions['FrozenControls']
    methods = {c.co_name: c for c in cls.co_consts if hasattr(c, 'co_name')}
    cls = m.get('FrozenControls')
    need(type(cls) is type and len(cls.__bases__) == 1 and cls.__bases__[0] is object and
         type(cls.__module__) is str and cls.__module__ == m['__name__'],
         'CONTROL_WHITELIST_ORIGINAL_CLASS_NOT_PROXY_OR_CUSTOM_METACLASS')
    need(all(type(k) is str for k in cls.__dict__),
         'CONTROL_WHITELIST_EXACT_BUILTIN_CLASS_KEYS_BEFORE_LOOKUP')
    for name in ('__init__', 'readonly_clocks', 'exact'):
        method = cls.__dict__.get(name)
        need(type(method) is FunctionType and method.__globals__ is m and
             _same_code(method.__code__, methods[name]),
             'CONTROL_WHITELIST_ORIGINAL_CLASS_METHODS_UNCHANGED')
    _closed_namespace(m, functions)
    return m


def _same_code(actual, expected):
    # Same exact-type/closed-namespace discipline as the existing numeric
    # guard. Compare every code field without CodeType.__eq__ or serialization
    # alias-table differences between separately compiled equivalent objects.
    if type(actual) is not CodeType or type(expected) is not CodeType:
        return False
    names = ('co_argcount','co_posonlyargcount','co_kwonlyargcount','co_nlocals',
        'co_stacksize','co_flags','co_code','co_consts','co_names','co_varnames',
        'co_filename','co_name','co_qualname','co_firstlineno','co_linetable',
        'co_exceptiontable','co_freevars','co_cellvars')
    return all(_same_code_value(getattr(actual, name), getattr(expected, name), 0) for name in names)


def _same_code_value(actual, expected, depth):
    if depth > 64 or type(actual) is not type(expected):
        return False
    kind = type(expected)
    if kind is CodeType:
        names = ('co_argcount','co_posonlyargcount','co_kwonlyargcount','co_nlocals',
            'co_stacksize','co_flags','co_code','co_consts','co_names','co_varnames',
            'co_filename','co_name','co_qualname','co_firstlineno','co_linetable',
            'co_exceptiontable','co_freevars','co_cellvars')
        return all(_same_code_value(getattr(actual,n),getattr(expected,n),depth+1) for n in names)
    if kind in (type(None),bool,int,float,complex,str,bytes):
        return actual == expected  # Both operands have EXACT immutable builtin type.
    if kind is tuple:
        return len(actual) == len(expected) and all(_same_code_value(a,b,depth+1) for a,b in zip(actual,expected))
    if kind is frozenset:
        return len(actual) == len(expected) and all(any(_same_code_value(a,b,depth+1) for b in expected) for a in actual)
    return False  # Never dispatch a caller's equality, conversion or iterator.


def _closed_namespace(namespace, functions):
    import ast as original_ast
    import builtins
    import copy as original_copy
    import dataclasses
    import inspect as original_inspect
    import textwrap as original_textwrap
    from common import need as original_need, digest
    from native_peer_registry import process_birth
    from native_container_retirement import alive
    import native_container_retirement as original
    from native_beta_layout import native_aliases
    from native_optional_stop_signal_validator import compile_validate as optional_validate
    canonical = vars(importlib.import_module('native_exact_control_bind'))
    need(type(canonical) is dict and all(type(k) is str for k in canonical) and
         set(namespace) == set(canonical), 'CONTROL_WHITELIST_CLOSED_ORIGINAL_NAMESPACE_KEYS')
    trusted = dict(Path=Path, MappingProxyType=MappingProxyType, MethodType=MethodType,
        dataclass=dataclass, ast=original_ast, copy=original_copy, inspect=original_inspect,
        os=os, stat=stat, textwrap=original_textwrap, need=original_need, digest=digest,
        process_birth=process_birth, alive=alive, original=original,
        native_aliases=native_aliases, optional_validate=optional_validate)
    need(namespace.get('__builtins__') is builtins.__dict__ and
         all(namespace.get(name) is value for name,value in trusted.items()),
         'CONTROL_WHITELIST_CLOSED_ORIGINAL_IMPORTS_AND_GUARD_NAMESPACE')
    for name in ('identity', 'mounted_path', 'compile_validate', 'bind_new_registry'):
        fn = namespace.get(name)
        need(type(fn) is FunctionType and fn.__globals__ is namespace and fn.__closure__ is None and
             fn.__defaults__ is fn.__kwdefaults__ is None and _same_code(fn.__code__, functions[name]),
             'CONTROL_WHITELIST_ORIGINAL_FUNCTION_AND_CLOSED_SOURCE_NAMESPACE')
    expected_constants = dict(APPROVED_PLAN='a89263734bc48884bac7d3fe68e60606e819398a5e6be38484c11d26bd10ee15',
        DESTINATION='/run/count14-dynteam', CLOCK='/run/count14-budget-clock')
    for name,value in expected_constants.items():
        need(type(namespace.get(name)) is str and namespace[name] == value,
             'CONTROL_WHITELIST_ORIGINAL_NAMESPACE_SCOPE_CONSTANTS')
    contracts = namespace.get('CONTRACTS')
    need(type(contracts) is frozenset and all(type(v) is str for v in contracts) and contracts == frozenset((
        'a009fcb9880fe694db540c6c9d8742d5e77ba1ce2314ee3b9018517f42f58e1e',
        '3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937',
        '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391')),
        'CONTROL_WHITELIST_ORIGINAL_APPROVED_CONTRACT_SET')
    cls = namespace['FrozenControls'];reference = canonical['FrozenControls']
    need(all(type(k) is str for k in reference.__dict__) and
         set(cls.__dict__) == set(reference.__dict__) and type(cls.__name__) is str and cls.__name__ == 'FrozenControls' and
         all(cls.__dict__[n].__closure__ is None for n in ('__init__','readonly_clocks','exact')),
         'CONTROL_WHITELIST_ORIGINAL_CLASS_STRUCTURE_AND_CLOSED_METHODS')
    init = cls.__dict__['__init__']
    need(init.__defaults__ is None and type(init.__kwdefaults__) is dict and
         set(init.__kwdefaults__) == {'retained'} and init.__kwdefaults__['retained'] is None and
         all(cls.__dict__[n].__defaults__ is cls.__dict__[n].__kwdefaults__ is None
             for n in ('readonly_clocks','exact')),
         'CONTROL_WHITELIST_ORIGINAL_METHOD_DEFAULTS_NOT_CALLER_OBJECTS')
    # Private original loaders may create a second genuine Entry class. Its
    # generated methods must still be real functions with exact safe code;
    # trusted imported types/constants above remain identity-bound.
    entry = namespace.get('Entry');expected = canonical['Entry']
    need(type(entry) is type and len(entry.__bases__) == 1 and entry.__bases__[0] is object and
         type(entry.__module__) is str and entry.__module__ == namespace['__name__'] and
         type(entry.__name__) is str and entry.__name__ == 'Entry' and
         all(type(k) is str for k in entry.__dict__) and all(type(k) is str for k in expected.__dict__) and
         set(entry.__dict__) == set(expected.__dict__),
         'CONTROL_WHITELIST_ORIGINAL_ENTRY_CLASS_NOT_PLACEHOLDER')
    for name,value in expected.__dict__.items():
        if type(value) is FunctionType:
            actual = entry.__dict__[name]
            need(type(actual) is FunctionType and _same_code(actual.__code__, value.__code__),
                 'CONTROL_WHITELIST_ORIGINAL_ENTRY_GENERATED_METHODS_NOT_CUSTOM_EQUALITY')
    fields = entry.__dict__['__dataclass_fields__']
    params = entry.__dict__['__dataclass_params__']
    need(type(fields) is dict and all(type(k) is str for k in fields) and
         set(fields) == {'source','directory_identity','cid','birth'} and
         all(type(v) is dataclasses.Field for v in fields.values()) and
         type(params) is dataclasses._DataclassParams and params.frozen is True,
         'CONTROL_WHITELIST_ORIGINAL_FROZEN_ENTRY_FIELD_CATALOGUE')


def verify_sources():
    _module()
    for name in ('native_container_retirement', 'financial_runtime_source_control', 'native_racing_phase_client'):
        p = Path(importlib.import_module(name).__file__)
        need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
             hashlib.sha256(p.read_bytes()).hexdigest() == PINS[name],
             'CONTROL_WHITELIST_EXACT_ORIGINAL_DEPENDENCIES')
    return dict(PINS)


def _cell(fn, name):
    need(name in fn.__code__.co_freevars, 'CONTROL_WHITELIST_ORIGINAL_INSTALLED_CLOSURE')
    return fn.__closure__[fn.__code__.co_freevars.index(name)].cell_contents


def _locate(core):
    from original_relay_core import OriginalRelayCore
    from native_container_retirement import NativeContainerRegistry
    registry = core.native_containers
    need(type(core) is OriginalRelayCore and type(registry) is NativeContainerRegistry and
         registry.core is core and type(registry.validate) is MethodType and
         registry.validate.__self__ is registry and 'validate' in vars(registry),
         'CONTROL_WHITELIST_GENUINE_EXISTING_SOURCE_PRIVATE_REGISTRY')
    fn = registry.validate.__func__
    need(type(fn) is FunctionType and type(fn.__code__) is CodeType,
         'CONTROL_WHITELIST_REAL_ORIGINAL_INSTALLED_VALIDATOR_FUNCTION')
    m = _module(fn.__globals__)
    whitelist = _cell(fn, 'whitelist')
    need(type(whitelist) is m['FrozenControls'] and whitelist.core is core and
         whitelist.registry is registry and set(vars(whitelist)) == {
             'core', 'registry', 'contract_sha', 'entries', 'read_only', 'retained', 'clocks', 'live_verified'},
         'CONTROL_WHITELIST_ACTUAL_ORIGINAL_INSTALLED_INSTANCE_NOT_RECONSTRUCTED_EMPTY')
    selected, _ = m['compile_validate'](whitelist)
    old_body, selected_body = _cell(fn, 'body'), _cell(selected, 'body')
    exact = old_body.__globals__.get('_exact')
    need(type(old_body) is type(selected_body) is FunctionType and
         _same_code(fn.__code__, selected.__code__) and _same_code(old_body.__code__, selected_body.__code__) and
         type(exact) is MethodType and exact.__self__ is whitelist and exact.__func__ is m['FrozenControls'].exact,
         'CONTROL_WHITELIST_EXACT_ORIGINAL_FULL_SELECTED_VALIDATOR_AND_BOUND_PREDICATE')
    return whitelist, m


def _directory(path, budget):
    _budget(budget)
    path = Path(path)
    s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and stat.S_ISDIR(s.st_mode),
         'CONTROL_WHITELIST_CANONICAL_DIRECTORY_NOT_PARENT_PREFIX_OR_SYMLINK')
    return [s.st_dev, s.st_ino, s.st_uid, s.st_gid, stat.S_IMODE(s.st_mode)]


def _socket(path, budget):
    _budget(budget)
    path = Path(path)
    s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and stat.S_ISSOCK(s.st_mode),
         'CONTROL_WHITELIST_EXACT_ORIGINAL_SOCKET_INODE_NO_BODY_READ')
    return [s.st_dev, s.st_ino, s.st_uid, s.st_gid, s.st_mode]


def _entry(entry, m, budget):
    from native_peer_registry import ProcessBirth
    need(type(entry) is m['Entry'] and
         (entry.cid is None and entry.birth is None or
          type(entry.cid) is str and len(entry.cid) == 64 and type(entry.birth) is ProcessBirth),
         'CONTROL_WHITELIST_ORIGINAL_ENTRY_WITH_TYPED_RETAINED_CID_FULL_BIRTH')
    identity = _directory(entry.source, budget)
    need(tuple(identity) == entry.directory_identity, 'CONTROL_WHITELIST_SOURCE_DIRECTORY_IDENTITY_DRIFT')
    return dict(source=str(entry.source), directory_identity=identity, cid=entry.cid,
                birth=None if entry.birth is None else asdict(entry.birth))


def _snapshot(core, whitelist, m, budget):
    from common import digest
    from native_container_retirement import ContainerBinding, ContainerBootPlan
    from native_peer_registry import process_birth
    from native_beta_layout import native_aliases
    _budget(budget, core)
    need(whitelist.contract_sha == digest(core.contract) and
         all(type(x) is MappingProxyType for x in (whitelist.entries, whitelist.read_only, whitelist.retained)) and
         type(whitelist.clocks) is frozenset and type(whitelist.live_verified) is dict,
         'CONTROL_WHITELIST_ORIGINAL_FROZEN_MAPS_AND_SAME_CONTRACT')
    expected = {(t, role, component) for t, row in core.rows.items()
                for role in native_aliases(row['arm']) for component in ('agent', 'router')}
    need(set(whitelist.entries) == {k for k in expected if k[2] == 'router'} and
         set(whitelist.read_only) == {k for k in expected if k[2] == 'agent'},
         'CONTROL_WHITELIST_COMPLETE_ORIGINAL_ALL_ROLES_AGENT_RO_ROUTER_RW_CATALOGUE')
    listener = _socket(core.control.path, budget)
    groups = {}
    all_entries = {}
    for name in ('entries', 'read_only', 'retained'):
        rows = []
        for key, entry in sorted(getattr(whitelist, name).items()):
            need(type(key) is tuple and key[:3] in expected and
                 (name != 'retained' and len(key) == 3 and entry.cid is None or
                  name == 'retained' and len(key) == 4 and key[2] == 'router' and key[3] == entry.cid),
                 'CONTROL_WHITELIST_EXACT_REGISTERED_ROLE_OR_RETAINED5199_KEY')
            value = _entry(entry, m, budget)
            need(_socket(entry.source / 'native-control.sock', budget) == listener,
                 'CONTROL_WHITELIST_ALIAS_MUST_NAME_ACTUAL_SOURCE_LISTENER_NOT_STALE_OR_OTHER_SOCKET')
            if name != 'retained':
                export = core.cold_native_exports['trajectories'][key[0]]['role_exports'][key[1]]
                field = 'agent_control_directory' if key[2] == 'agent' else 'router_control_directory'
                need(export[field] == str(entry.source), 'CONTROL_WHITELIST_ORIGINAL_EXPORT_AND_FROZEN_SOURCE_EQUAL')
            rows.append(dict(key=list(key), entry=value));all_entries[key] = entry
        groups[name] = rows
    live = []
    for token, entry in whitelist.live_verified.items():
        need(type(token) is tuple and len(token) == 6 and token[:3] in expected and
             (whitelist.retained.get((*token[:3], token[3])) or whitelist.entries.get(token[:3])) == entry,
             'CONTROL_WHITELIST_ONLY_SOURCE_PRIOR_LIVE_VERIFIED_EXACT_TOKEN_NO_GUESSED_PROOF')
        live.append(dict(key=list(token[:5]), init_birth=asdict(token[5]), entry=_entry(entry, m, budget)))
    registry = whitelist.registry
    bindings = []
    for name, cls in (('records', ContainerBinding), ('boot_plans', ContainerBootPlan)):
        for key, value in sorted(getattr(registry, name).items()):
            _budget(budget)
            need(type(value) is cls and key == (value.trajectory, value.role, value.component) and key in expected,
                 'CONTROL_WHITELIST_EXISTING_HYDRATED_REGISTRY_TYPED_BINDINGS_NO_EMPTY_GUESS')
            bindings.append(dict(kind=name, binding=asdict(value)))
    return dict(schema=SCHEMA, OWN=core.qualification_only, source_owner_birth=asdict(process_birth(os.getpid())),
                contract_sha256=whitelist.contract_sha, owner_home=str(core.home),
                row_controls={t:dict(root=row['root'], arm=row['arm'], roles=list(row['roles']))
                              for t, row in core.rows.items()},
                validator_sha256=PINS['native_exact_control_bind'], listener=dict(path=str(core.control.path), identity=listener),
                source_exports=_source_exports(core, budget),
                groups=groups, clocks=[dict(path=str(p), identity=_directory(p, budget)) for p in sorted(whitelist.clocks)],
                prior_live_verified=live, original_registered_bindings=bindings,
                source_registry_hydrated=bool(registry.records or registry.boot_plans),
                scientific_content_or_route_or_secret_body_read=False, runtime_or_exchange_authority=False)


@dataclass(frozen=True, repr=False)
class CapturedFrozenControls:
    core: object
    whitelist: object
    module: object
    birth: object
    thread: int
    controls: dict
    _seal: object

    def snapshot(self, *, read_budget):
        from native_peer_registry import process_birth
        _budget(read_budget, self.core)
        need(self._seal is _SEAL and _CAPS.get(id(self.core)) is self and
             self.birth == process_birth(os.getpid()) and self.thread == threading.get_ident(),
             'CONTROL_WHITELIST_SAME_LIVE_SOURCE_CAPTURE_BIRTH_AND_THREAD')
        w, m = _locate(self.core)
        need(w is self.whitelist and m is self.module and
             _snapshot(self.core, w, m, read_budget) == self.controls,
             'CONTROL_WHITELIST_ORIGINAL_SOURCE_CAPTURE_STILL_EXACT_NOT_MUTABLE_DICT')
        return copy.deepcopy(self.controls)


def _capture(core, *, read_budget, own):
    verify_sources();_budget(read_budget, core)
    from native_peer_registry import process_birth
    need(core.qualification_only is own and id(core) not in _CAPS and
         (not own or core.home.is_relative_to('/tmp') and any(p.startswith('OWN-') for p in core.home.parts)),
         'CONTROL_WHITELIST_ONCE_PER_ORIGINAL_SOURCE_AND_EXPLICIT_OWN_SCOPE')
    w, m = _locate(core)
    body = _snapshot(core, w, m, read_budget)
    need(_snapshot(core, w, m, read_budget) == body, 'CONTROL_WHITELIST_STABLE_ORIGINAL_SOURCE_FIELDS')
    cap = CapturedFrozenControls(core, w, m, process_birth(os.getpid()), threading.get_ident(), body, _SEAL)
    _CAPS[id(core)] = cap
    return cap


def capture_registered(owner, *, read_budget):
    import financial_runtime_source_control as F
    # No new T issuance or grant: reuse the already-issued original source
    # T/fullbirth/three-lock/storage/normal-retirement verifier before capture.
    F._source(owner, read_budget)
    return _capture(owner.core, read_budget=read_budget, own=False)


def capture_OWN(core, *, read_budget):
    return _capture(core, read_budget=read_budget, own=True)


def _decode_source_RAM(core, registry, body, *, read_budget):
    """Private codec only, NOT a production intake/installer or cap verifier."""
    from common import digest
    from original_relay_core import OriginalRelayCore
    from native_container_retirement import NativeContainerRegistry
    from native_peer_registry import ProcessBirth
    _budget(read_budget, core);m = _module()
    need(type(core) is OriginalRelayCore and type(registry) is NativeContainerRegistry and registry.core is core and
         body['schema'] == SCHEMA and body['validator_sha256'] == PINS['native_exact_control_bind'] and
         body['contract_sha256'] == digest(core.contract) and body['OWN'] is core.qualification_only and
         body['owner_home'] == str(core.home) and body['row_controls'] == {
             t:dict(root=row['root'], arm=row['arm'], roles=list(row['roles'])) for t, row in core.rows.items()} and
         body['runtime_or_exchange_authority'] is False,
         'CONTROL_WHITELIST_CODEC_SAME_ORIGINAL_CONTRACT_ROOTS_AND_ROLE_CATALOGUE')
    need(not registry.records and not registry.boot_plans and not registry.bootstrap_busy and
         'validate' not in vars(registry), 'CONTROL_WHITELIST_CODEC_NEW_REGISTRY_NO_HOT_REPLACEMENT')
    def decode(value):
        path = Path(value['source'])
        need(_directory(path, read_budget) == value['directory_identity'], 'CONTROL_WHITELIST_RECEIVER_PARENT_IDENTITY_DRIFT')
        return m['Entry'](path, tuple(value['directory_identity']), value['cid'],
                          None if value['birth'] is None else ProcessBirth(**value['birth']))
    maps = {}
    for name in ('entries', 'read_only', 'retained'):
        rows = body['groups'][name]
        data = {tuple(r['key']): decode(r['entry']) for r in rows}
        need(len(data) == len(rows), 'CONTROL_WHITELIST_NO_DUPLICATE_OR_DROPPED_SOURCE_ENTRY')
        maps[name] = MappingProxyType(data)
    from native_beta_layout import native_aliases
    expected = {(t, role, component) for t, row in core.rows.items()
                for role in native_aliases(row['arm']) for component in ('agent', 'router')}
    need(set(maps['entries']) == {k for k in expected if k[2] == 'router'} and
         set(maps['read_only']) == {k for k in expected if k[2] == 'agent'} and
         all(len(k) == 4 and k[:3] in expected and k[2] == 'router' and k[3] == v.cid
             for k, v in maps['retained'].items()),
         'CONTROL_WHITELIST_RECEIVE_COMPLETE_SOURCE_WHITELIST_NOT_FRESH_DEFAULTS')
    clocks = set()
    for row in body['clocks']:
        need(_directory(row['path'], read_budget) == row['identity'], 'CONTROL_WHITELIST_RECEIVE_CLOCK_DIRECTORY_DRIFT')
        clocks.add(Path(row['path']))
    need(len(clocks) == len(body['clocks']), 'CONTROL_WHITELIST_NO_DUPLICATE_CLOCK_ENTRY')
    live = {}
    for row in body['prior_live_verified']:
        token = (*row['key'], ProcessBirth(**row['init_birth']))
        entry = decode(row['entry'])
        need(len(token) == 6 and token[:3] in expected and token not in live and
             (maps['retained'].get((*token[:3], token[3])) or maps['entries'].get(token[:3])) == entry,
             'CONTROL_WHITELIST_RECEIVE_ONLY_ORIGINAL_PRIOR_VERIFIED_TOKEN')
        live[token] = entry
    w = object.__new__(m['FrozenControls'])
    w.core, w.registry, w.contract_sha = core, registry, body['contract_sha256']
    w.entries, w.read_only, w.retained = maps['entries'], maps['read_only'], maps['retained']
    w.clocks, w.live_verified = frozenset(clocks), live
    return w


def _regular_identity(path, budget):
    """Stat only: no route/phase-secret body, hash or length is exported."""
    _budget(budget)
    path = Path(path);s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode) and s.st_nlink == 1,
         'CONTROL_WHITELIST_EXACT_ORIGINAL_REGULAR_CONTROL_NODE')
    return [s.st_dev, s.st_ino, s.st_uid, s.st_gid, s.st_mode, s.st_mtime_ns, s.st_ctime_ns]


def _source_exports(core, budget):
    from native_racing_phase_client import NativeRacingPhaseClient
    exports = core.cold_native_exports
    need(exports['state'] == 'EXPORTED_HELD_NOT_DOCKER_OR_SCIENTIFIC_PREPARED' and
         set(exports['trajectories']) == set(core.rows), 'CONTROL_WHITELIST_SOURCE_ORIGINAL_COMPLETE_EXPORTS')
    rows = {}
    for t, row in core.rows.items():
        value = exports['trajectories'][t]
        need(set(value) == {'directory', 'native_roles', 'launcher_route', 'launcher_route_sha256',
                           'project_directory', 'phase_routes', 'role_exports', 'phase_client'} and
             set(value['role_exports']) == set(row['roles']) and value['native_roles'] == len(row['roles']) and
             ((not value['phase_routes'] and value['phase_client'] is None) or
              value['phase_routes'] and type(value['phase_client']) is NativeRacingPhaseClient),
             'CONTROL_WHITELIST_SOURCE_ORIGINAL_EXPORT_FIELDS_NOT_PRIVATE_CLIENT_STATE')
        directory = Path(value['directory'])
        launcher = Path(value['launcher_route'])
        need(launcher == directory/'native-launcher-control/route.json',
             'CONTROL_WHITELIST_ORIGINAL_EXACT_LAUNCHER_ROUTE_METADATA')
        phases = {}
        for role, route in value['phase_routes'].items():
            need(row['arm'] == 'DYNTEAM_RACING' and role in row['roles'] and
                 set(route) == {'socket', 'secret'} and
                 Path(route['socket']) == Path(value['role_exports'][role]['router_control_directory'])/'scientific.sock' and
                 Path(route['secret']) == Path(route['socket']).parent/'phase.secret',
                 'CONTROL_WHITELIST_ORIGINAL_RACING_PHASE_INPUT_PATHS_ONLY')
            phases[role] = dict(route=copy.deepcopy(route), secret_identity=_regular_identity(route['secret'], budget))
        rows[t] = dict(directory=str(directory), directory_identity=_directory(directory, budget),
                       native_roles=value['native_roles'], launcher_route=str(launcher),
                       launcher_route_sha256=value['launcher_route_sha256'],
                       launcher_route_identity=_regular_identity(launcher, budget),
                       project_directory=value['project_directory'], phase_routes=phases,
                       role_exports=copy.deepcopy(value['role_exports']))
    return dict(state=exports['state'], root=exports['root'], root_identity=_directory(exports['root'], budget),
                trajectories=rows, private_phase_client_state_exported=False)


def validate_section(body, *, own, source_birth, contract_sha256, catalogues):
    """Fixed sealed-source field shape. No path read or runtime authority."""
    from native_peer_registry import ProcessBirth
    import re
    need(type(body) is dict and set(body) == {
        'schema', 'OWN', 'source_owner_birth', 'contract_sha256', 'owner_home', 'row_controls',
        'validator_sha256', 'listener', 'groups', 'clocks', 'prior_live_verified', 'original_registered_bindings',
        'source_registry_hydrated', 'scientific_content_or_route_or_secret_body_read',
        'runtime_or_exchange_authority', 'source_exports'} and body['schema'] == SCHEMA and
         body['OWN'] is own and body['source_owner_birth'] == source_birth and
         body['contract_sha256'] == contract_sha256 and
         body['validator_sha256'] == PINS['native_exact_control_bind'] and
         body['scientific_content_or_route_or_secret_body_read'] is body['runtime_or_exchange_authority'] is False and
         set(body['row_controls']) == set(catalogues) and
         all(body['row_controls'][t]['roles'] == catalogues[t] for t in catalogues),
         'CONTROL_WHITELIST_SEALED_FIELD_SHAPE_AND_ORIGINAL_BIRTH_CONTRACT_ROSTER')
    ProcessBirth(**body['source_owner_birth'])
    expected = {(t, role, component) for t, roles in catalogues.items() for role in roles
                for component in ('agent', 'router')}
    need(type(body['groups']) is dict and set(body['groups']) == {'entries', 'read_only', 'retained'},
         'CONTROL_WHITELIST_THREE_ORIGINAL_FROZEN_MAP_DOMAINS')
    for name in ('entries', 'read_only', 'retained'):
        seen = set()
        component = 'router' if name == 'entries' else 'agent'
        need(type(body['groups'][name]) is list, 'CONTROL_WHITELIST_FIXED_ENTRY_LIST')
        for row in body['groups'][name]:
            need(type(row) is dict and set(row) == {'key', 'entry'} and type(row['key']) is list,
                 'CONTROL_WHITELIST_FIXED_ENTRY_KEY_FIELDS')
            key = tuple(row['key']);entry = row['entry']
            need(key not in seen and key[:3] in expected and type(entry) is dict and
                 set(entry) == {'source', 'directory_identity', 'cid', 'birth'} and
                 type(entry['source']) is str and Path(entry['source']).is_absolute() and
                 type(entry['directory_identity']) is list and len(entry['directory_identity']) == 5 and
                 all(type(v) is int for v in entry['directory_identity']),
                 'CONTROL_WHITELIST_UNIQUE_TYPED_ORIGINAL_ENTRY_FIELDS')
            if name == 'retained':
                need(len(key) == 4 and key[2] == 'router' and key[3] == entry['cid'] and
                     type(entry['cid']) is str and re.fullmatch('[0-9a-f]{64}', entry['cid']),
                     'CONTROL_WHITELIST_RETAINED_EXACT_CID_FIELD')
                ProcessBirth(**entry['birth'])
            else:
                need(len(key) == 3 and key[2] == component and entry['cid'] is entry['birth'] is None,
                     'CONTROL_WHITELIST_ORIGINAL_COMPONENT_READONLY_AND_DYNAMIC_CID_DOMAIN')
            seen.add(key)
        if name != 'retained':
            need(seen == {k for k in expected if k[2] == component},
                 'CONTROL_WHITELIST_COMPLETE_SOURCE_ROLE_CATALOGUE_NO_EMPTY_DEFAULT')
    exports = body['source_exports']
    need(type(exports) is dict and set(exports) == {
        'state', 'root', 'root_identity', 'trajectories', 'private_phase_client_state_exported'} and
         exports['state'] == 'EXPORTED_HELD_NOT_DOCKER_OR_SCIENTIFIC_PREPARED' and
         exports['private_phase_client_state_exported'] is False and set(exports['trajectories']) == set(catalogues),
         'CONTROL_WHITELIST_COMPLETE_SECRET_FREE_SOURCE_EXPORT_INPUTS')
    for t, roles in catalogues.items():
        row = exports['trajectories'][t]
        need(type(row) is dict and set(row) == {'directory', 'directory_identity', 'native_roles', 'launcher_route',
             'launcher_route_sha256', 'launcher_route_identity', 'project_directory', 'phase_routes', 'role_exports'} and
             row['native_roles'] == len(roles) and set(row['role_exports']) == set(roles),
             'CONTROL_WHITELIST_ORIGINAL_EXPORT_ROLE_METADATA_COMPLETE')
    return True


def source_fields(core, *, owner, own, read_budget):
    """Called inside the original issuer's same live source control capture."""
    _budget(read_budget, core)
    if not own:
        import financial_runtime_source_control as F
        need(owner is not None and owner.core is core, 'CONTROL_WHITELIST_ORIGINAL_SOURCE_OWNER_NOT_CALLER_PATH')
        F._source(owner, read_budget)
    value = _CAPS.get(id(core))
    if value is None:
        value = _capture(core, read_budget=read_budget, own=own)
    need(value.core is core and value.controls['OWN'] is own,
         'CONTROL_WHITELIST_SAME_SOURCE_CAPTURE_NO_REPLACEMENT_OR_SECOND_ATTEMPT')
    fields = value.snapshot(read_budget=read_budget)
    validate_section(fields, own=own, source_birth=fields['source_owner_birth'],
                     contract_sha256=fields['contract_sha256'],
                     catalogues={t:list(r['roles']) for t,r in core.rows.items()})
    return fields


def _restore_exports_RAM(core, body, *, read_budget):
    """Only original input paths; original phase constructor keeps secrets RAM-only."""
    from native_racing_phase_client import NativeRacingPhaseClient
    raw = body['source_exports']
    need(_directory(raw['root'], read_budget) == raw['root_identity'],
         'CONTROL_WHITELIST_SOURCE_EXPORT_ROOT_STILL_EXACT')
    exports = dict(state=raw['state'], root=raw['root'], trajectories={})
    for t, value in raw['trajectories'].items():
        need(_directory(value['directory'], read_budget) == value['directory_identity'] and
             _regular_identity(value['launcher_route'], read_budget) == value['launcher_route_identity'],
             'CONTROL_WHITELIST_SOURCE_EXPORT_DIRECTORY_AND_LAUNCHER_UNCHANGED')
        routes = {}
        for role, phase in value['phase_routes'].items():
            need(_regular_identity(phase['route']['secret'], read_budget) == phase['secret_identity'],
                 'CONTROL_WHITELIST_ORIGINAL_PHASE_CONTROL_FILE_IDENTITY_UNCHANGED')
            routes[role] = copy.deepcopy(phase['route'])
        client = NativeRacingPhaseClient(routes=routes,
            native_secret_owner_uid=os.geteuid() if core.qualification_only else 10000) if routes else None
        # The ORIGINAL trusted constructor above may read the original phase
        # secret only into RAM. Nothing from client.routes is exported/copied.
        for phase in value['phase_routes'].values():
            need(_regular_identity(phase['route']['secret'], read_budget) == phase['secret_identity'],
                 'CONTROL_WHITELIST_PHASE_FILE_STABLE_ACROSS_ORIGINAL_PRIVATE_CONSTRUCTOR')
        exports['trajectories'][t] = dict(directory=value['directory'], native_roles=value['native_roles'],
            launcher_route=value['launcher_route'], launcher_route_sha256=value['launcher_route_sha256'],
            project_directory=value['project_directory'], phase_routes=routes,
            role_exports=copy.deepcopy(value['role_exports']), phase_client=client)
    return exports


def bind_registered_receiver(graph, registry, *, capability, read_budget):
    """New metadata only, after genuine original T/services capability verification.

    No CID registration, alias mutation, peer launch or scientific unquarantine.
    Original caller must subsequently validate actual mounted parents/CID/scopes.
    """
    import native_control_source_supplement as S
    import new_owner_host_control as H
    from native_container_retirement import NativeContainerRegistry
    from native_docker_scope import ScopedDocker
    from native_peer_registry import process_birth
    from common import digest
    verify_sources()
    need(type(capability) is S.VerifiedNativeSourceControls and S._VERIFIED.get(id(capability)) is capability,
         'CONTROL_WHITELIST_ONLY_REGISTERED_ORIGINAL_VERIFIED_NATIVE_SOURCE_CAP')
    need(H.registered_stage_host_graph(graph.stage) is graph and
         capability.source_owner is graph.registration.source_owner and
         capability.source_ticket is graph.registration.source_ticket and
         capability.old_owner_birth == graph.registration.old_owner_birth == graph.stage.old_owner_birth and
         capability.new_owner_birth == graph.registration.new_owner_birth == graph.stage.new_owner_birth == process_birth(os.getpid()) and
         capability.contract_sha256 == digest(graph.core.contract) and
         tuple(capability.lock_fds) == tuple(graph.stage.context.lock_fds),
         'CONTROL_WHITELIST_ONLY_REAL_ORIGINAL_T_SERVICES_NEW_STAGE_CAPABILITY_NOT_DICT_OR_OWN')
    core = graph.core
    _budget(read_budget, core)
    need(core.gate.closed and not core.gate.waiters and set(core.gate.startup_held) == set(core.rows) and
         type(registry) is NativeContainerRegistry and registry.core is core and core.native_containers is registry and
         type(registry.docker) is ScopedDocker and registry.docker.route.qualification_only is False and
         not registry.records and not registry.boot_plans and not registry.bootstrap_busy and
         'validate' not in vars(registry) and id(graph) not in _RESTORES and not hasattr(core, 'cold_native_exports'),
         'CONTROL_WHITELIST_ONE_NEW_HELD_REGISTRY_BEFORE_FIRST_ADOPTION_NO_LIVE_PATCH')
    fields = capability.snapshot()['original_frozen_control_whitelist']
    validate_section(fields, own=False, source_birth=asdict(capability.old_owner_birth),
        contract_sha256=capability.contract_sha256, catalogues={t:list(r['roles']) for t,r in core.rows.items()})
    source_bindings = {}
    for row in fields['original_registered_bindings']:
        value = row['binding'];key = value['trajectory'], value['role'], value['component']
        need(key not in source_bindings and row['kind'] in ('records', 'boot_plans'),
             'CONTROL_WHITELIST_SOURCE_BINDINGS_NO_AMBIGUOUS_REGISTRATION')
        source_bindings[key] = value
    adopted = set()
    for retained in graph.registration.source_registration.retained_containers:
        c = retained.source_component;value = source_bindings.get(retained.key)
        need(value is not None and value['cid'] == c.cid and value['image_id'] == c.image_id and
             value['init_birth'] == asdict(c.init_birth),
             'CONTROL_WHITELIST_ORIGINAL_SDK_SOURCE_COMPONENT_AND_NATIVE_REGISTRY_MUST_AGREE')
        adopted.add(retained.key)
    record = dict(graph=graph, capability=capability, state='PARTIAL_RETAINED_NO_RETRY')
    record['source_registered_bindings'] = copy.deepcopy(fields['original_registered_bindings'])
    record['not_yet_resolved_source_binding_keys'] = sorted(set(source_bindings) - adopted)
    _RESTORES[id(graph)] = record;graph.native_control_whitelist_restore = record
    w = _decode_source_RAM(core, registry, fields, read_budget=read_budget)
    record['whitelist'] = w
    exports = _restore_exports_RAM(core, fields, read_budget=read_budget)
    record['exports'] = exports
    m = _module();validate, inverse = m['compile_validate'](w)
    core.cold_native_exports = exports
    registry.validate = MethodType(validate, registry)
    graph.native_control_whitelist = w
    record['state'] = 'SOURCE_WHITELIST_AND_EXPORT_METADATA_BOUND_NOT_IPC_RECONNECTED'
    record['inverse'] = inverse
    graph.unresolved.append('ORIGINAL_NATIVE_EXPORT_SOCKET_REBIND_NOT_YET_QUALIFIED')
    if record['not_yet_resolved_source_binding_keys']:
        graph.unresolved.append('SOURCE_NATIVE_REGISTRY_BINDINGS_WITHOUT_RESOLVED_ORIGINAL_SDK_COMPONENT')
    return w
