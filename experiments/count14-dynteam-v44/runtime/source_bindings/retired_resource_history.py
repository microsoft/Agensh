"""Read-only retired sampler history, never a sampler/owner/paid receiver.

Original typed T + new-birth metadata pair + three owned locks must verify
before any historical control read. Raw controls were closed INSIDE the real
old-source cap. No caller index, fresh health bool, constructor, Popen, poll,
pointer write/restamp, directory repair or scientific action is accepted.
"""
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import importlib
import json
import os
import stat

PINS = {
    'durable_service_source_controls': 'fe5cbbbb186e4d9049895f68c32529d8237d6ffbeda35d03b8ed15a0482f0b83',
    'source_services_controls': 'f7c72e41dc7df2940917ad664d582308ab936387c0b5190a21e2c07bac2d55db',
    'native_resource_producer': 'c1187cd5195a3b431a6eabd330578bd911ebe3fc4405a1358944d750df48be07',
    'native_resource_sampler': '880ae285ee18ad75e4aec3ccc4aa024f63a8423128834c6468b885606349cec3',
}
CONTRACTS = frozenset((
    '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391',
    '3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937'))
_SEAL = object()


def need(ok, code):
    if not ok:
        raise ValueError(code)


def verify_sources():
    for name, pin in PINS.items():
        p = Path(importlib.import_module(name).__file__); s = p.lstat()
        need(p.resolve() == p and stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and
             s.st_uid in (0, os.geteuid()) and not s.st_mode & 0o022 and
             hashlib.sha256(p.read_bytes()).hexdigest() == pin,
             'RESOURCE_HISTORY_EXACT_ORIGINAL_SOURCE_MODULES')


def _token(s):
    return [s.st_dev, s.st_ino, s.st_uid, s.st_gid, s.st_mode, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def _directory(p, budget):
    budget.check(); s = p.lstat()
    need(p.is_absolute() and p.resolve() == p and stat.S_ISDIR(s.st_mode) and
         s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == 0o700,
         'RESOURCE_HISTORY_EXACT_CANONICAL_PRIVATE_DIRECTORY')
    return [s.st_dev, s.st_ino, s.st_uid, s.st_gid, s.st_mode]


def _control(p, budget, *, mode):
    budget.check(); s = p.lstat()
    need(p.is_absolute() and p.resolve() == p and stat.S_ISREG(s.st_mode) and
         s.st_uid == os.geteuid() and s.st_nlink == 1 and
         stat.S_IMODE(s.st_mode) == mode and 0 < s.st_size <= 131072,
         'RESOURCE_HISTORY_BOUNDED_FIXED_PUBLIC_CONTROL')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd); raw = os.read(fd, 131073); b = os.fstat(fd)
        need(_token(s) == _token(a) == _token(b) == _token(p.lstat()) and len(raw) == s.st_size,
             'RESOURCE_HISTORY_STABLE_NOFOLLOW_CONTROL_FD')
    finally:
        os.close(fd)
    budget.check()
    return raw, dict(path=str(p), sha256=hashlib.sha256(raw).hexdigest(), identity=_token(s))


def _object(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'RESOURCE_HISTORY_DUPLICATE_CONTROL_KEY')
            value[key] = item
        return value
    def invalid(_):
        raise ValueError('RESOURCE_HISTORY_NONFINITE_CONTROL_VALUE')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    need(type(value) is dict, 'RESOURCE_HISTORY_PUBLIC_OBJECT_ONLY')
    return value


def _names(p, maximum, budget):
    result = []
    for x in p.iterdir():
        budget.check(); need(len(result) < maximum, 'RESOURCE_HISTORY_REGISTERED_LEAF_BOUND')
        result.append(x.name)
    return sorted(result)


def _read_bound(owner, row, old_birth, contract, *, own, budget):
    """Internal metadata parser. A caller dict alone produces NO capability."""
    need(type(row) is dict and type(row['registered']) is bool,
         'RESOURCE_HISTORY_EXPLICIT_ORIGINAL_PRESENCE')
    if not row['registered']:
        need(row == dict(registered=False, configuration=None, records=None),
             'RESOURCE_HISTORY_ABSENT_STAYS_UNKNOWN_NOT_EMPTY')
        return dict(registered=False, configuration=None, records=None,
                    public=dict(registered=False, sequence=None, source_history_complete=None)), []
    home = owner.core.home; cfg = row['configuration']; records = row['records']
    original = row['original_public']; closed = row['history_control_bindings']
    need(set(row) == {'registered','source_owner_birth','configuration','original_public','records',
                     'history_control_bindings','constructor_restarted'} and
         row['source_owner_birth'] == old_birth and row['constructor_restarted'] is False and
         set(cfg) == {'plan_path','inventory_sha256','sources','sequence','next_due','accepting',
                      'sourcehome','last_published','contract_sha256'} and
         cfg['contract_sha256'] == contract and cfg['sourcehome'] == str(home/'resources/producer') and
         cfg['accepting'] is False and type(cfg['sequence']) is int and 0 <= cfg['sequence'] <= 99999999 and
         type(cfg['next_due']) is int and cfg['next_due'] >= 0 and
         type(records) is list and len(records) == cfg['sequence'],
         'RESOURCE_HISTORY_COMPLETE_ORIGINAL_STOPPED_CONFIGURATION')
    need(set(original) == {'PUBLIC_code','sample_sequence','latest_state','accepting','latest_published_sha256',
                          'period_seconds','child_deadline_seconds','failures','models',
                          'another_owner_or_dispatcher_constructed','observation_is_not_admission'} and
         original['PUBLIC_code'] == 'DYNTEAM_SAME_OWNER_FINITE_RESOURCE_PRODUCER' and
         original['sample_sequence'] == cfg['sequence'] and original['accepting'] is False and
         original['latest_state'] == (None if not records else records[-1]['state']) and
         original['latest_published_sha256'] == cfg['last_published'] and
         original['period_seconds'] == 20 and original['child_deadline_seconds'] == 55 and
         original['models'] == 0 and original['another_owner_or_dispatcher_constructed'] is False and
         original['observation_is_not_admission'] is True and type(original['failures']) is list,
         'RESOURCE_HISTORY_ORIGINAL_PUBLIC_COUNTERS_AND_LIMITS')
    # Original NOT_STARTED failures can exceed32; never silently truncate them.
    for failure in original['failures']:
        budget.check()
        need(type(failure) is dict and set(failure) == {'exception_type','exit_code'} and
             type(failure['exception_type']) is str and
             (failure['exit_code'] is None or type(failure['exit_code']) is int),
             'RESOURCE_HISTORY_ORIGINAL_FAILURE_NONE_CODES_UNCHANGED')
    need(type(closed) is dict and set(closed) == {'schema','home','home_identity','record_directories',
             'control_references','pointer_present','pointer_reference','last_published_sha256'} and
         closed['schema'] == 'count14-original-sealed-resource-history-control-bindings-v1' and
         closed['home'] == cfg['sourcehome'] and type(closed['record_directories']) is list and
         len(closed['record_directories']) == len(records) and type(closed['control_references']) is list and
         type(closed['pointer_present']) is bool and closed['last_published_sha256'] == cfg['last_published'],
         'RESOURCE_HISTORY_CLOSED_INSIDE_ORIGINAL_SOURCE_NOT_CALLER_INDEX')
    producer = home/'resources/producer'
    identity = _directory(producer, budget)
    need(identity == closed['home_identity'], 'RESOURCE_HISTORY_ORIGINAL_HOME_IDENTITY')

    from native_resource_producer import ResourceSamplerSources
    from source_services_controls import sources
    pins = cfg['sources']
    need(set(pins) == set(ResourceSamplerSources.__dataclass_fields__),
         'RESOURCE_HISTORY_ORIGINAL_REGISTERED_CODE_CONFIGURATION')
    args = dict(pins)
    for key in ('python','child','factory_manifest'):
        need(type(args[key]) is str, 'RESOURCE_HISTORY_FIXED_REGISTERED_CODE_PATH')
        args[key] = Path(args[key])
    need(sources(ResourceSamplerSources(**args), budget) == pins and
         args['child'].name == 'native_resource_sample_child.py',
         'RESOURCE_HISTORY_ORIGINAL_CODE_RAW_PINS_STILL_MATCH')
    bootstrap = args['child'].with_name('native_cold_owner_entry.py')
    need(bootstrap.resolve() == bootstrap and not bootstrap.is_symlink() and
         hashlib.sha256(bootstrap.read_bytes()).hexdigest() == pins['bootstrap_sha256'],
         'RESOURCE_HISTORY_ORIGINAL_IMPORT_BOOTSTRAP_NOT_CONSTRUCTOR')
    plan_raw, plan_ref = _control(Path(cfg['plan_path']), budget, mode=0o444)
    plan = _object(plan_raw)
    need(plan_ref['sha256'] == cfg['inventory_sha256'] and
         plan['schema'] == 'count14-dynteam-resource-production-plan-v1' and
         plan['contract_sha256'] == contract and plan['no_active_unregistered_roots'] is True and
         plan['other_bound_is_full_allocations_plus_retained_UNKNOWN'] is True and
         (own or plan['OWN_fixture'] is None), 'RESOURCE_HISTORY_SAME_ORIGINAL_FROZEN_PLAN')
    from native_resource_sampler import allocation_envelope
    expected_roots = {t: r['root'] for t, r in owner.core.rows.items()}
    source_refs = closed['control_references']
    need(all(type(r) is dict and set(r) == {'path','sha256','identity'} and type(r['path']) is str
             for r in source_refs) and len({r['path'] for r in source_refs}) == len(source_refs),
         'RESOURCE_HISTORY_UNIQUE_CLOSED_CONTROL_REFERENCES')
    by_path = {r['path']: r for r in source_refs}
    seen = []; parsed = []; views = []; valid_values = []; receipts = []
    for seq, (record, view) in enumerate(zip(records, closed['record_directories']), 1):
        budget.check(); leaf = producer/f'{seq:08d}'
        need(set(record) == {'state','child_handle_present','child_returncode','intent_sha256','directory'} and
             record['directory'] == str(leaf) and type(record['child_handle_present']) is bool and
             record['state'] in ('OBSERVATION_PUBLISHED','FAILED_RETAINED','NOT_STARTED') and
             set(view) == {'sequence','path','identity','files'} and view['sequence'] == seq and
             view['path'] == str(leaf) and _directory(leaf, budget) == view['identity'],
             'RESOURCE_HISTORY_CONTIGUOUS_REGISTERED_TERMINAL_RECORDS')
        names = _names(leaf, 4, budget)
        need(names == view['files'] and 'INTENT_PUBLIC.json' in names and
             set(names) <= {'INTENT_PUBLIC.json','RESULT_PUBLIC.json','PUBLISHED_PUBLIC.json','FAILURE_PUBLIC.json'} and
             ('PUBLISHED_PUBLIC.json' not in names or 'RESULT_PUBLIC.json' in names),
             'RESOURCE_HISTORY_COMPLETE_FIXED_PUBLIC_CONTROL_SET')
        controls = {}
        for name in names:
            raw, reference = _control(leaf/name, budget, mode=0o600)
            need(by_path.get(str(leaf/name)) == reference,
                 'RESOURCE_HISTORY_RAW_CONTROL_EQUALS_OLD_SEALED_BINDING')
            controls[name] = raw; seen.append(reference)
        intent = _object(controls['INTENT_PUBLIC.json'])
        need(hashlib.sha256(controls['INTENT_PUBLIC.json']).hexdigest() == record['intent_sha256'] and
             set(intent) == {'schema','owner','contract_sha256','inventory_sha256','other_maximum_FP8_inflight',
                'core_home','new_root','trajectory_roots','ledger_path','system_registered','qualification_only','plan_path'} and
             intent['schema'] == 'count14-dynteam-finite-resource-intent-v1' and intent['owner'] == old_birth and
             intent['contract_sha256'] == contract and intent['inventory_sha256'] == cfg['inventory_sha256'] and
             intent['other_maximum_FP8_inflight'] == plan['other_maximum_FP8_inflight'] and
             intent['core_home'] == str(home) and intent['ledger_path'] == str(home/'ledger/ledger.sqlite') and
             intent['new_root'] == owner.core.contract['arms'][0]['root'] and intent['trajectory_roots'] == expected_roots and
             intent['plan_path'] == cfg['plan_path'] and intent['qualification_only'] is own and
             type(intent['system_registered']) is bool,
             'RESOURCE_HISTORY_EXACT_ORIGINAL_INTENT_OWNER_PLAN_ROOTS')
        if record['state'] == 'NOT_STARTED':
            need(record['child_handle_present'] is False and record['child_returncode'] is None and
                 names == ['INTENT_PUBLIC.json'], 'RESOURCE_HISTORY_NOT_STARTED_NEVER_FAKE_EXIT0')
        else:
            need(record['child_handle_present'] is True and type(record['child_returncode']) is int,
                 'RESOURCE_HISTORY_TRUE_SOURCE_PARENT_PHYSICAL_CHILD_TERMINAL')
        result = receipt = None; invalid_result = invalid_receipt = None
        encoded = None
        if 'RESULT_PUBLIC.json' in controls:
            try:
                result = _object(controls['RESULT_PUBLIC.json']); value = result['value']
                need(set(result) == {'schema','intent_sha256','factory_constructor_called','owner','value'} and
                     result['schema'] == 'count14-dynteam-finite-resource-result-v1' and
                     result['intent_sha256'] == record['intent_sha256'] and result['owner'] == old_birth and
                     result['factory_constructor_called'] is False and type(value) is dict and
                     value['schema'] == 'count14-seed46-global-resource-admission-v1' and
                     value['dynteam_allocation'] == allocation_envelope(intent) and
                     value['qualification_only'] is own and type(value['observed_ns']) is int and value['observed_ns'] > 0 and
                     value['models'] == 0 and (own or value['OWN_fixture_host_projection_used'] is False),
                     'RESOURCE_HISTORY_ORIGINAL_RESULT_NOT_NEW_OWNER_ADMISSION')
                encoded = (json.dumps(value, sort_keys=True, allow_nan=False)+'\n').encode()
            except (ValueError, KeyError, TypeError) as error:
                need(record['state'] == 'FAILED_RETAINED', 'RESOURCE_HISTORY_PUBLISHED_RESULT_MUST_BE_VALID')
                invalid_result = type(error).__name__; result = None
        if 'PUBLISHED_PUBLIC.json' in controls:
            try:
                receipt = _object(controls['PUBLISHED_PUBLIC.json'])
                need(result is not None and record['child_returncode'] == 0 and
                     receipt == dict(schema='count14-dynteam-resource-published-v1',
                        source_observed_ns=result['value']['observed_ns'],value_sha256=hashlib.sha256(encoded).hexdigest(),
                        restamped=False,observation_is_not_admission=True,models=0),
                     'RESOURCE_HISTORY_ORIGINAL_PUBLISHED_RESULT_HASH_AND_TIMESTAMP')
            except (ValueError, KeyError, TypeError) as error:
                need(record['state'] == 'FAILED_RETAINED', 'RESOURCE_HISTORY_PUBLISHED_RECEIPT_MUST_BE_VALID')
                invalid_receipt = type(error).__name__; receipt = None
        if record['state'] == 'OBSERVATION_PUBLISHED':
            need(record['child_returncode'] == 0 and names == ['INTENT_PUBLIC.json','PUBLISHED_PUBLIC.json','RESULT_PUBLIC.json'] and
                 result is not None and receipt is not None, 'RESOURCE_HISTORY_PUBLISHED_NEVER_INFERRED_FROM_FAILURE')
        if result is not None and record['child_returncode'] == 0:
            valid_values.append((seq, hashlib.sha256(encoded).hexdigest(), encoded))
        if receipt is not None:
            receipts.append((seq, receipt['value_sha256']))
        parsed.append(dict(sequence=seq, directory=leaf, state=record['state'], child=None,
            child_returncode=record['child_returncode'], intent_sha256=record['intent_sha256'], job=intent,
            result=result, receipt=receipt, retained_result_validation_error=invalid_result,
            retained_receipt_validation_error=invalid_receipt, failure_control_present='FAILURE_PUBLIC.json' in names))
        views.append((leaf, view))
    need(len(seen) == len(source_refs) and {r['path'] for r in seen} == set(by_path),
         'RESOURCE_HISTORY_NO_UNREGISTERED_OR_OMITTED_SOURCE_CONTROL')
    pointer = home/'resources/COHORT_RESOURCES_PUBLIC.json'; pointer_ref = None
    latest_receipt = None
    if closed['pointer_present']:
        raw, pointer_ref = _control(pointer, budget, mode=0o444)
        need(pointer_ref == closed['pointer_reference'] and pointer_ref['sha256'] == cfg['last_published'] and
             any(pin == cfg['last_published'] and encoded == raw for seq, pin, encoded in valid_values),
             'RESOURCE_HISTORY_ORIGINAL_POINTER_EXACT_SOURCE_RESULT_NOT_RESTAMPED')
        latest_receipt = bool(receipts and receipts[-1][1] == cfg['last_published'])
    else:
        need(closed['pointer_reference'] is None and cfg['last_published'] is None and not os.path.lexists(pointer),
             'RESOURCE_HISTORY_ABSENT_POINTER_NEVER_HEALTHY_ZERO')
    for reference in seen:
        _, again = _control(Path(reference['path']), budget, mode=0o600)
        need(again == reference, 'RESOURCE_HISTORY_CONTROL_DRIFT_DURING_SCAN')
    for leaf, view in views:
        need(_directory(leaf, budget) == view['identity'] and _names(leaf, 4, budget) == view['files'],
             'RESOURCE_HISTORY_RECORD_DIRECTORY_DRIFT_DURING_SCAN')
    if pointer_ref is not None:
        need(_control(pointer, budget, mode=0o444)[1] == pointer_ref, 'RESOURCE_HISTORY_POINTER_DRIFT_DURING_SCAN')
    else:
        need(not os.path.lexists(pointer), 'RESOURCE_HISTORY_POINTER_APPEARED_DURING_SCAN')
    need(_directory(producer, budget) == identity and
         _names(producer, len(records), budget) == [f'{seq:08d}' for seq in range(1,len(records)+1)] and
         _control(Path(cfg['plan_path']), budget, mode=0o444)[1] == plan_ref,
         'RESOURCE_HISTORY_HOME_PLAN_OR_LEAVES_DRIFT_DURING_SCAN')
    public = dict(registered=True, sequence=cfg['sequence'], original_public=copy.deepcopy(original),
        source_history_complete=True, pointer_present=closed['pointer_present'],
        last_pointer_has_complete_original_receipt=latest_receipt,
        old_observation_reused_for_new_owner_admission=False, resource_sampler_restored=False,
        failed_records=sum(r['state']=='FAILED_RETAINED' for r in parsed),
        NOT_STARTED_records=sum(r['state']=='NOT_STARTED' for r in parsed))
    return dict(registered=True, configuration=copy.deepcopy(cfg), records=parsed, plan=plan, public=public), seen+([pointer_ref] if pointer_ref else [])


class VerifiedResourceHistory:
    __slots__ = ('_snapshot','_references','_source','_seal','OWN')
    def __init__(self, *a, **k):
        raise ValueError('RESOURCE_HISTORY_ONLY_ORIGINAL_TYPED_NEW_BIRTH_VERIFIER')
    def __setattr__(self, name, value):
        need(not hasattr(self, '_seal'), 'RESOURCE_HISTORY_IMMUTABLE_METADATA_CAPABILITY')
        object.__setattr__(self, name, value)
    def public(self):
        need(self._seal is _SEAL, 'RESOURCE_HISTORY_ORIGINAL_VERIFIED_SEAL')
        return copy.deepcopy(self._snapshot['public'])
    @property
    def safe_to_TERM(self): return False
    @property
    def resource_sampler_restored(self): return False
    @property
    def paid_activation_authorized(self): return False
    @property
    def whole_runnable_ready(self): return False


def _read(reference, *, owner, ticket, read_budget, own):
    verify_sources()
    import durable_service_source_controls as C
    from bounded_metadata_ro import ReadBudget
    need(type(read_budget) is ReadBudget, 'RESOURCE_HISTORY_ORIGINAL_FINITE_METADATA_BUDGET')
    verify = C.verify_OWN_reference if own else C.verify_reference
    source = verify(reference, owner=owner, ticket=ticket, read_budget=read_budget)
    need(type(source) is C.VerifiedRetiredServiceControls and source.OWN is own and
         source.old_owner_birth.boot_id == source.new_owner_birth.boot_id,
         'RESOURCE_HISTORY_ORIGINAL_TYPED_NEW_BIRTH_THREE_LOCKS_CAPABILITY')
    if own:
        need(owner.core.qualification_only is True and owner.core.home.name.startswith('OWN-'),
             'RESOURCE_HISTORY_OWN_NAMESPACE_NEVER_PRODUCTION')
    else:
        need(owner.core.qualification_only is False and source.contract_sha256 in CONTRACTS and
             owner.core.home == Path(owner.core.contract['arms'][0]['root'])/'owner',
             'RESOURCE_HISTORY_ONLY_EXACT_APPROVED_TWO_ARM_CONTRACTS')
    snapshot, refs = _read_bound(owner, source.component('resource'), asdict(source.old_owner_birth),
                                 source.contract_sha256, own=own, budget=read_budget)
    again = verify(reference, owner=owner, ticket=ticket, read_budget=read_budget)
    need(again.snapshot() == source.snapshot() and again.new_owner_birth == source.new_owner_birth and
         again._reference == source._reference, 'RESOURCE_HISTORY_SOURCE_AND_PAIR_STILL_CURRENT_AFTER_SCAN')
    result = object.__new__(VerifiedResourceHistory)
    result._snapshot, result._references, result._source, result.OWN = snapshot, tuple(refs), source, own
    result._seal = _SEAL
    return result


def read_history(reference, *, owner, ticket, read_budget):
    return _read(reference, owner=owner, ticket=ticket, read_budget=read_budget, own=False)


def read_OWN_history(reference, *, owner, ticket, read_budget):
    return _read(reference, owner=owner, ticket=ticket, read_budget=read_budget, own=True)
