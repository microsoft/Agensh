"""Preserve a verified old resource epoch BEFORE any pointer transition.

No sampler, Popen, pointer write, producer constructor or paid/native restore.
Only exact controls already verified by original typed T/new-birth/three-lock
history are copied. Complete files alone never become an authority: the live
capability remains registered to the original pair, birth and control thread.
"""
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import importlib
import json
import os
import stat
import threading

PINS = dict(
    retired_resource_history='b756439360673e2e0cf96d7e0e3ae7f546cfd43fd7862e437894fc85cd3ade97',
    durable_service_source_controls='fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83',
    normal_inert_cut='aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',
    metadata_inert_pair='83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da',
    bounded_metadata_ro='621cd0db6da2d1e6422537f6ae2188ac8466627efe803d8b4d39f260bfb7c249')
LEAF = 'retired-resource-epoch-archives-v1'
SCHEMA = 'count14-preserved-retired-resource-epoch-v1'
_SEAL = object()
_ATTEMPTS = {}
_REGISTERED = {}


def need(value, code):
    if not value:
        raise ValueError(code)


def _token(info):
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_sources():
    for name, pin in PINS.items():
        path = Path(importlib.import_module(name).__file__)
        info = path.lstat()
        need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(info.st_mode)
             and info.st_nlink == 1 and info.st_uid in (0, os.geteuid())
             and not info.st_mode & 0o022 and _sha(path.read_bytes()) == pin,
             'RESOURCE_ARCHIVE_EXACT_ORIGINAL_SOURCE_PINS')
    path = Path(__file__)
    info = path.lstat()
    need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(info.st_mode)
         and info.st_nlink == 1 and not info.st_mode & 0o022,
         'RESOURCE_ARCHIVE_FROZEN_CANONICAL_SELF')
    return _sha(path.read_bytes())


def _budget(value):
    from bounded_metadata_ro import ReadBudget
    need(type(value) is ReadBudget, 'RESOURCE_ARCHIVE_ORIGINAL_FINITE_METADATA_BUDGET')
    value.check()


def _directory(path, budget):
    budget.check()
    info = path.lstat()
    need(path.is_absolute() and path.resolve() == path and stat.S_ISDIR(info.st_mode)
         and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700,
         'RESOURCE_ARCHIVE_EXACT_PRIVATE_DIRECTORY')
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode]


def _read(path, *, mode, limit, budget, expected=None):
    budget.check()
    info = path.lstat()
    need(path.is_absolute() and path.resolve() == path and stat.S_ISREG(info.st_mode)
         and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == mode
         and info.st_nlink == 1 and 0 < info.st_size <= limit,
         'RESOURCE_ARCHIVE_BOUNDED_CANONICAL_SINGLE_LINK_CONTROL')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        raw = bytearray()
        while len(raw) <= limit:
            budget.check()
            block = os.read(fd, min(131072, limit + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        after = os.fstat(fd)
        need(_token(info) == _token(before) == _token(after) == _token(path.lstat())
             and len(raw) == info.st_size, 'RESOURCE_ARCHIVE_STABLE_ORIGINAL_FD')
    finally:
        os.close(fd)
    raw = bytes(raw)
    reference = dict(path=str(path), sha256=_sha(raw), identity=_token(info))
    need(expected is None or reference == expected, 'RESOURCE_ARCHIVE_EXACT_SEALED_RAW_REFERENCE')
    budget.check()
    return raw, reference


def _sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path, raw, budget):
    budget.check()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    budget.check()
    return _read(path, mode=0o444, limit=max(1, len(raw)), budget=budget)[1]


def _json(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()


def _history(reference, owner, ticket, budget, own):
    _budget(budget)
    verify_sources()
    import retired_resource_history as R
    result = (R.read_OWN_history if own else R.read_history)(
        reference, owner=owner, ticket=ticket, read_budget=budget)
    need(type(result) is R.VerifiedResourceHistory and result._seal is R._SEAL and result.OWN is own,
         'RESOURCE_ARCHIVE_ORIGINAL_TYPED_HISTORY_NOT_JSON_OR_GREEN_BOOL')
    return result


def _original_inputs(history, ticket, budget):
    """Fixed old controls plus their original T/SOURCE issuance, not discovery."""
    result = []
    for item in history._references:
        path = Path(item['path'])
        mode = 0o444 if path.name == 'COHORT_RESOURCES_PUBLIC.json' else 0o600
        raw, reference = _read(path, mode=mode, limit=131072, budget=budget, expected=item)
        result.append(dict(kind='original_resource_control', raw=raw, reference=reference))
    source = history._source._reference
    fixed = (
        ('original_service_SOURCE', Path(source['path']), source['sha256'], 8 * 1024 * 1024),
        ('original_service_ISSUED', Path(source['issued_identity']['path']), source['issued_sha256'], 262144),
        ('original_T', Path(ticket.path), ticket.sha256, 16 * 1024 * 1024),
        ('original_T_ISSUED', Path(ticket.path).with_name('ISSUED.json'), None, 16384))
    for kind, path, pin, limit in fixed:
        raw, reference = _read(path, mode=0o600, limit=limit, budget=budget)
        need(pin is None or reference['sha256'] == pin, 'RESOURCE_ARCHIVE_ORIGINAL_ISSUER_PIN')
        result.append(dict(kind=kind, raw=raw, reference=reference))
    need(len({r['reference']['path'] for r in result}) == len(result),
         'RESOURCE_ARCHIVE_UNIQUE_REGISTERED_CONTROL_PATHS')
    need(sum(len(r['raw']) for r in result) <= 32 * 1024 * 1024,
         'RESOURCE_ARCHIVE_FINITE_TOTAL_RAW_CONTROL_BOUND')
    return result


def _same_history(first, second):
    return (first._snapshot == second._snapshot and first._references == second._references
            and first._source._reference == second._source._reference
            and first._source.old_owner_birth == second._source.old_owner_birth
            and first._source.new_owner_birth == second._source.new_owner_birth)


class PreservedResourceEpoch:
    __slots__ = ('_body', '_manifest', '_issued', '_root_identity', '_reference',
                 '_owner', '_ticket', '_history', '_thread', '_seal', 'OWN')

    def __init__(self, *args, **kwargs):
        raise ValueError('RESOURCE_ARCHIVE_ONLY_TYPED_REGISTERED_CREATION')

    def __setattr__(self, name, value):
        need(not hasattr(self, '_seal'), 'RESOURCE_ARCHIVE_IMMUTABLE_CAPABILITY')
        object.__setattr__(self, name, value)

    def snapshot(self):
        need(self._seal is _SEAL and _REGISTERED.get(id(self)) is self,
             'RESOURCE_ARCHIVE_REGISTERED_SEAL_NOT_FILE_AUTHORITY')
        return copy.deepcopy(self._body)

    def public(self):
        body = self.snapshot()
        return dict(schema='count14-preserved-resource-epoch-status-v1',
            registered=body['resource_history_public']['registered'],
            old_sequence=body['resource_history_public']['sequence'],
            old_pointer_archived=body['old_pointer_copy'] is not None,
            control_copies=len(body['copies']), complete_archive=True,
            original_records_relabelled=False, pointer_transition_authorized=False,
            resource_sampler_restored=False, native_paid_runtime_restored=False,
            safe_to_TERM=False, whole_runnable_ready=False, paid_activation_authorized=False)


def _closed_leaf(capability, budget):
    body = capability._body
    root = Path(body['archive_directory'])
    need(_directory(root, budget) == capability._root_identity,
         'RESOURCE_ARCHIVE_ORIGINAL_ARCHIVE_DIRECTORY_IDENTITY')
    names = []
    for path in root.iterdir():
        budget.check()
        need(len(names) < len(body['copies']) + 3, 'RESOURCE_ARCHIVE_NO_UNKNOWN_ARCHIVE_LEAF')
        names.append(path.name)
    expected_names = ['ATTEMPT_PUBLIC.json', 'ARCHIVE_PUBLIC.json', 'ISSUED_PUBLIC.json',
                      *[r['name'] for r in body['copies']]]
    need(sorted(names) == sorted(expected_names), 'RESOURCE_ARCHIVE_EXACT_CLOSED_ARCHIVE_LEAF_SET')
    for row in body['copies']:
        path = root / row['name']
        raw, _ = _read(path, mode=0o444, limit=row['original']['identity'][6],
                       budget=budget, expected=row['copy'])
        need(_sha(raw) == row['original']['sha256'], 'RESOURCE_ARCHIVE_COPY_BYTES_NOT_SOURCE_AUTHORITY')
    _read(Path(body['attempt_reference']['path']), mode=0o444, limit=131072,
          budget=budget, expected=body['attempt_reference'])
    raw, _ = _read(Path(capability._manifest['path']), mode=0o444, limit=8 * 1024 * 1024,
                   budget=budget, expected=capability._manifest)
    need(raw == _json(body), 'RESOURCE_ARCHIVE_MANIFEST_PRESERVES_ORIGINAL_SEMANTICS')
    _read(Path(capability._issued['path']), mode=0o444, limit=131072,
          budget=budget, expected=capability._issued)


def _prepare(reference, *, owner, ticket, read_budget, own):
    history = _history(reference, owner, ticket, read_budget, own)
    key = (id(owner), history._source.old_owner_birth.pid,
           history._source.old_owner_birth.start_ticks, history._source._reference['sha256'])
    need(key not in _ATTEMPTS, 'RESOURCE_ARCHIVE_ONCE_PER_REGISTERED_PAIR_NO_RETRY')
    originals = _original_inputs(history, ticket, read_budget)
    current = _history(reference, owner, ticket, read_budget, own)
    need(_same_history(history, current), 'RESOURCE_ARCHIVE_ORIGINALS_STABLE_BEFORE_ANY_WRITE')
    old, new = history._source.old_owner_birth, history._source.new_owner_birth
    home = owner.core.home
    # Missing resources for ABSENT remains unknown; only the private archive is new.
    resources = home / 'resources'
    if not os.path.lexists(resources):
        resources.mkdir(mode=0o700)
    need(resources.is_dir() and resources.resolve() == resources and not resources.is_symlink(),
         'RESOURCE_ARCHIVE_CANONICAL_EXISTING_RESOURCE_PARENT')
    parent = resources / LEAF
    if not os.path.lexists(parent):
        parent.mkdir(mode=0o700)
        _sync(resources)
    _directory(parent, read_budget)
    root = parent / f'from-{old.pid}-{old.start_ticks}-to-{new.pid}-{new.start_ticks}'
    _ATTEMPTS[key] = dict(state='PREPARING_RETAIN_ALL_PARTIALS_NO_RETRY', path=str(root))
    root.mkdir(mode=0o700)
    root_identity = _directory(root, read_budget)
    copies = []
    attempt = dict(schema='count14-preserved-resource-epoch-attempt-v1', OWN=own,
        old_owner=asdict(old), new_owner=asdict(new), contract_sha256=history._source.contract_sha256,
        source_reference=copy.deepcopy(history._source._reference),
        original_T=dict(path=ticket.path, sha256=ticket.sha256), source_module_sha256=verify_sources(),
        pointer_writes=0, models=0, no_automatic_retry=True)
    attempt_ref = _write(root / 'ATTEMPT_PUBLIC.json', _json(attempt), read_budget)
    for number, item in enumerate(originals):
        name = f'{number:08d}-{Path(item["reference"]["path"]).name}'
        copied = _write(root / name, item['raw'], read_budget)
        copies.append(dict(name=name, kind=item['kind'], original=item['reference'], copy=copied))
    snapshot = history._snapshot
    pointer = next((r for r in copies if Path(r['original']['path']).name == 'COHORT_RESOURCES_PUBLIC.json'), None)
    records = None if snapshot['records'] is None else [dict(
        sequence=r['sequence'], state=r['state'], child_returncode=r['child_returncode'],
        intent_sha256=r['intent_sha256'], original_directory=str(r['directory']),
        retained_result_validation_error=r['retained_result_validation_error'],
        retained_receipt_validation_error=r['retained_receipt_validation_error']) for r in snapshot['records']]
    body = dict(schema=SCHEMA, OWN=own, archive_directory=str(root),
        old_owner=asdict(old), preserving_owner=asdict(new),
        contract_sha256=history._source.contract_sha256, original_issuance=attempt,
        resource_history_public=history.public(), configuration=copy.deepcopy(snapshot['configuration']),
        records=records, copies=copies, old_pointer_copy=pointer, attempt_reference=attempt_ref,
        source_module_sha256=verify_sources(), source_pins=dict(PINS),
        pointer_transition_authorized=False, resource_sampler_restored=False,
        safe_to_TERM=False, paid_activation_authorized=False, whole_runnable_ready=False)
    encoded_body = _json(body)
    need(len(encoded_body) <= 8 * 1024 * 1024, 'RESOURCE_ARCHIVE_BOUNDED_MANIFEST_BEFORE_ISSUED')
    manifest = _write(root / 'ARCHIVE_PUBLIC.json', encoded_body, read_budget)
    # A failure here leaves the entire partial without ISSUED and cannot be retried.
    final = _history(reference, owner, ticket, read_budget, own)
    need(_same_history(history, final) and
         _original_inputs(history, ticket, read_budget) == originals,
         'RESOURCE_ARCHIVE_ORIGINALS_UNCHANGED_AFTER_FULL_COPY')
    issued = _write(root / 'ISSUED_PUBLIC.json', _json(dict(
        schema='count14-preserved-resource-epoch-complete-v1', OWN=own,
        archive_reference=manifest, source_module_sha256=body['source_module_sha256'],
        old_owner=asdict(old), preserving_owner=asdict(new),
        file_complete_not_cold_or_pointer_authority=True,
        pointer_transition_authorized=False, resource_sampler_restored=False)), read_budget)
    _sync(root)
    _sync(parent)
    value = object.__new__(PreservedResourceEpoch)
    value._body, value._manifest, value._issued = body, manifest, issued
    value._root_identity, value._reference = root_identity, reference
    value._owner, value._ticket, value._history = owner, ticket, history
    value._thread, value.OWN = threading.get_ident(), own
    value._seal = _SEAL
    _closed_leaf(value, read_budget)
    _REGISTERED[id(value)] = value
    _ATTEMPTS[key]['state'] = 'COMPLETE_ARCHIVE_NOT_TRANSITION_AUTHORITY'
    return value


def archive_before_transition(reference, *, owner, ticket, read_budget):
    return _prepare(reference, owner=owner, ticket=ticket, read_budget=read_budget, own=False)


def archive_OWN_before_transition(reference, *, owner, ticket, read_budget):
    return _prepare(reference, owner=owner, ticket=ticket, read_budget=read_budget, own=True)


def _verify(value, *, owner, ticket, read_budget, own):
    _budget(read_budget)
    need(type(value) is PreservedResourceEpoch and value._seal is _SEAL
         and _REGISTERED.get(id(value)) is value and value.OWN is own
         and value._owner is owner and value._ticket is ticket
         and value._thread == threading.get_ident(),
         'RESOURCE_ARCHIVE_EXACT_LIVE_CAPABILITY_OWNER_THREAD_AND_NAMESPACE')
    current = _history(value._reference, owner, ticket, read_budget, own)
    need(_same_history(value._history, current),
         'RESOURCE_ARCHIVE_ORIGINAL_HISTORY_STILL_CURRENT_BEFORE_TRANSITION')
    _closed_leaf(value, read_budget)
    return value.snapshot()


def verify_before_transition(value, *, owner, ticket, read_budget):
    return _verify(value, owner=owner, ticket=ticket, read_budget=read_budget, own=False)


def verify_OWN_before_transition(value, *, owner, ticket, read_budget):
    return _verify(value, owner=owner, ticket=ticket, read_budget=read_budget, own=True)
