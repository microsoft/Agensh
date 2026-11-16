"""Exact pinned native/framework-source UID cold adapter; no owner or model work.

Only build_stager(original_stager_module, args) is the production interface.
No chmod/chown, source writes, credential reads, retry, or root creation here.
"""
from pathlib import Path
from types import FunctionType, ModuleType
import hashlib
import os
import stat

ORIGINAL_STAGER_SHA256 = 'a662e49ef6fb6f504627b46251f92c63d2cfc32dd2e47927a675da17dfa025bb'
PROFILE_SHA256 = '8530bb5026d7ad9a77a5aa78a92d9d18426fb97b5236de75ccb6c278ae28aeba'
ORIGIN_SHA256 = 'c193188fd4d20de8ec0729b4a41bc4df7e15e38b54d84736147da0a546a147b6'


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _source(path, credential):
    p = Path(path)
    need(p.is_absolute() and p.resolve() == p and not p.is_symlink() and p != credential,
         'NATIVE_UID_EXACT_CANONICAL_NONCREDENTIAL_SOURCE')
    s = p.lstat()
    need(stat.S_ISREG(s.st_mode) and not s.st_mode & 0o002 and s.st_nlink == 1,
         'NATIVE_UID_SOURCE_REGULAR_SINGLE_LINK_NOT_WORLD_WRITABLE')
    need(s.st_uid in (0, os.geteuid()) or (s.st_uid, s.st_gid) == (1000, 1000),
         'NATIVE_UID_ONLY_ORIGINAL_OWNER_OR_EXACT_1000_1000')
    if s.st_uid == 1000:
        need(s.st_gid == 1000, 'NATIVE_UID_EXACT_1000_GID')
    return p, s


def _pinned_read(path, pin, credential, *, collect=False):
    """Only enumerated runtime-code or PUBLIC metadata; never a credential."""
    p, before = _source(path, credential)
    need(type(pin) is str and len(pin) == 64 and all(c in '0123456789abcdef' for c in pin),
         'NATIVE_UID_FIXED_SHA256')
    if collect:
        need(before.st_size <= 16 * 1024 * 1024, 'NATIVE_UID_PUBLIC_METADATA_BOUND')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    h = hashlib.sha256(); pieces = []
    with os.fdopen(fd, 'rb') as f:
        opened = os.fstat(f.fileno())
        need(identity(before) == identity(opened), 'NATIVE_UID_OPEN_EXACT_FD_IDENTITY')
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
            if collect:
                pieces.append(chunk)
        ended = os.fstat(f.fileno())
        need(identity(opened) == identity(ended), 'NATIVE_UID_FD_STABLE')
    p2, after = _source(p, credential)
    need(p2 == p and identity(before) == identity(after) and h.hexdigest() == pin,
         'NATIVE_UID_SOURCE_STABLE_AND_FIXED_BYTEPIN')
    return b''.join(pieces) if collect else p


class _GuardedSourceOS:
    """Original copy body unchanged; its selected-source open adds FD guards."""
    def __init__(self, selected, credential):
        self.selected = selected; self.credential = credential

    def __getattr__(self, name):
        return getattr(os, name)

    def open(self, path, flags, *args, **kwargs):
        selected = self.selected.get(Path(path)) if isinstance(path, (str, bytes, os.PathLike)) and not isinstance(path, bytes) else None
        if selected is None:
            return os.open(path, flags, *args, **kwargs)
        p, before = _source(path, self.credential)
        need(flags == (os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK),
             'NATIVE_UID_ORIGINAL_READONLY_NOFOLLOW_NONBLOCK_OPEN')
        fd = os.open(p, flags, *args, **kwargs)
        try:
            need(identity(os.fstat(fd)) == identity(before) == identity(p.lstat()),
                 'NATIVE_UID_COPY_OPEN_EXACT_GUARDED_FD')
        except BaseException:
            os.close(fd)
            raise
        return fd


def _private_stager(original, selected, credential):
    """Private dependency graph, also exercised by one explicit OWN fixture."""
    selected = dict(selected)
    need(credential not in selected, 'NATIVE_UID_NEVER_SELECT_CREDENTIAL')
    private = ModuleType('_count14_exact_native_source_uid_private_stager')
    scope = private.__dict__; scope.update(vars(original))
    scope['__name__'] = private.__name__
    scope['os'] = _GuardedSourceOS(selected, credential)

    def regular(path):
        p = Path(path)
        if p in selected:
            return _pinned_read(p, selected[p], credential)
        return original.regular(path)

    scope['regular'] = regular
    scope['kept'] = lambda path, roots: exact_current_native_source(original, path, roots)
    # Keep original file_sha/public/copy/stage code objects, dependencies private.
    for name in ('file_sha', 'public', 'copy_pinned', 'stage'):
        original_fn = getattr(original, name)
        fn = FunctionType(original_fn.__code__, scope, original_fn.__name__,
                          original_fn.__defaults__, original_fn.__closure__)
        fn.__kwdefaults__ = original_fn.__kwdefaults__
        scope[name] = fn
    original_copy = scope['copy_pinned']; original_public = scope['public']; original_sha = scope['file_sha']

    def copy_pinned(source, destination, expected):
        p = Path(source)
        if p in selected:
            need(expected == selected[p], 'NATIVE_UID_COPY_EXACT_REGISTERED_BYTEPIN')
        return original_copy(source, destination, expected)

    def public(path, expected):
        p = Path(path)
        if p in selected:
            need(expected == selected[p], 'NATIVE_UID_PUBLIC_EXACT_REGISTERED_BYTEPIN')
        return original_public(path, expected)

    def file_sha(path):
        value = original_sha(path); p = Path(path)
        if p in selected:
            need(value == selected[p], 'NATIVE_UID_HASH_EXACT_REGISTERED_BYTEPIN')
        return value

    scope.update(copy_pinned=copy_pinned, public=public, file_sha=file_sha)
    private._native_uid_exact_source_pins_public = tuple(
        {'path': str(p), 'sha256': pin} for p, pin in sorted(selected.items()))
    return private


def exact_current_native_source(original, path, roots):
    """One exact current frozen native559 root; NEVER broaden old KEEP."""
    import json
    source_home = Path(__file__).resolve().parents[2]
    expected_home = Path('/mnt/ptb-scratch2/ct14-dynteam-formal-msg237-20261110-v33/source-msg276-n33-session-ready-repropose-v44')
    native = source_home/'NATIVE_FINAL_SOURCE'
    if Path(path) != native:
        return original.kept(path, roots)
    need(source_home == expected_home and native.resolve() == native and native.is_dir() and
         os.geteuid() == 0 and os.uname().nodename == 'H100DEV4',
         'FORMAL_UID_EXACT_CURRENT_NATIVE559_INITIAL_SOURCE_ONLY')
    need(not any((source_home.parent/arm/'owner/ledger/ledger.sqlite').exists() for arm in ('u','r')),
         'FORMAL_UID_NATIVE_SOURCE_ONLY_BEFORE_OWNER_NO_LIVE_CHANGE')
    table_path = source_home/'NATIVE_FINAL_FILES_PUBLIC.json'
    before = table_path.lstat(); raw = table_path.read_bytes(); after = table_path.lstat()
    need(identity(before) == identity(after) and stat.S_ISREG(before.st_mode) and before.st_uid == 0 and
         before.st_nlink == 1 and not before.st_mode&0o222 and
         hashlib.sha256(raw).hexdigest() == '2395e3e57f324227da2bbee6880f88ca94154c5b7196619d7c961781508092f0',
         'FORMAL_UID_EXACT_REGISTERED_NATIVE559_INVENTORY_PIN')
    table = json.loads(raw)
    need(len(table['files']) == 559 and {p.name for p in native.iterdir()} == set(table['files']),
         'FORMAL_UID_COMPLETE_NATIVE559_NOT_SUBSET_OR_OLD557')
    for name,pin in table['files'].items():
        need(Path(name).name == name, 'FORMAL_UID_NATIVE559_SINGLE_COMPONENT_MEMBER')
        p = native/name; s = p.lstat()
        need(p.resolve() == p and stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1 and
             not s.st_mode&0o222 and s.st_size == pin['bytes'] and
             hashlib.sha256(p.read_bytes()).hexdigest() == pin['sha256'] and identity(s) == identity(p.lstat()),
             'FORMAL_UID_CURRENT_NATIVE559_FILE_EXACT_IMMUTABLE_BYTES')
    return native


def build_stager(original_stager, a):
    """Derive finite exact sources only from fixed profile/origin/import registry.

    Unselected paths, especially credential, always keep original regular().
    No empty-partial/mkdir exception lives in this adapter.
    """
    original = original_stager
    source = Path(original.__file__)
    need(source.is_absolute() and source.resolve() == source and not source.is_symlink()
         and hashlib.sha256(source.read_bytes()).hexdigest() == ORIGINAL_STAGER_SHA256,
         'NATIVE_UID_ORIGINAL_STAGER_SOURCE_PIN')
    for name in ('regular', 'file_sha', 'public', 'copy_pinned', 'stage'):
        need(getattr(original, name).__globals__ is vars(original),
             'NATIVE_UID_ONLY_EXACT_ORIGINAL_MODULE_NO_PREVIOUS_MUTATION')
    credential = original.canonical(a.credential_source)
    selected = {}

    def put(path, pin):
        p = original.canonical(path); original.sha(pin)
        need(p != credential and not any(x.lower() in original.DENIED_COMPONENTS for x in p.parts),
             'NATIVE_UID_ENUMERATED_RUNTIME_OR_PUBLIC_ONLY_NOT_CREDENTIAL')
        need(p not in selected or selected[p] == pin, 'NATIVE_UID_NO_CONFLICTING_EXACT_PATH_PIN')
        selected[p] = pin
        return p

    def metadata(path, pin):
        # PUBLIC profile/origin/registry already passed the original OPS guard.
        # They derive the finite list, but get no UID exception themselves.
        return original.public(path, pin)

    # Caller supplies explicit fixed complete profile path, not a prefix exception.
    need(a.reference_profile and a.reference_profile_sha256 == PROFILE_SHA256,
         'NATIVE_UID_FIXED_COMPLETE_PROFILE_REQUIRED')
    profile = metadata(a.reference_profile, PROFILE_SHA256)
    need(profile.get('schema') == 'count14-agensh-native-v21-profile-v1'
         and original.digest(profile) == PROFILE_SHA256,
         'NATIVE_UID_COMPLETE_PROFILE_RAW_AND_CANONICAL_PIN')
    contract = original.public(a.contract, a.contract_sha256)
    need(contract.get('schema') == 'count14-dynteam-two-arm-public-contract-v1'
         and contract.get('mode') == 'smoke'
         and contract['v2_baseline_reference_protocol']['final_v21'] == PROFILE_SHA256,
         'NATIVE_UID_EXACT_SMOKE_CONTRACT_PROFILE')
    base = original.canonical(a.base)
    origin = metadata(base / 'NATIVE_FINAL_CODE_ORIGIN.json', ORIGIN_SHA256)
    need(origin.get('schema') == 'agensh-original-native-final-code-v1'
         and type(origin.get('files')) is dict and origin['files'],
         'NATIVE_UID_FIXED_NATIVE_ORIGIN')
    imports = metadata(a.framework_imports, original.sha(a.framework_imports_sha256))
    need(imports.get('schema') == 'count14-dynteam-framework-import-pins-v1'
         and type(imports.get('roots')) is list and imports['roots'],
         'NATIVE_UID_FIXED_IMPORT_REGISTRY')
    roots = [Path(p) for p in original.RUNTIME_KEEP_ROOTS]
    native = exact_current_native_source(original, a.native_source, roots)
    for name, pin in origin['files'].items():
        original.relative_code(name, native=True); put(native / name, pin)
    source_index_pin = profile['source_index']['sha256']
    need(not a.native_source_index_sha256 or a.native_source_index_sha256 == source_index_pin,
         'NATIVE_UID_ORIGINAL_PROFILE_SOURCE_INDEX_PIN')
    put(native / 'source-manifest.json', source_index_pin)
    for row in imports['roots']:
        root = original.canonical(row['path'])
        need(root == base or root.is_relative_to(Path(contract['arms'][0]['root']) / 'frozen-code')
             or any(root == r or root.is_relative_to(r) for r in roots),
             'NATIVE_UID_FRAMEWORK_ORIGINAL_PACKAGE_OR_KEEP_ONLY')
        for name, pin in row['files'].items():
            original.relative_code(name); put(root / name, pin)
    return _private_stager(original, selected, credential)
