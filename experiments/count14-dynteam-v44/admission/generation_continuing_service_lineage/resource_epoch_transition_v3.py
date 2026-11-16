"""One typed new-owner finite observation and exact archived-pointer switch.

This does NOT construct or hydrate NativeResourceProducer/NativeCohortResources,
native/SDK/paid runtime or a scientific dispatcher. A pointer is an observation,
never admission. No import/start/poll automatically publishes or releases work.
"""
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import importlib
import json
import os
import stat
import subprocess
import threading
import time

import resource_epoch_archive_v2 as A

PINS = dict(resource_epoch_archive_v2='aa54e75ce3af53d4d257082e6159792d5a32b9966554c245fec7f371ae7e60c9',
    retired_resource_history='b756439360673e2e0cf96d7e0e3ae7f546cfd43fd7862e437894fc85cd3ade97',
    durable_service_source_controls='fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83',
    native_resource_sampler='880ae285ee18ad75e4aec3ccc4aa024f63a8423128834c6468b885606349cec3',
    native_resource_producer='c1187cd5195a3b431a6eabd330578bd911ebe3fc4405a1358944d750df48be07',
    native_system_probe_child='0b0435eaabc7bf65419c05e0ea33a4139e1978360c63b94bff74915bc56d4ebe')
_SEAL = object()
_REG = {}
_ATTEMPTS = {}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def _sources():
    for name, pin in PINS.items():
        path = Path(importlib.import_module(name).__file__)
        info = path.lstat()
        need(path.resolve() == path and stat.S_ISREG(info.st_mode) and info.st_nlink == 1
             and not info.st_mode & 0o022 and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
             'RESOURCE_EPOCH_EXACT_FROZEN_ORIGINAL_SOURCES')
    path = Path(__file__)
    info = path.lstat()
    need(path.resolve() == path and stat.S_ISREG(info.st_mode) and not info.st_mode & 0o022,
         'RESOURCE_EPOCH_CANONICAL_FROZEN_SELF')
    A.verify_sources()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value, budget):
    from native_system_probe_child import append
    budget.check()
    append(path, value)
    budget.check()
    return A._read(path, mode=0o600, limit=131072, budget=budget)[1]


class ResourceEpoch:
    __slots__ = ('_seal',)

    def __init__(self, *args, **kwargs):
        raise ValueError('RESOURCE_EPOCH_ONLY_ORIGINAL_TYPED_ARCHIVE_ENTRY')

    def __setattr__(self, name, value):
        need(not hasattr(self, '_seal'), 'RESOURCE_EPOCH_IMMUTABLE_CAPABILITY')
        object.__setattr__(self, name, value)

    def public(self):
        r = _registered(self)
        return dict(schema='count14-new-owner-resource-epoch-status-v1', state=r['state'],
            sequence=r['sequence'], old_sequence=r['history']._snapshot['configuration']['sequence'],
            child_started=r['child'] is not None, physical_child_exit_code=r['child_exit'],
            publication_attempted=r['publication_attempted'], physical_pointer=r['physical_pointer'],
            publication_complete=r['state'] == 'TRANSITION_COMPLETE',
            observation_is_not_admission=True, original_old_records_relabelled=False,
            producer_manager_native_paid_runtime_restored=False, models=0,
            safe_to_TERM=False, whole_runnable_ready=False, paid_activation_authorized=False)

    def poll(self, *, read_budget):
        return poll(self, read_budget=read_budget)


def _registered(value, own=None):
    from native_peer_registry import process_birth
    need(type(value) is ResourceEpoch and value._seal is _SEAL and id(value) in _REG,
         'RESOURCE_EPOCH_EXACT_REGISTERED_CAPABILITY_NOT_JSON')
    r = _REG[id(value)]
    need(r['cap'] is value and r['birth'] == process_birth(os.getpid())
         and r['thread'] == threading.get_ident() and (own is None or r['OWN'] is own),
         'RESOURCE_EPOCH_SAME_REAL_BIRTH_CONTROL_THREAD_AND_NAMESPACE')
    need(not r['owner'].core.ledger.mutex._is_owned() and not r['owner'].core.queue.mutex._is_owned(),
         'RESOURCE_EPOCH_NO_IO_OR_WAIT_UNDER_SCIENCE_LOCKS')
    return r


def _guard(r, budget, *, before_pointer):
    import durable_service_source_controls as C
    _sources()
    A._budget(budget)
    archive = r['archive']
    need(type(archive) is A.PreservedResourceEpoch and archive._seal is A._SEAL
         and A._REGISTERED.get(id(archive)) is archive and archive._owner is r['owner']
         and archive._ticket is r['ticket'] and archive._thread == threading.get_ident()
         and archive.OWN is r['OWN'], 'RESOURCE_EPOCH_EXACT_REGISTERED_PRESERVED_ARCHIVE')
    verifier = C.verify_OWN_reference if r['OWN'] else C.verify_reference
    source = verifier(archive._reference, owner=r['owner'], ticket=r['ticket'], read_budget=budget)
    need(source.snapshot() == r['history']._source.snapshot()
         and source.old_owner_birth == r['history']._source.old_owner_birth
         and source.new_owner_birth == r['birth'], 'RESOURCE_EPOCH_SAME_T_SOURCE_NEW_BIRTH_AND_THREE_LOCKS')
    A._closed_leaf(archive, budget)
    if before_pointer:
        verify = A.verify_OWN_before_transition if r['OWN'] else A.verify_before_transition
        verify(archive, owner=r['owner'], ticket=r['ticket'], read_budget=budget)
    else:
        # Only the canonical pointer was atomically replaced. Every other old
        # original remains exact; the old pointer raw bytes are in the sealed archive.
        for row in archive._body['copies']:
            original = row['original']
            if Path(original['path']) == r['pointer']:
                continue
            A._read(Path(original['path']), mode=original['identity'][4] & 0o777,
                limit=original['identity'][6], budget=budget, expected=original)


def _failure(r, error, budget):
    r['failure_type'] = type(error).__name__
    path = r['root'] / 'TRANSITION_FAILURE_PUBLIC.json'
    if not os.path.lexists(path):
        try:
            _write(path, dict(schema='count14-resource-epoch-failure-retained-v1',
                state=r['state'], exception_type=r['failure_type'], physical_child_exit_code=r['child_exit'],
                physical_pointer=r['physical_pointer'], automatic_retries=0, models=0), budget)
        except Exception:
            pass  # Keep the real partial and original exception; never retry the operation.


def _checked_sampler_sources(configuration):
    # Same original NativeResourceProducer constructor checks, without calling
    # that first-cold constructor on an existing producer directory.
    from native_resource_producer import ResourceSamplerSources
    from native_system_health import executable
    from native_resource_sampler import read_public
    arguments = dict(configuration['sources'])
    for key in ('python', 'child', 'factory_manifest'):
        arguments[key] = Path(arguments[key])
    sources = ResourceSamplerSources(**arguments)
    python = executable(sources.python, sources.python_sha256)
    child = Path(sources.child)
    metadata = child.lstat()
    need(child.name == 'native_resource_sample_child.py' and child.resolve() == child
         and stat.S_ISREG(metadata.st_mode) and not metadata.st_mode & 0o022
         and metadata.st_uid in (0, os.geteuid())
         and hashlib.sha256(child.read_bytes()).hexdigest() == sources.child_sha256,
         'DYNTEAM_RESOURCE_FROZEN_FINITE_CHILD_SOURCE')
    bootstrap = child.with_name('native_cold_owner_entry.py')
    need(bootstrap.resolve() == bootstrap and not bootstrap.is_symlink()
         and hashlib.sha256(bootstrap.read_bytes()).hexdigest() == sources.bootstrap_sha256,
         'DYNTEAM_RESOURCE_SAME_COLD_ENTRY_IMPORT_BOOTSTRAP')
    _, factory_raw = read_public(sources.factory_manifest)
    need(hashlib.sha256(factory_raw).hexdigest() == sources.factory_manifest_sha256,
         'DYNTEAM_RESOURCE_FROZEN_IMPORT_ONLY_FACTORY_MANIFEST')
    return python


def _observe(archive, *, owner, ticket, read_budget, own):
    _sources()
    verify = A.verify_OWN_before_transition if own else A.verify_before_transition
    body = verify(archive, owner=owner, ticket=ticket, read_budget=read_budget)
    history = archive._history
    cfg = history._snapshot['configuration']
    need(body['resource_history_public']['registered'] is True and type(cfg) is dict,
         'RESOURCE_EPOCH_REGISTERED_ORIGINAL_PLAN_REQUIRED_NOT_ABSENT_ZERO')
    need(time.monotonic_ns() >= cfg['next_due'], 'RESOURCE_EPOCH_WAIT_ORIGINAL_NEXT_DUE_NO_REBASE')
    key = (id(owner), history._source._reference['sha256'])
    need(key not in _ATTEMPTS, 'RESOURCE_EPOCH_ONCE_NEW_OWNER_NO_LAUNCH_RETRY')
    from native_peer_registry import process_birth
    birth = process_birth(os.getpid())
    core = owner.core
    job = dict(schema='count14-dynteam-finite-resource-intent-v1', owner=asdict(birth),
        contract_sha256=history._source.contract_sha256, inventory_sha256=cfg['inventory_sha256'],
        other_maximum_FP8_inflight=history._snapshot['plan']['other_maximum_FP8_inflight'],
        core_home=str(core.home), new_root=core.contract['arms'][0]['root'],
        trajectory_roots={t: row['root'] for t, row in core.rows.items()},
        ledger_path=str(core.ledger.home / 'ledger.sqlite'),
        system_registered=history._source.component('SYSTEM')['registered'],
        qualification_only=own, plan_path=cfg['plan_path'])
    need(core.qualification_only is own and job['owner'] != asdict(history._source.old_owner_birth),
         'RESOURCE_EPOCH_ACTUAL_NEW_OWNER_NOT_OLD_OBSERVATION_RELABELLING')
    parent = core.home / 'resources/new-owner-resource-epochs-v1'
    if not os.path.lexists(parent):
        parent.mkdir(mode=0o700)
    A._directory(parent, read_budget)
    root = parent / f'{birth.pid}-{birth.start_ticks}'
    _ATTEMPTS[key] = dict(path=str(root), state='STARTING_RETAIN_ALL_PARTIALS_NO_RETRY')
    root.mkdir(mode=0o700)
    cap = object.__new__(ResourceEpoch)
    cap._seal = _SEAL
    r = dict(cap=cap, owner=owner, ticket=ticket, history=history, archive=archive,
        birth=birth, thread=threading.get_ident(), OWN=own, job=job,
        root=root, root_identity=A._directory(root, read_budget),
        pointer=core.home / 'resources/COHORT_RESOURCES_PUBLIC.json', sequence=cfg['sequence'] + 1,
        state='STARTING_RETAINED', child=None, child_birth=None, child_exit=None,
        publication_attempted=False, physical_pointer='UNCHANGED', refs={}, child_terminal_wall_ns=None,
        result=None, canonical=None, value=None, pointer_ref=None, failure_type=None)
    _REG[id(cap)] = r
    try:
        _guard(r, read_budget, before_pointer=True)
        r['refs']['epoch_intent'] = _write(root / 'EPOCH_INTENT_PUBLIC.json', dict(
            schema='count14-new-owner-resource-epoch-intent-v1', OWN=own,
            source_module_sha256=_sources(), source_pins=dict(PINS), old_sequence=cfg['sequence'],
            new_sequence=r['sequence'], original_next_due=cfg['next_due'],
            old_owner=asdict(history._source.old_owner_birth), new_owner=asdict(birth),
            preserved_archive=archive._manifest, preserved_issued=archive._issued,
            observation_is_not_admission=True, models=0), read_budget)
        r['refs']['intent'] = _write(root / 'INTENT_PUBLIC.json', job, read_budget)
        pins = cfg['sources']
        python = _checked_sampler_sources(cfg)
        argv = [python, '-I', '-B', pins['child'], '--intent', str(root / 'INTENT_PUBLIC.json'),
            '--intent-sha256', r['refs']['intent']['sha256'], '--factory', pins['factory_manifest'],
            '--factory-sha256', pins['factory_manifest_sha256'], '--bootstrap-sha256', pins['bootstrap_sha256']]
        r['argv'], r['started_wall_ns'], r['started_mono_ns'] = argv, time.time_ns(), time.monotonic_ns()
        # The original fixed child owns its real55s alarm and original projections.
        r['child'] = subprocess.Popen(argv, cwd='/', stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=dict(PATH='/usr/bin:/bin', LANG='C.UTF-8', PYTHONDONTWRITEBYTECODE='1'))
        r['child_birth'] = process_birth(r['child'].pid)
        r['state'] = 'OBSERVATION_RUNNING'
    except Exception as error:
        r['state'] = 'NOT_STARTED_RETAINED' if r['child'] is None else 'STARTED_BIRTH_UNAVAILABLE_RETAINED'
        _failure(r, error, read_budget)
    return cap


def observe(archive, *, owner, ticket, read_budget):
    return _observe(archive, owner=owner, ticket=ticket, read_budget=read_budget, own=False)


def observe_OWN(archive, *, owner, ticket, read_budget):
    return _observe(archive, owner=owner, ticket=ticket, read_budget=read_budget, own=True)


def _observation_interval(observed_ns, *, started_wall_ns, terminal_wall_ns, now_ns):
    # These bounds come from the retained real Popen, not from caller JSON.
    # A cached pre-launch observation is refused, never restamped. The original
    # separate60s publication TTL remains unchanged below.
    need(all(type(v) is int for v in (observed_ns, started_wall_ns, terminal_wall_ns, now_ns))
         and 0 < started_wall_ns <= observed_ns <= terminal_wall_ns <= now_ns,
         'RESOURCE_EPOCH_NEW_OBSERVATION_WITHIN_RETAINED_REAL_CHILD_LAUNCH_INTERVAL')


def _result(r, budget):
    import retired_resource_history as R
    from native_resource_sampler import allocation_envelope
    need(type(r['child']) is subprocess.Popen and r['child'].poll() == 0
         and r['child_birth'] is not None and r['child'].args == r['argv'],
         'RESOURCE_EPOCH_REAL_RETAINED_POPEN_EXIT0_AND_EXACT_ARGV')
    raw, intent = A._read(r['root'] / 'INTENT_PUBLIC.json', mode=0o600, limit=131072,
                          budget=budget, expected=r['refs']['intent'])
    need(R._object(raw) == r['job'], 'RESOURCE_EPOCH_ORIGINAL_FIXED_INTENT_UNCHANGED')
    raw, reference = A._read(r['root'] / 'RESULT_PUBLIC.json', mode=0o600, limit=131072, budget=budget)
    result = R._object(raw)
    need(set(result) == {'schema','intent_sha256','factory_constructor_called','owner','value'}
         and result['schema'] == 'count14-dynteam-finite-resource-result-v1'
         and result['intent_sha256'] == intent['sha256'] and result['owner'] == asdict(r['birth'])
         and result['factory_constructor_called'] is False, 'RESOURCE_EPOCH_ACTUAL_ORIGINAL_CHILD_NEW_OWNER_RESULT')
    value = result['value']
    need(type(value) is dict and value['schema'] == 'count14-seed46-global-resource-admission-v1'
         and value['dynteam_allocation'] == allocation_envelope(r['job'])
         and value['qualification_only'] is r['OWN'] and value['models'] == 0
         and (r['OWN'] or value['OWN_fixture_host_projection_used'] is False)
         and type(value['observed_ns']) is int and 0 < value['observed_ns'] <= time.time_ns(),
         'RESOURCE_EPOCH_EXACT_SOURCE_VALUES_NEVER_RESTAMPED_OR_GREEN_SUBSTITUTE')
    _observation_interval(value['observed_ns'], started_wall_ns=r['started_wall_ns'],
        terminal_wall_ns=r['child_terminal_wall_ns'], now_ns=time.time_ns())
    canonical = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    need(len(canonical) <= 131072, 'RESOURCE_EPOCH_BOUNDED_ORIGINAL_NUMERIC_POINTER')
    return result, reference, canonical


def poll(epoch, *, read_budget):
    r = _registered(epoch)
    A._budget(read_budget)
    if r['state'] != 'OBSERVATION_RUNNING':
        return epoch.public()
    code = r['child'].poll()
    if code is None:
        return epoch.public()
    r['child_exit'] = code
    r['child_terminal_wall_ns'] = time.time_ns()  # First genuine parent observation of this physical terminal.
    try:
        _guard(r, read_budget, before_pointer=True)
        need(code == 0, 'RESOURCE_EPOCH_FAILED_FINITE_CHILD_RETAINED_NO_PUBLICATION')
        result, reference, canonical = _result(r, read_budget)
        r['result'], r['value'], r['canonical'] = result, result['value'], canonical
        r['refs']['result'] = reference
        r['refs']['custody'] = _write(r['root'] / 'OBSERVATION_CUSTODY_PUBLIC.json', dict(
            schema='count14-resource-epoch-physical-custody-v1', child_birth=asdict(r['child_birth']),
            new_owner=asdict(r['birth']), argv=r['argv'], actual_exit_code=code,
            started_wall_ns=r['started_wall_ns'], completed_wall_ns=time.time_ns(),
            first_observed_terminal_wall_ns=r['child_terminal_wall_ns'],
            original_finite_child=True, factory_constructor_called=False, models=0), read_budget)
        r['state'] = 'OBSERVATION_READY_UNPUBLISHED'
    except Exception as error:
        r['state'] = 'OBSERVATION_FAILED_RETAINED'
        _failure(r, error, read_budget)
    return epoch.public()


def _pointer_state(r, budget):
    if not os.path.lexists(r['pointer']):
        return 'ABSENT'
    try:
        raw, _ = A._read(r['pointer'], mode=0o444, limit=131072, budget=budget)
        if raw == r['canonical']:
            return 'NEW_ORIGINAL_OBSERVATION'
        old = r['archive']._body['old_pointer_copy']
        if old is not None and hashlib.sha256(raw).hexdigest() == old['original']['sha256']:
            return 'OLD_ARCHIVED_OBSERVATION'
    except Exception:
        pass
    return 'UNKNOWN_RETAINED'


def _publish(epoch, *, read_budget, own):
    r = _registered(epoch, own)
    A._budget(read_budget)
    need(r['state'] == 'OBSERVATION_READY_UNPUBLISHED' and not r['publication_attempted'],
         'RESOURCE_EPOCH_ONE_PUBLICATION_ATTEMPT_NO_REPLAY')
    r['publication_attempted'] = True
    try:
        _guard(r, read_budget, before_pointer=True)
        result, reference, canonical = _result(r, read_budget)
        need(reference == r['refs']['result'] and result == r['result'] and canonical == r['canonical'],
             'RESOURCE_EPOCH_NEW_RESULT_STILL_EXACT_BEFORE_COMMIT')
        need(0 <= time.time_ns() - r['value']['observed_ns'] <= 60 * 10**9,
             'RESOURCE_EPOCH_ORIGINAL_OBSERVATION_TTL_NOT_EXTENDED')
        r['refs']['transition_intent'] = _write(r['root'] / 'TRANSITION_INTENT_PUBLIC.json', dict(
            schema='count14-resource-epoch-pointer-transition-intent-v1', OWN=own,
            preserved_archive=r['archive']._manifest, preserved_issued=r['archive']._issued,
            old_pointer_copy=r['archive']._body['old_pointer_copy'],
            original_new_result=reference, new_owner=asdict(r['birth']),
            old_sequence=r['history']._snapshot['configuration']['sequence'], new_sequence=r['sequence'],
            original_next_due=r['history']._snapshot['configuration']['next_due'],
            new_value_sha256=hashlib.sha256(canonical).hexdigest(),
            source_observed_ns=r['value']['observed_ns'], restamped=False,
            observation_is_not_admission=True, models=0), read_budget)
        candidate = r['root'] / 'POINTER_CANDIDATE_PUBLIC.json'
        A._write(candidate, canonical, read_budget)
        # Last original T/three-lock/history/pointer guard immediately before replace.
        _guard(r, read_budget, before_pointer=True)
        r['state'] = 'POINTER_REPLACEMENT_ATTEMPTED_RETAINED'
        os.replace(candidate, r['pointer'])
        A._sync(r['pointer'].parent)
        r['physical_pointer'] = _pointer_state(r, read_budget)
        need(r['physical_pointer'] == 'NEW_ORIGINAL_OBSERVATION', 'RESOURCE_EPOCH_PHYSICAL_POINTER_NOT_ASSUMED')
        _, r['pointer_ref'] = A._read(r['pointer'], mode=0o444, limit=131072, budget=read_budget)
        r['refs']['published'] = _write(r['root'] / 'PUBLISHED_PUBLIC.json', dict(
            schema='count14-dynteam-resource-published-v1', source_observed_ns=r['value']['observed_ns'],
            value_sha256=hashlib.sha256(canonical).hexdigest(), restamped=False,
            observation_is_not_admission=True, models=0), read_budget)
        _guard(r, read_budget, before_pointer=False)
        r['refs']['complete'] = _write(r['root'] / 'TRANSITION_COMPLETE_PUBLIC.json', dict(
            schema='count14-resource-epoch-transition-complete-v1', OWN=own,
            source_module_sha256=_sources(), source_pins=dict(PINS),
            preserved_archive=r['archive']._manifest, preserved_issued=r['archive']._issued,
            old_owner=asdict(r['history']._source.old_owner_birth), new_owner=asdict(r['birth']),
            old_sequence=r['history']._snapshot['configuration']['sequence'], new_sequence=r['sequence'],
            original_next_due=r['history']._snapshot['configuration']['next_due'],
            pointer=r['pointer_ref'], new_result=r['refs']['result'], published=r['refs']['published'],
            restamped=False, observation_is_not_admission=True,
            manager_native_paid_runtime_restored=False, models=0), read_budget)
        A._sync(r['root'])
        r['state'] = 'TRANSITION_COMPLETE'
    except Exception as error:
        r['physical_pointer'] = _pointer_state(r, read_budget)
        r['state'] = 'TRANSITION_PARTIAL_RETAINED_NO_RETRY'
        _failure(r, error, read_budget)
        raise
    return epoch.public()


def publish(epoch, *, read_budget):
    return _publish(epoch, read_budget=read_budget, own=False)


def publish_OWN(epoch, *, read_budget):
    return _publish(epoch, read_budget=read_budget, own=True)


def _verify_complete(epoch, *, read_budget, own):
    r = _registered(epoch, own)
    need(r['state'] == 'TRANSITION_COMPLETE' and r['publication_attempted'],
         'RESOURCE_EPOCH_ONLY_TRUE_COMPLETE_TRANSITION')
    _guard(r, read_budget, before_pointer=False)
    need(_result(r, read_budget) == (r['result'], r['refs']['result'], r['canonical']),
         'RESOURCE_EPOCH_COMPLETED_RESULT_NOT_REPLACED')
    raw, _ = A._read(r['pointer'], mode=0o444, limit=131072,
                     budget=read_budget, expected=r['pointer_ref'])
    need(raw == r['canonical'], 'RESOURCE_EPOCH_CURRENT_POINTER_IS_EXACT_ORIGINAL_NEW_CHILD_VALUE')
    for reference in r['refs'].values():
        A._read(Path(reference['path']), mode=0o600, limit=131072,
            budget=read_budget, expected=reference)
    expected = {Path(v['path']).name for v in r['refs'].values()}
    names = set()
    for path in r['root'].iterdir():
        read_budget.check()
        need(len(names) < len(expected), 'RESOURCE_EPOCH_NO_UNKNOWN_TRANSITION_LEAF')
        names.add(path.name)
    need(names == expected and A._directory(r['root'], read_budget) == r['root_identity'],
         'RESOURCE_EPOCH_CLOSED_COMPLETE_TRANSITION_CONTROL_SET')
    return dict(schema='count14-resource-epoch-verified-control-binding-v1', OWN=own,
        old_owner=asdict(r['history']._source.old_owner_birth), new_owner=asdict(r['birth']),
        archive=r['archive']._manifest, archive_issued=r['archive']._issued,
        new_sequence=r['sequence'], original_next_due=r['history']._snapshot['configuration']['next_due'],
        pointer=r['pointer_ref'], original_new_controls=copy.deepcopy(r['refs']),
        pointer_is_original_new_child_result=True, old_pointer_preserved_as_exact_archived_bytes=True,
        resource_manager_or_native_paid_runtime_restored=False, next_source_issuance_authority=False,
        safe_to_TERM=False, paid_activation_authorized=False, whole_runnable_ready=False)


def verify_complete(epoch, *, read_budget):
    return _verify_complete(epoch, read_budget=read_budget, own=False)


def verify_OWN_complete(epoch, *, read_budget):
    return _verify_complete(epoch, read_budget=read_budget, own=True)
