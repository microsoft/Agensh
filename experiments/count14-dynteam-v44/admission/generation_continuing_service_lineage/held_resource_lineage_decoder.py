"""Third-birth OWN decoder for the immutable resource SOURCE ingredient.

This is NOT VerifiedResourceHistory, a T issuer/receiver, SYSTEM lineage or a
runtime-restoration capability. Original authority flags stay false. Production
entry deliberately refuses until true new T + joint SYSTEM provenance exists.
Only fixed registered infra metadata is read; no model/DB/daemon/launch/write.
"""
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import importlib
import os
import stat
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import ProcessBirth, process_birth
import resource_epoch_archive_v2 as A
import retired_resource_history as R

SOURCE_PIN = '62c754ed3c2e3e075f6b496c28ba165134242e9b731b1f6784cdb4adc2a28449'
MAX_BYTES = 32 * 1024 * 1024
FLAGS = ('next_SOURCE_receiver_authority', 'SYSTEM_lineage_qualified',
         'safe_to_TERM', 'paid_activation_authorized', 'whole_runnable_ready')
_SEAL = object()
_REG = {}
_ATTEMPTS = {}


def _budget(value):
    M.need(type(value) is ReadBudget, 'LINEAGE_DECODER_ORIGINAL_FINITE_BUDGET')
    value.check()


def verify_sources():
    module = importlib.import_module('held_resource_lineage_source')
    p = Path(module.__file__)
    s = p.lstat()
    M.need(p.is_absolute() and p.resolve() == p and stat.S_ISREG(s.st_mode)
           and s.st_nlink == 1 and not s.st_mode & 0o022
           and hashlib.sha256(p.read_bytes()).hexdigest() == SOURCE_PIN,
           'LINEAGE_DECODER_EXACT_ORIGINAL_SOURCE_INGREDIENT')
    module.verify_sources()
    p = Path(__file__)
    s = p.lstat()
    M.need(p.is_absolute() and p.resolve() == p and stat.S_ISREG(s.st_mode)
           and s.st_nlink == 1 and not s.st_mode & 0o022,
           'LINEAGE_DECODER_FROZEN_CANONICAL_SELF')
    return module


def _birth(old, budget):
    _budget(budget)
    current = process_birth(os.getpid())
    M.need(type(old) is ProcessBirth and old != current
           and all(getattr(old, k) == getattr(current, k) for k in (
               'uid', 'gid', 'boot_id', 'pid_namespace', 'mount_namespace', 'network_namespace')),
           'LINEAGE_DECODER_EXACT_DISTINCT_SOURCE_AND_NEW_BIRTH')
    # Do not mistake broken zombie namespace links for proof of absence.
    p = Path('/proc') / str(old.pid) / 'stat'
    try:
        raw = p.read_bytes()
    except FileNotFoundError:
        M.need(not os.path.lexists(p.parent), 'LINEAGE_DECODER_UNKNOWN_SOURCE_PHYSICAL_STATE')
    else:
        fields = raw[raw.rfind(b')') + 2:].split()
        M.need(int(fields[19]) != old.start_ticks,
               'LINEAGE_DECODER_ORIGINAL_SOURCE_BIRTH_MUST_PHYSICALLY_END')
    budget.check()
    return current


def _ref(value):
    M.need(type(value) is dict and set(value) == {'path', 'sha256', 'identity'}
           and type(value['path']) is str and type(value['sha256']) is str
           and len(value['sha256']) == 64
           and all(c in '0123456789abcdef' for c in value['sha256'])
           and type(value['identity']) is list and len(value['identity']) == 9
           and all(type(x) is int for x in value['identity']),
           'LINEAGE_DECODER_EXACT_RAW_REFERENCE_TYPES')
    p = Path(value['path'])
    M.need(p.is_absolute() and str(p) == value['path'], 'LINEAGE_DECODER_CANONICAL_FIXED_PATH')
    return p


def _semantic(s, raw, home, old, module, budget):
    """Pure control validation; no file/SQL/daemon reads and no authority."""
    _budget(budget)
    M.need(s['schema'] == 'count14-continuing-resource-closed-lineage-source-ingredient-v1'
           and s['OWN'] is True and s['source_owner_birth'] == asdict(old)
           and s['source_component_sha256'] == SOURCE_PIN
           and s['publisher_module_sha256'] == SOURCE_PIN and s['source_pins'] == module.PINS
           and all(s[k] is False for k in FLAGS), 'LINEAGE_DECODER_SOURCE_INGREDIENT_NOT_AUTHORITY')
    cfg = s['configuration']
    origin = s['origin_service_snapshot']
    ocfg = origin['resource']['configuration']
    rows = s['records']
    M.need(type(rows) is list and rows and len(rows) <= 100000
           and type(cfg['global_sequence']) is int and type(ocfg['sequence']) is int
           and 0 < ocfg['sequence'] < cfg['global_sequence'] <= 99999999
           and cfg['global_sequence'] == ocfg['sequence'] + len(rows)
           and cfg['sourcehome'] == str(home / 'resources/producer')
           and cfg['accepting'] is False and type(cfg['next_due']) is int
           and cfg['next_due'] >= 0 and cfg['inventory_sha256'] == ocfg['inventory_sha256']
           and s['contract_sha256'] == ocfg['contract_sha256']
           and origin['source_owner_birth'] == s['original_source_owner_birth']
           and origin['resource']['source_owner_birth'] == s['original_source_owner_birth'],
           'LINEAGE_DECODER_COMPLETE_GLOBAL_AND_ORIGINAL_BIRTH_CONFIGURATION')
    expected = {}

    def control(ref, path=None, mode=None):
        p = _ref(ref)
        M.need((path is None or p == path) and (mode is None or ref['identity'][4] & 0o777 == mode)
               and str(p) in raw and hashlib.sha256(raw[str(p)]).hexdigest() == ref['sha256']
               and len(raw[str(p)]) == ref['identity'][6], 'LINEAGE_DECODER_EXACT_CONTROL_RAW_BYTES')
        M.need(str(p) not in expected or expected[str(p)] == ref,
               'LINEAGE_DECODER_NO_CONFLICTING_CONTROL_REFERENCES')
        expected[str(p)] = ref
        return raw[str(p)]

    archive = R._object(control(s['origin_archive'], mode=0o444))
    control(s['origin_archive_issued'], Path(s['origin_archive']['path']).with_name('ISSUED_PUBLIC.json'), 0o444)
    M.need(archive['OWN'] is True and archive['old_owner'] == s['original_source_owner_birth']
           and archive['preserving_owner'] == asdict(old)
           and archive['configuration'] == ocfg
           and archive['contract_sha256'] == s['contract_sha256'],
           'LINEAGE_DECODER_ARCHIVE_AND_ORIGIN_SNAPSHOT_SAME_EPOCH')
    service_source = []
    archive_root = Path(s['origin_archive']['path']).parent
    M.need(Path(archive['archive_directory']) == archive_root and archive_root.is_relative_to(home),
           'LINEAGE_DECODER_FIXED_ORIGINAL_ARCHIVE_DIRECTORY')
    for row in archive['copies']:
        budget.check()
        b = control(row['copy'], archive_root / row['name'], 0o444)
        M.need(hashlib.sha256(b).hexdigest() == row['original']['sha256'],
               'LINEAGE_DECODER_ARCHIVE_COPY_NOT_REWRITTEN_HISTORY')
        if row['kind'] == 'original_service_SOURCE':
            service_source.append(R._object(b))
    M.need(len(service_source) == 1 and service_source[0]['source_controls'] == origin,
           'LINEAGE_DECODER_EXACT_ORIGINAL_SERVICE_SNAPSHOT_FROM_ARCHIVED_BYTES')
    plan_raw = control(cfg['plan'], Path(ocfg['plan_path']), 0o444)
    M.need(hashlib.sha256(plan_raw).hexdigest() == cfg['inventory_sha256'],
           'LINEAGE_DECODER_ORIGINAL_PLAN_PIN')
    epoch = home / 'resources/new-owner-resource-epochs-v1' / f'{old.pid}-{old.start_ticks}'
    for ref in s['epoch_controls'].values():
        control(ref, epoch / Path(ref['path']).name, 0o600)
    latest = None
    states = []
    for i, row in enumerate(rows):
        budget.check()
        seq = ocfg['sequence'] + i + 1
        controls = row['controls']
        job = row['job']
        directory = epoch if i == 0 else home / 'resources/producer' / f'{seq:08d}'
        M.need(type(row['global_sequence']) is int and row['global_sequence'] == seq
               and row['kind'] == ('ORIGINAL_NEW_OWNER_EPOCH' if i == 0 else 'ORIGINAL_CADENCE')
               and job['owner'] == asdict(old) and job['core_home'] == str(home)
               and job['contract_sha256'] == s['contract_sha256']
               and job['inventory_sha256'] == cfg['inventory_sha256']
               and job['plan_path'] == ocfg['plan_path'] and job['qualification_only'] is True
               and job['system_registered'] is origin['SYSTEM']['registered'],
               'LINEAGE_DECODER_EACH_RECORD_ORIGINAL_OWNER_SEQUENCE_AND_JOB')
        M.need((i == 0 and row['subsequent_child_birth_not_reconstructed'] is False
                and type(row['actual_child_birth']) is dict
                and row['actual_child_birth']['pid'] == row['actual_child_pid'])
               or (i > 0 and row['subsequent_child_birth_not_reconstructed'] is True
                   and row['actual_child_birth'] is None),
               'LINEAGE_DECODER_NO_RECONSTRUCTED_SUBSEQUENT_CHILD_BIRTH')
        for name, ref in controls.items():
            M.need(type(name) is str and Path(name).name == name,
                   'LINEAGE_DECODER_FIXED_CONTROL_FILENAME')
            control(ref, directory / name, 0o600)
        intent = R._object(control(controls['INTENT_PUBLIC.json']))
        M.need(intent == job, 'LINEAGE_DECODER_EXACT_ORIGINAL_INTENT_JOB')
        state = row['state']
        exit_code = row['actual_child_returncode']
        M.need(exit_code is None or type(exit_code) is int,
               'LINEAGE_DECODER_EXACT_PHYSICAL_EXIT_CODE_NOT_BOOL')
        if i == 0:
            M.need(controls == {Path(v['path']).name: v for v in s['epoch_controls'].values()}
                   and state == 'OBSERVATION_PUBLISHED' and exit_code == 0,
                   'LINEAGE_DECODER_COMPLETE_FIRST_ORIGINAL_EPOCH')
        elif state == 'OBSERVATION_PUBLISHED':
            M.need(set(controls) == {'INTENT_PUBLIC.json', 'RESULT_PUBLIC.json', 'PUBLISHED_PUBLIC.json'}
                   and exit_code == 0, 'LINEAGE_DECODER_PUBLISHED_REQUIRES_TRUE_CHILD0')
        elif state == 'FAILED_RETAINED':
            M.need('PUBLISHED_PUBLIC.json' not in controls and type(row['actual_child_pid']) is int
                   and type(exit_code) is int and set(controls) <= {
                       'INTENT_PUBLIC.json', 'RESULT_PUBLIC.json', 'FAILURE_PUBLIC.json'},
                   'LINEAGE_DECODER_FAILED_STATE_NOT_PROMOTED_OR_CLEARED')
        else:
            M.need(state == 'NOT_STARTED' and exit_code is None and row['actual_child_pid'] is None
                   and set(controls) == {'INTENT_PUBLIC.json'},
                   'LINEAGE_DECODER_NOT_STARTED_IS_NOT_EXIT0')
        if state == 'OBSERVATION_PUBLISHED':
            result = R._object(control(controls['RESULT_PUBLIC.json']))
            published = R._object(control(controls['PUBLISHED_PUBLIC.json']))
            value = result['value']
            b = A._json(value)
            from native_resource_sampler import allocation_envelope
            M.need(result['owner'] == asdict(old)
                   and result['intent_sha256'] == controls['INTENT_PUBLIC.json']['sha256']
                   and result['factory_constructor_called'] is False and value['models'] == 0
                   and value['qualification_only'] is True
                   and value['dynteam_allocation'] == allocation_envelope(job)
                   and published['restamped'] is False
                   and published['source_observed_ns'] == value['observed_ns']
                   and published['value_sha256'] == hashlib.sha256(b).hexdigest(),
                   'LINEAGE_DECODER_ORIGINAL_RESULT_NO_RESTAMP_OR_NEW_ALLOCATION')
            latest = (seq, b)
        states.append(state)
    pointer = control(s['current_pointer'], home / 'resources/COHORT_RESOURCES_PUBLIC.json', 0o444)
    M.need(latest is not None and latest == (s['latest_published_global_sequence'], pointer)
           and cfg['last_published'] == hashlib.sha256(pointer).hexdigest(),
           'LINEAGE_DECODER_LATEST_TRULY_PUBLISHED_NOT_GLOBAL_LATEST_OR_RESTAMPED')
    public = cfg['original_public']
    M.need(public['sample_sequence'] == cfg['global_sequence'] and public['latest_state'] == states[-1]
           and public['latest_published_sha256'] == cfg['last_published']
           and public['accepting'] is False and public['period_seconds'] == 20
           and public['child_deadline_seconds'] == 55 and public['models'] == 0,
           'LINEAGE_DECODER_RETAIN_ORIGINAL_PUBLIC_LIMITS_AND_FAILURE_STATE')
    M.need(set(expected) == set(raw), 'LINEAGE_DECODER_EXACT_FULL_CONTROL_SET_NO_OMISSION_OR_EXTRA')
    return expected


def _load(reference, issued, *, home, source_birth, read_budget):
    _budget(read_budget)
    module = verify_sources()
    new = _birth(source_birth, read_budget)
    M.need(type(home) is type(Path('/')) and home.is_absolute() and home.resolve() == home,
           'LINEAGE_DECODER_INDEPENDENT_CANONICAL_OWN_HOME')
    root = home / module.OWN_LEAF / f'{source_birth.pid}-{source_birth.start_ticks}'
    M.need(_ref(reference) == root / 'SOURCE_PUBLIC.json'
           and _ref(issued) == root / 'ISSUED_PUBLIC.json',
           'LINEAGE_DECODER_EXACT_REGISTERED_OWN_SOURCE_NAMESPACE')
    A._directory(root, read_budget)
    A._directory(root / 'COPIES', read_budget)
    encoded, _ = A._read(Path(reference['path']), mode=0o444, limit=MAX_BYTES,
                         budget=read_budget, expected=reference)
    s = R._object(encoded)
    marker_raw, _ = A._read(Path(issued['path']), mode=0o444, limit=131072,
                            budget=read_budget, expected=issued)
    marker = R._object(marker_raw)
    original_body = {k: v for k, v in s.items()
                     if k not in ('preserved_control_copies', 'publisher_module_sha256')}
    M.need(marker == dict(schema='count14-resource-lineage-ingredient-ISSUED-v1', OWN=True,
               source=reference, source_owner_birth=asdict(source_birth),
               source_snapshot_sha256=hashlib.sha256(A._json(original_body)).hexdigest(),
               no_new_receiver_or_T_authority=True), 'LINEAGE_DECODER_EXACT_SOURCE_ISSUED_MARKER')
    pairs = s['preserved_control_copies']
    M.need(type(pairs) is list and 0 < len(pairs) <= 100000,
           'LINEAGE_DECODER_FINITE_COPY_SET')
    M.need(module._names(root, 4, read_budget) == {'COPIES', 'SOURCE_PUBLIC.json', 'ISSUED_PUBLIC.json'}
           and module._names(root / 'COPIES', len(pairs) + 1, read_budget)
               == {f'{i:06d}.raw' for i in range(len(pairs))},
           'LINEAGE_DECODER_EXACT_CLOSED_LEAF_SET')
    raw = {}
    refs = {}
    total = 0
    for i, pair in enumerate(pairs):
        original, copied = pair['original'], pair['copy']
        p = _ref(original)
        M.need(str(p) not in raw and _ref(copied) == root / 'COPIES' / f'{i:06d}.raw',
               'LINEAGE_DECODER_UNIQUE_FIXED_RAW_COPY_PATH')
        b, _ = A._read(Path(copied['path']), mode=0o444, limit=MAX_BYTES,
                       budget=read_budget, expected=copied)
        total += len(b)
        M.need(total <= MAX_BYTES and len(b) == original['identity'][6]
               and hashlib.sha256(b).hexdigest() == original['sha256'],
               'LINEAGE_DECODER_EXACT_BOUNDED_ORIGINAL_COPY_BYTES')
        raw[str(p)] = b
        refs[str(p)] = original
    exact = _semantic(s, raw, home, source_birth, module, read_budget)
    M.need(exact == refs, 'LINEAGE_DECODER_ALL_ORIGINAL_REFERENCE_IDENTITIES_RETAINED')
    # Validate fixed current originals only AFTER namespace and semantic closure.
    # Historical refs inside origin metadata are NEVER dereferenced as current.
    for p, r in exact.items():
        original, _ = A._read(Path(p), mode=r['identity'][4] & 0o777, limit=MAX_BYTES,
                              budget=read_budget, expected=r)
        M.need(original == raw[p], 'LINEAGE_DECODER_ORIGINAL_CHANGED_AFTER_COPY')
    M.need(_birth(source_birth, read_budget) == new, 'LINEAGE_DECODER_NEW_BIRTH_CHANGED_DURING_READ')
    return s, new


class DecodedOWNResourceLineage:
    def __init__(self, *a, **k):
        raise M.PaidColdWait('LINEAGE_DECODER_NO_METADATA_CAPABILITY_CONSTRUCTOR')

    def snapshot(self, *, read_budget):
        _budget(read_budget)
        r = _REG.get(id(self))
        M.need(type(self) is DecodedOWNResourceLineage and type(r) is dict
               and r['cap'] is self and r['seal'] is _SEAL
               and r['birth'] == process_birth(os.getpid()) and r['thread'] == threading.get_ident(),
               'LINEAGE_DECODER_SAME_REAL_NEW_BIRTH_THREAD_AND_REGISTRY')
        s, new = _load(**r['inputs'], read_budget=read_budget)
        M.need(s == r['body'] and new == r['birth'], 'LINEAGE_DECODER_SOURCE_CHANGED_RETAIN_FAILURE')
        return copy.deepcopy(s)


def decode_OWN(reference, issued, *, home, source_birth, read_budget):
    s, new = _load(reference, issued, home=home, source_birth=source_birth, read_budget=read_budget)
    key = (reference['sha256'], new)
    M.need(key not in _ATTEMPTS, 'LINEAGE_DECODER_ONCE_PER_SOURCE_NEW_BIRTH_NO_RETRY')
    _ATTEMPTS[key] = True
    cap = object.__new__(DecodedOWNResourceLineage)
    _REG[id(cap)] = dict(cap=cap, seal=_SEAL, birth=new, thread=threading.get_ident(), body=s,
        inputs=copy.deepcopy(dict(reference=reference, issued=issued, home=home, source_birth=source_birth)))
    return cap


def decode_registered(*a, **k):
    raise M.PaidColdWait('LINEAGE_DECODER_NOT_NEW_T_OR_JOINT_SYSTEM_OR_PRODUCTION_AUTHORITY')
