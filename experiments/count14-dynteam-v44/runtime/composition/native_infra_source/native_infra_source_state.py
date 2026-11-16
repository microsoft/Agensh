"""Original native infrastructure control provenance, not a launch/adoption API.

SOURCE must be the genuine original T/services issuer. Receiver must have the
genuine independently verified native-source capability and new held graph.
Only fixed framework-control fields and inode metadata are transferred. Private
envfile/route bodies, scientific files, Popen handles and memory readers are not.
No mkdir/chown/UP/TERM, financial grant, scientific release or alias exchange.
"""
from dataclasses import asdict
from pathlib import Path
from types import CodeType, MethodType, FunctionType, ModuleType
import copy
import builtins
import json
import subprocess
import time
import traceback
import hashlib
import importlib
import os
import re
import shlex
import stat

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import ProcessBirth, process_birth
from native_cold_bootstrap import NativeColdBootstrap, mem_available
from native_layout import NativeLayout, native_names
from native_beta_layout import native_aliases
from native_host_environment import INFRA, infra_labels
from common import need as _original_need, digest as _original_digest
from original_relay_core import OriginalRelayCore

SCHEMA = 'count14-original-native-infra-layout-host-source-v1'
STATE = 'ORIGINAL_SOURCE_NATIVE_INFRA_LAYOUT_HOST_CONTROLS'
PINS = dict(
    native_cold_bootstrap='4fd79b6272cb55c6dded4217d467bc734a8881a0c85b4fd92b45868b3ce78d6a',
    native_host_environment='a4c7d84cd2226372a9e94e978b9f9f21e6957d68f035209484cc1e69507e209b',
    native_layout='05a002bed1250bf98c5f9aab52f285bb2960dc3f5b058f1eead66b68ca698388',
    native_peer_registry='0986b61a7c71b6745442b9c71dfc67d79eebf960a50523ea1e2b5ee0f37d019d',
    native_beta_layout='92a22647dc030a222f053b1ee6d6a0a0f673f617b49b234ca9382790a7be055a',
)
LAUNCH_KEYS = frozenset((
    'COUNT14_NATIVE_MAKE', 'COUNT14_NATIVE_PROFILE', 'COUNT14_NATIVE_ENV_FILE',
    'COUNT14_NATIVE_COMPOSE_BASE', 'COUNT14_NATIVE_COMPOSE_COMMAND',
    'COUNT14_NATIVE_PYTHON', 'COUNT14_NATIVE_SPAWN_CLIENT', 'COUNT14_NATIVE_SPAWN_ROUTE',
    'COUNT14_NATIVE_SPAWN_ROUTE_SHA256', 'COUNT14_NATIVE_DOCKER', 'COUNT14_NATIVE_DOCKER_SOCKET',
))
HOST_KEYS = frozenset(('profile', 'data_root', 'envfile', 'compose', 'launcher_env',
                       'spawn_source', 'project_root', 'initial_roles', 'infra_services', 'image_ids'))
BLOCK_BOOT = ('start', 'start_initial', '_initial', '_spawn', '_receipt', '_infra_ready',
              '_resources', '_held', 'step')
_SEAL = object()
_RESTORES = {}


def _budget(value, core=None):
    M.need(type(value) is ReadBudget, 'NATIVE_INFRA_SOURCE_FINITE_METADATA_BUDGET')
    value.check()
    if core is not None:
        M.need(not core.ledger.mutex._is_owned() and not core.queue.mutex._is_owned(),
               'NATIVE_INFRA_SOURCE_NEVER_CONTROL_IO_UNDER_SCIENCE_LOCKS')


def _sha(value):
    M.need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'NATIVE_INFRA_SOURCE_SHA_CONTROL')
    return value


def _plain(value, depth=0):
    """Closed builtin JSON/control graph; never invoke caller conversion hooks."""
    M.need(depth < 100, 'NATIVE_INFRA_SOURCE_FINITE_BUILTIN_CONTROL_GRAPH')
    if type(value) in (str, int, bool, type(None)):
        return value
    if type(value) in (tuple, list):
        return [_plain(v, depth + 1) for v in value]
    M.need(type(value) is dict and all(type(k) is str for k in value), 'NATIVE_INFRA_SOURCE_ONLY_BUILTIN_CONTROL_FIELDS')
    return {k: _plain(v, depth + 1) for k, v in value.items()}


def _birth(value):
    M.need(type(value) is dict and set(value) == set(ProcessBirth.__dataclass_fields__) and
           type(value['boot_id']) is str and all(type(v) is int and v >= 0
           for k, v in value.items() if k != 'boot_id') and value['pid'] > 0 and value['start_ticks'] > 0,
           'NATIVE_INFRA_SOURCE_EXACT_FULL_PROCESS_BIRTH')
    return ProcessBirth(**value)


def _path(value):
    M.need(type(value) is str and value and '\0' not in value and '\n' not in value and
           Path(value).is_absolute(), 'NATIVE_INFRA_SOURCE_ABSOLUTE_CONTROL_PATH')
    return Path(value)


def _node(path, budget, directory):
    _budget(budget)
    p = Path(path); s = p.lstat()
    M.need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
           (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode) and s.st_nlink == 1),
           'NATIVE_INFRA_SOURCE_CANONICAL_EXACT_CONTROL_NODE')
    # No private file size/body/hash: only registered inode metadata.
    return ([s.st_dev, s.st_ino, s.st_uid, s.st_gid, stat.S_IMODE(s.st_mode)] if directory else
            [s.st_dev, s.st_ino, s.st_uid, s.st_gid, s.st_mode, s.st_mtime_ns, s.st_ctime_ns])


def _same_code_value(actual, expected, depth=0):
    # Do NOT use CodeType.__eq__: co_consts may contain a caller object whose
    # equality runs code. Every node has an exact closed builtin type first.
    if depth > 64 or type(actual) is not type(expected):
        return False
    if type(expected) is CodeType:
        names = ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals',
                 'co_stacksize', 'co_flags', 'co_code', 'co_consts', 'co_names', 'co_varnames',
                 'co_filename', 'co_name', 'co_qualname', 'co_firstlineno', 'co_linetable',
                 'co_exceptiontable', 'co_freevars', 'co_cellvars')
        return all(_same_code_value(getattr(actual, n), getattr(expected, n), depth + 1) for n in names)
    if type(expected) in (type(None), bool, int, float, complex, str, bytes):
        return actual == expected
    if type(expected) is tuple:
        return len(actual) == len(expected) and all(_same_code_value(a, b, depth + 1) for a, b in zip(actual, expected))
    if type(expected) is frozenset:
        return len(actual) == len(expected) and all(any(_same_code_value(a, b, depth + 1) for b in expected) for a in actual)
    return False


def _method_identity(fn, code, module, *, memory_reader_default=False):
    # Exact FunctionType must precede EVERY attribute lookup on fn. The RAM
    # counterfeit from OPS1826 must not even have its __code__ getter called.
    if type(fn) is not FunctionType or type(code) is not CodeType or type(module) is not ModuleType:
        return False
    if not (type(fn.__code__) is CodeType and _same_code_value(fn.__code__, code) and
            fn.__globals__ is vars(module) and fn.__defaults__ is None and fn.__closure__ is None and
            type(fn.__annotations__) is dict and not fn.__annotations__ and not fn.__dict__):
        return False
    if memory_reader_default:
        kw = fn.__kwdefaults__
        return type(kw) is dict and all(type(k) is str for k in kw) and set(kw) == {'memory_reader'} and kw['memory_reader'] is None
    return fn.__kwdefaults__ is None


def _namespace_bindings(namespace, expected):
    metadata = {'__name__', '__doc__', '__package__', '__loader__', '__spec__', '__file__', '__cached__', '__builtins__'}
    return (type(namespace) is dict and all(type(k) is str for k in namespace) and
            namespace.get('__builtins__') is builtins.__dict__ and
            set(namespace) - metadata == set(expected) and
            all(namespace.get(name) is value for name, value in expected.items()))


def _class_methods(cls, module, original, *, bootstrap):
    M.need(type(cls) is type and type(module) is ModuleType and len(cls.__bases__) == 1 and cls.__bases__[0] is object and
           type(cls.__module__) is str and cls.__module__ == module.__name__ and
           all(type(k) is str for k in cls.__dict__), 'NATIVE_INFRA_SOURCE_EXACT_ORIGINAL_CLASS_SHAPE')
    methods = {v.co_name: v for v in original.co_consts if type(v) is CodeType}
    M.need(set(cls.__dict__) == {'__module__', '__dict__', '__weakref__', '__doc__', *methods},
           'NATIVE_INFRA_SOURCE_CLOSED_ORIGINAL_CLASS_METHOD_NAMES')
    for name, code in methods.items():
        M.need(_method_identity(cls.__dict__[name], code, module,
               memory_reader_default=bootstrap and name == '__init__'),
               'NATIVE_INFRA_SOURCE_EXACT_FUNCTION_CODE_DEFAULTS_CLOSURE_GLOBALS')


def verify_sources():
    modules = {}
    for name, pin in PINS.items():
        module = importlib.import_module(name)
        M.need(type(module) is ModuleType, 'NATIVE_INFRA_SOURCE_EXACT_BUILTIN_MODULE_NAMESPACE')
        p = Path(module.__file__)
        M.need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and
               hashlib.sha256(p.read_bytes()).hexdigest() == pin, 'NATIVE_INFRA_SOURCE_ORIGINAL_FROZEN_MODULE_PINS')
        modules[name] = module
    for name, cls in (('native_cold_bootstrap', NativeColdBootstrap), ('native_layout', NativeLayout)):
        module = modules[name]; p = Path(module.__file__)
        tree = compile(p.read_bytes(), str(p), 'exec', dont_inherit=True)
        original = next(v for v in tree.co_consts if type(v) is CodeType and v.co_name == cls.__name__)
        bootstrap = name == 'native_cold_bootstrap'
        _class_methods(cls, module, original, bootstrap=bootstrap)
        expected = dict(Path=Path, json=json, os=os, need=_original_need, digest=_original_digest,
                        native_aliases=native_aliases)
        helper = 'mem_available' if bootstrap else 'native_names'
        helper_code = next(v for v in tree.co_consts if type(v) is CodeType and v.co_name == helper)
        fn = module.__dict__.get(helper)
        M.need(_method_identity(fn, helper_code, module), 'NATIVE_INFRA_SOURCE_ORIGINAL_HELPER_FUNCTION_NAMESPACE')
        if bootstrap:
            expected.update(subprocess=subprocess, time=time, traceback=traceback, INFRA=INFRA, infra_labels=infra_labels,
                            GIB=1024**3, mem_available=mem_available, NativeColdBootstrap=NativeColdBootstrap)
            # GIB is compared only after exact-int validation, not by identity
            # of distinct equal integer objects produced by separate modules.
            gib = vars(module).get('GIB')
            M.need(type(gib) is int and gib == 1024**3, 'NATIVE_INFRA_SOURCE_ORIGINAL_GIB_CONSTANT')
            expected['GIB'] = gib
        else:
            expected.update(stat=stat, process_birth=process_birth, native_names=native_names, NativeLayout=NativeLayout)
        M.need(_namespace_bindings(vars(module), expected), 'NATIVE_INFRA_SOURCE_CLOSED_ORIGINAL_CLASS_MODULE_BINDINGS')
    return dict(PINS)


def _host(host, rows):
    M.need(type(host) is dict and set(host) == {'state', 'trajectories', 'task_binding_sha256',
           'smoke_initial_tester_only_no_reference_ABI_claim'} and
           host['state'] == 'HOST_ENV_EXPORTED_MODEL_GATES_HELD' and set(host['trajectories']) == set(rows) and
           type(host['smoke_initial_tester_only_no_reference_ABI_claim']) is bool,
           'NATIVE_INFRA_SOURCE_COMPLETE_ORIGINAL_HOST_CONTROL_DOMAIN')
    if host['task_binding_sha256'] is not None:
        _sha(host['task_binding_sha256'])  # existing opaque binding only; no task file opened.
    files = set()
    for t, value in host['trajectories'].items():
        M.need(type(value) is dict and set(value) == HOST_KEYS and
               value['profile'] == native_names(t)[0] and
               value['data_root'] == str(_path(rows[t]['root']) / 'native-data') and
               value['initial_roles'] == list(rows[t]['initial_active_roles']) and
               value['infra_services'] == list(INFRA) and
               set(value['image_ids']) == {'agent', 'router', *INFRA} and
               all(type(v) is str and v.startswith('sha256:') and _sha(v[7:]) for v in value['image_ids'].values()),
               'NATIVE_INFRA_SOURCE_EXACT_ORIGINAL_HOST_TRACK_IMAGES_AND_ROLES')
        env = value['launcher_env']; argv = value['compose']
        M.need(type(env) is dict and set(env) == LAUNCH_KEYS and all(type(v) is str and v and '\0' not in v and
               '\n' not in v for v in env.values()) and env['COUNT14_NATIVE_PROFILE'] == value['profile'] and
               env['COUNT14_NATIVE_ENV_FILE'] == value['envfile'] and type(argv) is list and
               len(argv) >= 4 and argv[:4] == [env['COUNT14_NATIVE_DOCKER'], '--host',
               env['COUNT14_NATIVE_DOCKER_SOCKET'], 'compose'] and shlex.split(env['COUNT14_NATIVE_COMPOSE_COMMAND']) == argv,
               'NATIVE_INFRA_SOURCE_FIXED_SAFE_LAUNCH_FIELDS_NO_SECRET_OR_MODEL_ENV')
        _sha(env['COUNT14_NATIVE_SPAWN_ROUTE_SHA256'])
        # Original Compose control argv: only admitted options with one path/name
        # value each. Never serialize inline environment/key/command arguments.
        M.need(len(argv[4:]) % 2 == 0, 'NATIVE_INFRA_SOURCE_ORIGINAL_COMPOSE_CONTROL_OPTION_PAIRS')
        pairs = list(zip(argv[4::2], argv[5::2])); flags = [k for k, v in pairs]
        M.need(set(flags) == {'--project-directory', '-f', '--project-name', '--env-file', '--profile'} and
               all(flags.count(k) == 1 for k in set(flags) - {'-f'}),
               'NATIVE_INFRA_SOURCE_NO_EXTRA_COMPOSE_INLINE_CONTENT')
        for flag, value_arg in pairs:
            M.need(type(value_arg) is str and value_arg and '\0' not in value_arg and '\n' not in value_arg,
                   'NATIVE_INFRA_SOURCE_SAFE_ORIGINAL_COMPOSE_VALUE')
            if flag in ('-f', '--env-file'):
                files.add(str(_path(value_arg)))
                if flag == '--env-file':
                    M.need(value_arg == value['envfile'], 'NATIVE_INFRA_SOURCE_COMPOSE_SAME_PRIVATE_ENVFILE_POINTER')
            elif flag == '--project-directory':
                M.need(_path(value_arg).parent == _path(value['project_root']),
                       'NATIVE_INFRA_SOURCE_COMPOSE_SAME_REGISTERED_PROJECT_PARENT')
            elif flag == '--profile':
                M.need(value_arg == value['profile'], 'NATIVE_INFRA_SOURCE_SAME_PROFILE')
            else:
                M.need(value_arg == 'omcgitea-' + value['profile'], 'NATIVE_INFRA_SOURCE_SAME_COMPOSE_PROJECT')
        M.need(('-f', env['COUNT14_NATIVE_COMPOSE_BASE']) in pairs, 'NATIVE_INFRA_SOURCE_ORIGINAL_BASE_NOT_DROPPED')
        for key in ('COUNT14_NATIVE_MAKE', 'COUNT14_NATIVE_ENV_FILE', 'COUNT14_NATIVE_COMPOSE_BASE',
                    'COUNT14_NATIVE_PYTHON', 'COUNT14_NATIVE_SPAWN_CLIENT', 'COUNT14_NATIVE_SPAWN_ROUTE',
                    'COUNT14_NATIVE_DOCKER'):
            files.add(str(_path(env[key])))
        files.add(str(_path(value['spawn_source']))); _path(value['project_root'])
    return files


def validate_section(body, *, own, source_birth, contract_sha256, rows):
    _plain(body)
    M.need(type(body) is dict and set(body) == {'schema', 'OWN', 'state', 'source_owner_birth',
           'contract_sha256', 'owner_home', 'row_controls', 'origin_layout_owner_birth', 'handoffs',
           'layout', 'layout_proof', 'host_environment', 'host_control_files', 'bootstrap',
           'private_envfile_or_route_or_scientific_body_read', 'runtime_or_launch_authority'} and
           body['schema'] == SCHEMA and body['state'] == STATE and body['OWN'] is own and
           body['source_owner_birth'] == source_birth and body['contract_sha256'] == contract_sha256 and
           body['row_controls'] == {t: dict(root=r['root'], roles=list(r['roles']),
               initial_active_roles=list(r['initial_active_roles']), arm=r['arm']) for t, r in rows.items()} and
           body['private_envfile_or_route_or_scientific_body_read'] is body['runtime_or_launch_authority'] is False,
           'NATIVE_INFRA_SOURCE_SEALED_EXACT_CONTROL_SCHEMA_NO_AUTHORITY')
    source = _birth(source_birth); origin = _birth(body['origin_layout_owner_birth']); _path(body['owner_home'])
    previous = origin
    for h in body['handoffs']:
        M.need(type(h) is dict and set(h) == {'from_birth', 'to_birth', 'native_source_reference', 'source_section_sha256'} and
               _birth(h['from_birth']) == previous and _birth(h['to_birth']) != previous and
               type(h['native_source_reference']) is dict and set(h['native_source_reference']) == {'path', 'sha256', 'issued_sha256'},
               'NATIVE_INFRA_SOURCE_LOSSLESS_ORIGIN_AND_ALL_HANDOFF_LINEAGE')
        _path(h['native_source_reference']['path']); _sha(h['native_source_reference']['sha256'])
        _sha(h['native_source_reference']['issued_sha256']); _sha(h['source_section_sha256'])
        previous = _birth(h['to_birth'])
    M.need(previous == source, 'NATIVE_INFRA_SOURCE_CURRENT_CAPTURE_IS_LAST_TRUE_OWNER_BIRTH')
    layout = body['layout']
    M.need(type(layout) is dict and set(layout) == {'uid', 'state', 'rows', 'archive_bindings', 'identities'} and
           type(layout['uid']) is int and layout['uid'] >= 0 and (own or layout['uid'] == 10000) and
           layout['state'] == 'NEW_LAYOUT_DURABLE_MODEL_GATES_HELD' and set(layout['rows']) == set(rows),
           'NATIVE_INFRA_SOURCE_ORIGINAL_LAYOUT_DOMAIN_AND_SCIENTIFIC_UID')
    keys = set()
    expected_layout = {}; expected_archives = {}; expected_directories = {}
    for t, row in rows.items():
        profile, org = native_names(t); data = _path(row['root']) / 'native-data'; root = data / profile
        aliases = native_aliases(row['arm'])
        M.need(set(aliases) == set(row['roles']), 'NATIVE_INFRA_SOURCE_ORIGINAL_COMPLETE_NATIVE_LAYOUT_ROLE_CATALOGUE')
        expected_directories[str(data)] = (origin.uid, 0o700)
        for p in (root, *(root / name for name in ('agents', 'acp', 'trajectories', 'workspaces'))):
            expected_directories[str(p)] = (origin.uid, 0o755)
        roles = {}
        for role, alias in aliases.items():
            account = org + '-' + alias['native_short']
            values = dict(agent_state=str(root / 'agents' / account), archive_root=str(root / 'trajectories' / account),
                          acp_root=str(root / 'acp' / account), workspace=str(root / 'workspaces' / account))
            roles[role] = values
            expected_archives[t, role] = dict(archive_root=values['archive_root'],
                native_turn_metadata=str(Path(values['acp_root']) / 'current-turn.json'), owner_uid=origin.uid)
            for name, p in values.items():
                expected_directories[p] = (origin.uid, 0o700) if name == 'archive_root' else (layout['uid'], 0o755)
        expected_layout[t] = dict(data_root=str(data), profile=profile, org=org, profile_root=str(root), roles=roles)
    M.need(layout['rows'] == expected_layout, 'NATIVE_INFRA_SOURCE_LAYOUT_PATHS_EXACT_ORIGINAL_GENERATOR_NOT_ARBITRARY_ROWS')
    for r in layout['archive_bindings']:
        M.need(type(r) is dict and set(r) == {'trajectory', 'role', 'binding'} and
               (r['trajectory'], r['role']) not in keys and r['trajectory'] in rows and r['role'] in rows[r['trajectory']]['roles'],
               'NATIVE_INFRA_SOURCE_EXACT_LAYOUT_ARCHIVE_BINDING_KEYS')
        M.need(r['binding'] == expected_archives[r['trajectory'], r['role']],
               'NATIVE_INFRA_SOURCE_ORIGINAL_ARCHIVE_AND_TURN_POINTERS_NOT_OTHER_ROOT')
        keys.add((r['trajectory'], r['role']))
    M.need(keys == {(t, role) for t, row in rows.items() for role in row['roles']}, 'NATIVE_INFRA_SOURCE_ALL_ARCHIVE_BINDINGS_PRESERVED')
    M.need(type(layout['identities']) is dict and set(layout['identities']) == set(expected_directories),
           'NATIVE_INFRA_SOURCE_COMPLETE_ORIGINAL_LAYOUT_IDENTITY_DOMAIN_NO_DROPPED_ROOT')
    for name, values in layout['identities'].items():
        _path(name)
        M.need(type(values) is list and len(values) == 5 and all(type(v) is int and v >= 0 for v in values) and
               any(Path(name).is_relative_to(_path(r['root']) / 'native-data') for r in rows.values()),
               'NATIVE_INFRA_SOURCE_EXACT_REGISTERED_LAYOUT_DIRECTORY_METADATA')
        M.need((values[2], values[4]) == expected_directories[name],
               'NATIVE_INFRA_SOURCE_ORIGINAL_LAYOUT_UID_MODE_INCLUDING_SCIENTIFIC_UID')
    proof = body['layout_proof']
    M.need(type(proof) is dict and set(proof) == {'path', 'identity', 'sha256'} and
           proof['path'] == str(_path(body['owner_home']) / 'NATIVE_LAYOUT_PUBLIC_INODES.json'),
           'NATIVE_INFRA_SOURCE_FIXED_ORIGINAL_LAYOUT_PROOF_POINTER')
    _sha(proof['sha256'])
    files = _host(body['host_environment'], rows)
    M.need(type(body['host_control_files']) is dict and set(body['host_control_files']) == files,
           'NATIVE_INFRA_SOURCE_ALL_SAFE_HOST_FILE_IDENTITIES_NO_BODY')
    for values in (proof['identity'], *body['host_control_files'].values()):
        M.need(type(values) is list and len(values) == 7 and all(type(v) is int for v in values),
               'NATIVE_INFRA_SOURCE_FIXED_REGULAR_CONTROL_IDENTITIES')
    boot = body['bootstrap']
    M.need(type(boot) is dict and set(boot) == {'forecast', 'records', 'infra_birth_records'} and
           type(boot['forecast']) is int and boot['forecast'] >= 0 and set(boot['records']) == set(rows),
           'NATIVE_INFRA_SOURCE_COMPLETE_ORIGINAL_BOOTSTRAP_CONTROL_DOMAIN')
    for t, r in boot['records'].items():
        M.need(type(r) is dict and set(r) == {'trajectory', 'phase', 'sequence', 'receipt_root',
               'started_ns', 'warning120', 'failure_type', 'control_births', 'discovery_present', 'discovery'} and r['trajectory'] == t and
               r['phase'] == 'INITIAL_UP_COMMANDS_RETURNED_MODEL_HELD' and type(r['sequence']) is int and r['sequence'] > 0 and
               r['receipt_root'] == str(_path(rows[t]['root']) / 'native-bootstrap-public') and
               type(r['started_ns']) is int and r['started_ns'] > 0 and type(r['warning120']) is bool and
               r['failure_type'] is None and type(r['control_births']) is list and bool(r['control_births']),
               'NATIVE_INFRA_SOURCE_FINISHED_ORIGINAL_BOOTSTRAP_CONTROLS_NO_HANDLE_OR_ADOPTION')
        M.need(type(r['discovery_present']) is bool and
               (r['discovery'] is None if not r['discovery_present'] else type(r['discovery']) is dict and
                set(r['discovery']) == {'plans_registered', 'pending_components', 'existing_components'} and
                all(type(v) is int and v >= 0 for v in r['discovery'].values())),
               'NATIVE_INFRA_SOURCE_ORIGINAL_DISCOVERY_COUNTERS_PRESERVED_NOT_REINFERRED')
        for v in r['control_births']:
            _birth(v)
    seen = set(); cids = set()
    for r in boot['infra_birth_records']:
        M.need(type(r) is dict and set(r) == {'trajectory', 'name', 'launch'} and
               (r['trajectory'], r['name']) not in seen and r['trajectory'] in rows and
               r['name'] in set(INFRA) - {'bootstrap', 'gitea-admin-init'}, 'NATIVE_INFRA_SOURCE_EXACT_SIX_ORIGINAL_INFRA_KEYS')
        launch = r['launch']
        M.need(type(launch) is dict and set(launch) == {'cid', 'image_id', 'init_birth'} and
               _sha(launch['cid']) not in cids and launch['image_id'] ==
               body['host_environment']['trajectories'][r['trajectory']]['image_ids'][r['name']],
               'NATIVE_INFRA_SOURCE_ORIGINAL_LAUNCH_FIELDS_AND_IMAGE_PIN')
        _birth(launch['init_birth']); cids.add(launch['cid']); seen.add((r['trajectory'], r['name']))
    M.need(seen == {(t, name) for t in rows for name in set(INFRA) - {'bootstrap', 'gitea-admin-init'}},
           'NATIVE_INFRA_SOURCE_ALL_SIX_LIVE_INFRA_LAUNCH_RECORDS_NO_LATE_DEFAULT')
    return True


def _read_original_layout_proof(path, budget):
    """Only original immutable 0400 layout PUBLIC JSON; never an envfile reader."""
    _budget(budget)
    path = Path(path); before = path.lstat(); limit = 2 * 1024 * 1024
    M.need(path.name == 'NATIVE_LAYOUT_PUBLIC_INODES.json' and path.is_absolute() and
           path.resolve() == path and stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
           before.st_uid == os.geteuid() and stat.S_IMODE(before.st_mode) == 0o400 and before.st_size <= limit,
           'NATIVE_INFRA_SOURCE_ONLY_ORIGINAL_IMMUTABLE_LAYOUT_PROOF')
    def stamp(s):
        return (s.st_dev, s.st_ino, s.st_uid, s.st_gid, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        M.need(stamp(os.fstat(source.fileno())) == stamp(before), 'NATIVE_INFRA_SOURCE_LAYOUT_PROOF_OPEN_SAME_INODE')
        raw = source.read(limit + 1)
        M.need(stamp(os.fstat(source.fileno())) == stamp(before), 'NATIVE_INFRA_SOURCE_LAYOUT_PROOF_STABLE_FD')
    M.need(len(raw) == before.st_size and len(raw) <= limit and stamp(path.lstat()) == stamp(before),
           'NATIVE_INFRA_SOURCE_LAYOUT_PROOF_STABLE_NOFOLLOW_BOUNDED_READ')
    _budget(budget)
    return M.strict(raw), hashlib.sha256(raw).hexdigest()


def _proof(core, layout, origin, budget):
    p = core.home / 'NATIVE_LAYOUT_PUBLIC_INODES.json'
    before = _node(p, budget, False)
    value, pin = _read_original_layout_proof(p, budget)
    expected = dict(schema='count14-native-layout-public-v1', owner_pid=origin.pid,
                    owner_start_ticks=origin.start_ticks, owner_boot_id=origin.boot_id,
                    contract_sha256=M.digest(core.contract), directories=[
                        dict(path=name, dev=v[0], inode=v[1], uid=v[2], mode=v[3])
                        for name, v in sorted(layout.identities.items())])
    M.need(value == expected and _node(p, budget, False) == before,
           'NATIVE_INFRA_SOURCE_GENUINE_ORIGINAL_LAYOUT_PROOF_AND_INODES_UNCHANGED')
    return dict(path=str(p), identity=before, sha256=pin)


def _fresh_infra(core, body, budget):
    from native_container_retirement import NativeContainerRegistry
    from native_docker_scope import ScopedDocker
    registry = core.native_containers
    M.need(type(registry) is NativeContainerRegistry and registry.core is core and type(registry.docker) is ScopedDocker and
           registry.docker.route.qualification_only is body['OWN'], 'NATIVE_INFRA_SOURCE_ORIGINAL_PRIVATE_DOCKER_REGISTRY')
    docker = registry.docker; docker.verify_files(); docker.verify_daemon()
    launches = {(v['trajectory'], v['name']): v['launch'] for v in body['bootstrap']['infra_birth_records']}
    for t, host in body['host_environment']['trajectories'].items():
        env = host['launcher_env']; _budget(budget, core)
        M.need(env['COUNT14_NATIVE_DOCKER'] == str(docker.route.cli) and
               env['COUNT14_NATIVE_DOCKER_SOCKET'] == 'unix://' + str(docker.route.socket_path),
               'NATIVE_INFRA_SOURCE_ORIGINAL_LAUNCH_HOST_ROUTE_NOT_DEFAULT_DAEMON')
        for name in INFRA:
            _budget(budget, core); labels = infra_labels(core, t, name); ids = docker.list_scope_ids(labels)
            M.need(len(ids) == 1, 'NATIVE_INFRA_SOURCE_SINGLE_ORIGINAL_INFRA_GENERATION')
            row = docker.inspect(ids[0])
            expected = {k: labels[v] for k, v in {'root': 'count14.root', 'trajectory': 'count14.trajectory-sha256',
                        'contract': 'count14.contract-sha256', 'role': 'count14.role', 'component': 'count14.component'}.items()}
            M.need(row['labels'] == expected and row['image'] == host['image_ids'][name] and
                   not any(row[k] for k in ('paused', 'restarting', 'dead')), 'NATIVE_INFRA_SOURCE_EXACT_INFRA_IMAGE_FIVE_SCOPES_STATE')
            if name in ('bootstrap', 'gitea-admin-init'):
                M.need(not row['running'] and row['pid'] == 0 and row['exit_code'] == 0, 'NATIVE_INFRA_SOURCE_ORIGINAL_INIT_PREFIX_TERMINAL')
            else:
                value = launches[t, name]
                M.need(row['running'] and (row['id'], row['image'], process_birth(row['pid'])) ==
                       (value['cid'], value['image_id'], _birth(value['init_birth'])),
                       'NATIVE_INFRA_SOURCE_EXISTING_ORIGINAL_INIT_BIRTH_NO_CURRENT_CID_FIRST_BIND')
    _budget(budget, core)


def source_fields(core, *, owner, own, read_budget):
    """Called in the existing issuer, not an arbitrary current-CID observer."""
    _budget(read_budget, core); verify_sources()
    M.need(type(core) is OriginalRelayCore and type(own) is bool and core.qualification_only is own and
           (any(p.startswith('OWN-') for p in core.home.parts) if own else owner is not None and owner.core is core),
           'NATIVE_INFRA_SOURCE_EXACT_ORIGINAL_SOURCE_SCOPE_AND_OWNER')
    if not own:
        import financial_runtime_source_control as F
        F._source(owner, read_budget)  # genuine issued T, retired services, three locks, fixed finance.
    layout = core.native_layout; boot = core.cold_bootstrap
    M.need(type(layout) is NativeLayout and layout.core is core and type(boot) is NativeColdBootstrap and boot.core is core and
           layout.owner == process_birth(os.getpid()), 'NATIVE_INFRA_SOURCE_ORIGINAL_TYPED_SAME_SOURCE_OBJECTS')
    restored = _RESTORES.get(id(core))
    if restored is None:
        M.need(not any(n in vars(boot) for n in BLOCK_BOOT) and '_mkdir' not in vars(layout),
               'NATIVE_INFRA_SOURCE_NO_CALLER_REPLACED_BOOTSTRAP_OR_LAYOUT_METHODS')
        origin, handoffs = layout.owner, []
    else:
        M.need(restored['state'] == 'COMPLETE' and restored['core'] is core and restored['boot'] is boot and
               restored['layout'] is layout and restored['host'] is core.native_host_environment and
               all(vars(boot)[n].__func__ is _no_bootstrap_effect for n in BLOCK_BOOT) and
               vars(layout)['_mkdir'].__func__ is _no_bootstrap_effect,
               'NATIVE_INFRA_SOURCE_REPEATED_SOURCE_REQUIRES_REGISTERED_RESTORE_NOT_ADOPTION')
        origin = _birth(restored['source']['origin_layout_owner_birth']); handoffs = copy.deepcopy(restored['handoffs'])
    for t in core.rows:
        layout.current(t); _budget(read_budget, core)
    identities = {name: _node(name, read_budget, True) for name in sorted(layout.identities)}
    M.need(all((v[0], v[1], v[2], v[4]) == tuple(layout.identities[name]) for name, v in identities.items()),
           'NATIVE_INFRA_SOURCE_ORIGINAL_LAYOUT_IDENTITIES_NOT_RETAGGED')
    host = _plain(core.native_host_environment); files = _host(host, core.rows)
    records = {}
    keys = ('trajectory', 'phase', 'sequence', 'receipt_root', 'started_ns', 'warning120', 'failure_type', 'control_births')
    for t, r in boot.records.items():
        M.need(type(r) is dict and r['child'] is None and 'adopted_existing_infra_not_fresh_UP' not in r and
               'adopted_infra_launch_provenance' not in r, 'NATIVE_INFRA_SOURCE_NO_ACTIVE_CONTROL_CHILD_OR_ADOPTED_PREFIX')
        records[t] = _plain({k: str(r[k]) if k == 'receipt_root' else r[k] for k in keys})
        records[t]['discovery_present'] = 'discovery' in r
        records[t]['discovery'] = _plain(r['discovery']) if 'discovery' in r else None
    launches = []
    for (t, name), r in sorted(boot.infra_birth_records.items()):
        M.need(type(r) is dict and set(r) == {'cid', 'image_id', 'init_birth'} and type(r['init_birth']) is ProcessBirth,
               'NATIVE_INFRA_SOURCE_ONLY_ORIGINAL_LAUNCH_RECORD_OBJECTS')
        launches.append(dict(trajectory=t, name=name, launch=dict(cid=r['cid'], image_id=r['image_id'], init_birth=asdict(r['init_birth']))))
    body = dict(schema=SCHEMA, OWN=own, state=STATE, source_owner_birth=asdict(layout.owner),
                contract_sha256=M.digest(core.contract), owner_home=str(core.home),
                row_controls={t: dict(root=r['root'], roles=list(r['roles']), initial_active_roles=list(r['initial_active_roles']), arm=r['arm'])
                              for t, r in core.rows.items()}, origin_layout_owner_birth=asdict(origin), handoffs=handoffs,
                layout=dict(uid=layout.uid, state=layout.state, rows=_plain(layout.rows),
                    archive_bindings=[dict(trajectory=t, role=r, binding=_plain(v)) for (t, r), v in sorted(layout.archive_bindings.items())],
                    identities=identities), layout_proof=_proof(core, layout, origin, read_budget),
                host_environment=host, host_control_files={p: _node(p, read_budget, False) for p in sorted(files)},
                bootstrap=dict(forecast=boot.forecast, records=records, infra_birth_records=launches),
                private_envfile_or_route_or_scientific_body_read=False, runtime_or_launch_authority=False)
    validate_section(body, own=own, source_birth=asdict(layout.owner), contract_sha256=M.digest(core.contract), rows=core.rows)
    _fresh_infra(core, body, read_budget)
    return body


def _no_bootstrap_effect(*args, **kwargs):
    raise M.PaidColdWait('NATIVE_INFRA_COLD_RESTORE_NEVER_REPLAYS_BOOTSTRAP_OR_LAYOUT_CONSTRUCTORS')


def _decode_source_RAM(core, body, *, read_budget):
    """Private codec only. No binding/grant; production caller must verify cap."""
    _budget(read_budget, core); verify_sources()
    validate_section(body, own=core.qualification_only, source_birth=body['source_owner_birth'],
                     contract_sha256=M.digest(core.contract), rows=core.rows)
    M.need(body['owner_home'] == str(core.home) and not any(hasattr(core, n) for n in
           ('cold_bootstrap', 'native_host_environment', 'native_layout')), 'NATIVE_INFRA_RESTORE_NEW_CORE_NO_HOT_REPLACEMENT')
    for p, values in body['layout']['identities'].items():
        M.need(_node(p, read_budget, True) == values, 'NATIVE_INFRA_RESTORE_LAYOUT_INODE_UID_GID_MODE_DRIFT')
    for p, values in body['host_control_files'].items():
        M.need(_node(p, read_budget, False) == values, 'NATIVE_INFRA_RESTORE_ORIGINAL_HOST_CONTROL_FILE_DRIFT')
    layout = NativeLayout.__new__(NativeLayout)
    raw = body['layout']; layout.core, layout.uid, layout.owner = core, raw['uid'], process_birth(os.getpid())
    layout.contract_sha256, layout.state = body['contract_sha256'], raw['state']
    layout.rows = copy.deepcopy(raw['rows'])
    layout.archive_bindings = {(r['trajectory'], r['role']): copy.deepcopy(r['binding']) for r in raw['archive_bindings']}
    layout.identities = {p: (v[0], v[1], v[2], v[4]) for p, v in raw['identities'].items()}
    layout._mkdir = MethodType(_no_bootstrap_effect, layout)
    M.need(_proof(core, layout, _birth(body['origin_layout_owner_birth']), read_budget) == body['layout_proof'],
           'NATIVE_INFRA_RESTORE_ORIGINAL_LAYOUT_PROOF_NOT_NEW_PROOF')
    host = copy.deepcopy(body['host_environment'])
    for r in host['trajectories'].values():
        for k in ('compose', 'initial_roles', 'infra_services'):
            r[k] = tuple(r[k])
    boot = NativeColdBootstrap.__new__(NativeColdBootstrap)
    boot.core, boot.forecast, boot.memory = core, body['bootstrap']['forecast'], mem_available
    boot.records = copy.deepcopy(body['bootstrap']['records'])
    for r in boot.records.values():
        r['receipt_root'] = Path(r['receipt_root']); r['child'] = None
        present = r.pop('discovery_present'); discovery = r.pop('discovery')
        if present:
            r['discovery'] = discovery
    boot.infra_birth_records = {(r['trajectory'], r['name']): dict(cid=r['launch']['cid'],
        image_id=r['launch']['image_id'], init_birth=_birth(r['launch']['init_birth'])) for r in body['bootstrap']['infra_birth_records']}
    for name in BLOCK_BOOT:
        setattr(boot, name, MethodType(_no_bootstrap_effect, boot))
    return boot, host, layout


def bind_registered_receiver(graph, *, capability, read_budget):
    """Only a genuine T/services/native cap may bind NEW held receiver RAM."""
    import native_control_source_supplement as S
    import new_owner_host_control as H
    M.need(type(capability) is S.VerifiedNativeSourceControls and S._VERIFIED.get(id(capability)) is capability,
           'NATIVE_INFRA_RESTORE_ONLY_REGISTERED_ORIGINAL_NATIVE_SOURCE_CAP')
    M.need(H.registered_stage_host_graph(graph.stage) is graph and capability.source_owner is graph.registration.source_owner and
           capability.source_ticket is graph.registration.source_ticket and
           capability.old_owner_birth == graph.registration.old_owner_birth == graph.stage.old_owner_birth and
           capability.new_owner_birth == graph.registration.new_owner_birth == graph.stage.new_owner_birth == process_birth(os.getpid()) and
           tuple(capability.lock_fds) == tuple(graph.stage.context.lock_fds) and
           capability.contract_sha256 == M.digest(graph.core.contract), 'NATIVE_INFRA_RESTORE_ORIGINAL_CROSSBIRTH_THREE_LOCK_GRAPH')
    core = graph.core; _budget(read_budget, core)
    M.need(core.qualification_only is False and core.gate.closed and not core.gate.waiters and
           set(core.gate.startup_held) == set(core.rows) and id(core) not in _RESTORES,
           'NATIVE_INFRA_RESTORE_ONCE_NEW_HELD_PRODUCTION_GRAPH_NOT_OWN_OR_LIVE_PATCH')
    body = capability.snapshot()['original_native_infrastructure_controls']  # absence is WAIT/error, never fallback.
    validate_section(body, own=False, source_birth=asdict(capability.old_owner_birth),
                     contract_sha256=capability.contract_sha256, rows=core.rows)
    _fresh_infra(core, body, read_budget)
    boot, host, layout = _decode_source_RAM(core, body, read_budget=read_budget)
    reference = capability._reference
    handoffs = copy.deepcopy(body['handoffs']) + [dict(from_birth=asdict(capability.old_owner_birth),
        to_birth=asdict(capability.new_owner_birth), source_section_sha256=M.digest(body),
        native_source_reference={k: reference[k] for k in ('path', 'sha256', 'issued_sha256')})]
    record = dict(core=core, graph=graph, capability=capability, source=copy.deepcopy(body),
                  handoffs=handoffs, boot=boot, host=host, layout=layout, state='PARTIAL_RETAINED_NO_RETRY', seal=_SEAL)
    _RESTORES[id(core)] = record  # preserve any real partial; never retry or undo a binding.
    core.cold_bootstrap, core.native_host_environment, core.native_layout = boot, host, layout
    for t in core.rows:
        layout.current(t); _budget(read_budget, core)
    record['state'] = 'COMPLETE'
    return record
