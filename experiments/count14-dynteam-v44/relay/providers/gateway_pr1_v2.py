"""Msg220 cold-only provider and OWN relay timing source, never admission.

No HTTP, credentials, response/body/CLI content, ledger writes, or actors.
Scientific transport code and original TTFT/rate validators stay unchanged.
The finite sampler receives a source-bound metadata aggregate in its original
durable intent. Missing observations remain unavailable, never zero/green.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
from types import CodeType, FunctionType, MethodType
import ast
import copy
import hashlib
import inspect
import math
import os
import textwrap
import time

OLD_BASE = _count14_os.environ.get('COUNT14_GLM_LEGACY_BASE_URL', 'https://glm-legacy-gateway.example.invalid/v1')
NEW_BASE = _count14_os.environ.get('COUNT14_GLM_BASE_URL', 'https://glm-gateway.example.invalid/v1')
APPROVAL = 'CARETAKER_USER_GLM_ENDPOINT_SWITCH_GATEWAY_PR1'
APPROVAL_AT = '2026-11-07T17:09:44+00:00'
FACTORY_PIN = '71de11f1bb3f778b9d4afc7ce965d18fd4f7ed9dcf49bcb6fdbf622cea9dd29f'
PRODUCER_PIN = '88a48dbf31752dea0d839cef0eb1e5322d3397d73287df52b6657e742fdbc5b3'
PRODUCER_PINS = {PRODUCER_PIN, 'c1187cd5195a3b431a6eabd330578bd911ebe3fc4405a1358944d750df48be07'}
# The second frozen original only adds newroot source selection in __init__; poll is identical.
SAMPLER_PIN = '880ae285ee18ad75e4aec3ccc4aa024f63a8423128834c6468b885606349cec3'
PROJECTION_PIN = '66ece9e044bdde4b0742941ae390a16c9eaaf18f38c61d342224007b86fbdf26'
HEADER_SCHEMA = 'count14-msg220-own-relay-provider-timing-source-v1'
HEADER_KEY = 'msg220_own_relay_timing'
_SEAL = object()
_CORES = {}



def _msg221_alias():
    import importlib.util
    p=Path(__file__).resolve().with_name('provider_model_alias.py')
    s=p.lstat()
    import stat
    if not (p.is_absolute() and p.resolve()==p and not p.is_symlink() and
            stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid in (0,os.geteuid()) and
            stat.S_IMODE(s.st_mode)==0o444 and
            hashlib.sha256(p.read_bytes()).hexdigest()=='5924a5b99af0ebc8f6cfedaa22ea40932300259049f97f513092ded21a54a981'):
        raise ValueError('MSG221_EXACT_FROZEN_PRIVATE_ALIAS_SOURCE')
    spec=importlib.util.spec_from_file_location('count14_msg221_private_provider_alias',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def need(ok, code):
    if not ok:
        raise ValueError('MSG220_' + code)


def number(v):
    return type(v) in (int, float) and math.isfinite(v) and v >= 0


def pinned_source(path, pin):
    p = Path(path)
    need(p.is_absolute() and p.resolve() == p and not p.is_symlink(), 'CANONICAL_SOURCE')
    b = p.read_bytes()
    need(hashlib.sha256(b).hexdigest() == pin, 'ORIGINAL_SOURCE_PIN')
    return b


def registered_scope(contract):
    """Extra scope restriction, not a substitute for original frozen contract."""
    need(type(contract) is dict and contract.get('schema') == 'count14-dynteam-two-arm-public-contract-v1',
         'ONLY_REGISTERED_TWO_NEW_ARMS')
    arms = contract['arms']
    need(type(arms) is list and len(arms) == 2 and
         {r['arm'] for r in arms} == {'DYNTEAM', 'DYNTEAM_RACING'} and
         contract['mode'] in ('smoke', 'production'), 'ONLY_TWO_ARM_GRID')
    for r in arms:
        p = Path(r['root'])
        need(p.is_absolute() and str(p) == r['root'] and '..' not in p.parts and
             p.is_relative_to((_C14_SCRATCH)) and p != Path((_C14_SCRATCH)) and
             not any('mockdebug' in x for x in p.parts), 'NO_OLD_OR_MOCK_ROOT')
    need(len(contract['trajectories']) == (2 if contract['mode'] == 'smoke' else 6),
         'ORIGINAL_TWO_OR_SIX_TRAJECTORIES')


def provider_change(*, actual_cutover_at=None):
    return dict(schema='count14-msg220-msg221-registered-provider-change-v2', approval=APPROVAL,
        approval_tags=list(_msg221_alias().APPROVALS), old_model_id=_msg221_alias().OLD_MODEL,
        new_model_id=_msg221_alias().NEW_MODEL, one_combined_provider_change=True,
        authorized_at=APPROVAL_AT, old_base_url=OLD_BASE, new_base_url=NEW_BASE,
        actual_cutover_at=actual_cutover_at,
        scope='DYNTEAM/DYNTEAM_RACING only; no mockdebug or old arms',
        key_headers_session_stream_retry_UNKNOWN_accounting_thresholds_unchanged=True,
        logical_historical_model_policy_immutable=True, model_alias_before_upstream_hash=True,
        TTFT_source='OWN original HeaderOpener first nonempty SSE; cold SYSTEM200 full latency conservative upper',
        old_gateway_metrics_used=False, target_recovery_qualified=False)


def override_bindings(bindings):
    need(type(bindings) is dict and type(bindings.get('provider')) is dict and
         bindings['provider'].get('base_url') == OLD_BASE, 'EXACT_OLD_PROVIDER_ONLY_ONCE')
    value = copy.deepcopy(bindings)
    value['provider']['base_url'] = NEW_BASE
    inverse = copy.deepcopy(value)
    inverse['provider']['base_url'] = OLD_BASE
    need(inverse == bindings, 'ONLY_BASE_URL_DEEP_INVERSE')
    return value


def _codes(code, name):
    result = [code] if code.co_name == name else []
    for c in code.co_consts:
        if type(c) is CodeType:
            result.extend(_codes(c, name))
    return result


def _cell(value):
    return (lambda: value).__closure__[0]


def select_transport_factory(original, *, contract, physical_factory_source=None):
    registered_scope(contract)
    need(type(original) is FunctionType, 'ORIGINAL_TRANSPORT_FUNCTION_TYPE')
    # co_filename is a compiler origin, not necessarily a filesystem path.
    # The explicit physical source is supplied only by the original typed
    # compiler's authenticated outer_arguments(create) result. Never split it.
    physical = Path(original.__code__.co_filename) if physical_factory_source is None else Path(physical_factory_source)
    allowed = (str(physical),) if physical_factory_source is None else (str(physical), str(physical) + ':pre-ledger-typed-input-prefix')
    need(original.__code__.co_filename in allowed, 'EXACT_PHYSICAL_OR_ORIGINAL_TYPED_PREFIX_FILENAME')
    raw = pinned_source(physical, FACTORY_PIN)
    codes = _codes(compile(raw, original.__code__.co_filename, 'exec', dont_inherit=True, optimize=__import__('sys').flags.optimize), 'transport')
    from feasibility_relay import ChatTransport
    need(len(codes) == 1 and original.__code__ == codes[0] and
         original.__code__.co_freevars == ('ChatTransport', 'b'), 'ORIGINAL_COMPLETE_TRANSPORT_CODE')
    cells = dict(zip(original.__code__.co_freevars, original.__closure__))
    need(cells['ChatTransport'].cell_contents is ChatTransport, 'ORIGINAL_TRANSPORT_CLASS_CLOSURE')
    b = cells['b'].cell_contents
    new = override_bindings(b)
    closure = tuple(_cell(new) if name == 'b' else cells[name] for name in original.__code__.co_freevars)
    selected = FunctionType(original.__code__, original.__globals__, original.__name__,
                            original.__defaults__, closure)
    selected.__kwdefaults__ = original.__kwdefaults__
    need(selected.__code__ is original.__code__ and cells['b'].cell_contents is b and
         selected.__closure__[0] is original.__closure__[0],
         'NO_ORIGINAL_FACTORY_GLOBAL_CLASS_OR_BINDING_MUTATION')
    return selected, dict(provider_change(), physical_factory_source=dict(path=str(physical), sha256=FACTORY_PIN), original_transport_co_filename=original.__code__.co_filename, original_complete_transport_CodeType_retained=True)


def nearest_rank_p95(values):
    need(type(values) is list and len(values) <= 8192 and all(number(v) for v in values),
         'EXACT_FINITE_TIMING_SAMPLES')
    if not values:
        return None
    rows = sorted(values)
    return rows[math.ceil(.95 * len(rows)) - 1]


def timing_aggregate(scientific, system, *, now_ns):
    """Only whitelisted scalar metadata, not request/response body objects."""
    need(type(now_ns) is int and now_ns > 0 and type(scientific) is list and type(system) is list,
         'TIMING_TYPED_INPUTS')
    values, seen = [], set()
    measured = upper = 0
    for rows in scientific:
        need(type(rows) is list and len(rows) < 10000, 'TIMING_RING_TRUNCATION_FAIL_CLOSED')
        for r in rows:
            need(type(r) is dict, 'TIMING_ROW')
            if r.get('kind') != 'FIRST_NONEMPTY_SSE_LINE':
                continue
            at, seconds = r['sent_at_ns'], r['seconds']
            need(type(at) is int and 0 < at <= now_ns and number(seconds), 'SSE_REAL_SOURCE_TIME')
            if now_ns - 600 * 10**9 < at <= now_ns:
                identity = (r['trajectory'], r['request_id'], at)
                need(type(identity[0]) is str and type(identity[1]) is str and identity not in seen,
                     'NO_DUPLICATE_OR_DECODED_REQUEST_ID')
                seen.add(identity)
                values.append(seconds)
                measured += 1
    for r in system:
        need(type(r) is dict, 'SYSTEM_TIMING_ROW')
        if r.get('upstream_base_url') != NEW_BASE:
            continue  # Old records remain in original cost/error history, not this backend's TTFT.
        if r['http_status'] != 200 or r['healthy'] is not True:
            continue
        at, seconds = r['completed_at_ns'], r['elapsed_seconds']
        need(type(at) is int and 0 < at <= now_ns and number(seconds), 'SYSTEM_REAL_TOTAL_LATENCY')
        if now_ns - 600 * 10**9 < at <= now_ns:
            values.append(seconds)
            upper += 1
    return dict(p95_seconds=nearest_rank_p95(values), sample_count=len(values),
                scientific_first_SSE_samples=measured, SYSTEM_total_latency_upper_samples=upper,
                empty_is_unavailable_not_zero=not values)


def _raw_transport(engine):
    from scientific_relay import ScientificRelay
    from feasibility_relay import ChatTransport
    from glm_session_header import HeaderOpener, Timings
    need(type(engine) is ScientificRelay and type(engine.transport) is FunctionType,
         'ORIGINAL_ENGINE_AND_TRANSPORT')
    cells = dict(zip(engine.transport.__code__.co_freevars,
                     (c.cell_contents for c in engine.transport.__closure__ or ())))
    raw = cells.get('transport')
    need(type(raw) is ChatTransport and raw.url == NEW_BASE + '/chat/completions' and
         raw.auth_style == 'bearer' and type(raw.opener) is HeaderOpener and
         raw.opener.url == raw.url and type(raw.opener.timings) is Timings,
         'NEW_PROVIDER_ORIGINAL_HEADER_AND_TIMINGS_NO_WRAPPERS')
    return raw


def observe_core(core):
    from original_relay_core import OriginalRelayCore
    from common import digest
    from native_peer_registry import process_birth
    import datetime
    need(type(core) is OriginalRelayCore, 'ORIGINAL_CORE_BEFORE_ATTRIBUTES')
    row = _CORES.get(id(core))
    need(row is not None and row['seal'] is _SEAL and row['core'] is core and
         process_birth(os.getpid()) == row['birth'] and not core.ledger.mutex._is_owned(),
         'ONLY_REGISTERED_NEW_OWNER_OUTSIDE_SCIENCE_LOCK')
    observed = time.time_ns()
    scientific = [_raw_transport(e).opener.timings.snapshot() for e in core.engines.values()]
    terminals = []
    health = getattr(core, 'system_health', None)
    if health is not None:
        for r in health.records:
            v = r.get('terminal')
            if (r['state'] != 'HTTP_PHYSICAL_TERMINAL' or r['exit_code'] != 0 or
                type(v) is not dict or v.get('upstream_base_url') != NEW_BASE):
                continue
            at = datetime.datetime.fromisoformat(v['completed_at'])
            need(at.tzinfo is not None, 'SYSTEM_ORIGINAL_TIMEZONE')
            terminals.append(dict(upstream_base_url=v['upstream_base_url'],
                http_status=v['http_status'], healthy=v['healthy'], elapsed_seconds=v['elapsed_seconds'],
                completed_at_ns=int(at.timestamp() * 10**9)))
    aggregate = timing_aggregate(scientific, terminals, now_ns=observed)
    from dataclasses import asdict
    return dict(schema=HEADER_SCHEMA, upstream_base_url=NEW_BASE, observed_ns=observed,
        owner=asdict(row['birth']), contract_sha256=digest(core.contract), **aggregate,
        original_error_window_counts_unchanged=True, old_gateway_metrics_used=False)


def _job(job, core):
    need(type(job) is dict and HEADER_KEY not in job, 'ORIGINAL_JOB_EXTENSION_ONCE')
    value = dict(job)
    value[HEADER_KEY] = observe_core(core)
    return value


def compile_producer_poll(original):
    need(type(original) is FunctionType, 'ORIGINAL_POLL_TYPE')
    source_path = Path(original.__code__.co_filename)
    need(source_path.is_absolute() and source_path.resolve() == source_path and not source_path.is_symlink(),
         'PRODUCER_CANONICAL_ORIGINAL_SOURCE')
    source_pin = hashlib.sha256(source_path.read_bytes()).hexdigest()
    need(source_pin in PRODUCER_PINS, 'EXACT_REVIEWED_ORIGINAL_PRODUCER_FAMILY')
    pinned_source(source_path, source_pin)
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    before = copy.deepcopy(tree)
    sites = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and len(n.targets) == 1 and
             isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'job']
    need(len(sites) == 1 and isinstance(sites[0].value, ast.Call) and
         ast.unparse(sites[0].value.func) == 'dict', 'ONE_ORIGINAL_JOB_DICT')
    sites[0].value = ast.Call(func=ast.Name(id='_msg220_job', ctx=ast.Load()),
        args=[sites[0].value, ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()),
              attr='core', ctx=ast.Load())], keywords=[])
    inverse = copy.deepcopy(tree)
    site = next(n for n in ast.walk(inverse) if isinstance(n, ast.Assign) and
                isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'job')
    site.value = site.value.args[0]
    need(ast.dump(inverse, include_attributes=False) == ast.dump(before, include_attributes=False),
         'FULL_POLL_INVERSE_AST_NO_LAUNCH_PERIOD_OR_ACCOUNTING_CHANGE')
    namespace = dict(original.__globals__, _msg220_job=_job)
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':original-poll-one-job-port', 'exec'), namespace)
    return namespace[original.__name__]


def install_new_producer(core):
    from original_relay_core import OriginalRelayCore
    from native_resource_producer import NativeResourceProducer
    from native_peer_registry import process_birth
    need(type(core) is OriginalRelayCore, 'ONLY_ORIGINAL_NEW_CORE')
    registered_scope(core.contract)
    need(id(core) not in _CORES and not core.closed and not core.scientific_activation_qualified and
         set(core.gate.startup_held) == set(core.rows), 'NOT_LIVE_OWNER_OR_SECOND_INSTALL')
    producer = core.resource_producer
    need(type(producer) is NativeResourceProducer and producer.sequence == 0 and not producer.records,
         'BEFORE_FIRST_ORIGINAL_RESOURCE_POLL')
    with core.ledger.mutex:
        need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0] == 0 and
             core.ledger.db.execute('SELECT COUNT(*) FROM aux_permits').fetchone()[0] == 0,
             'BEFORE_SCIENCE_OR_AUX_NO_RESET')
    for engine in core.engines.values():
        _raw_transport(engine)
    alias_proof=_msg221_alias().install_search_profile(core.profile,contract=core.contract)
    need(all(engine.profile is core.profile for engine in core.engines.values()),'ALL_ROLE_ENGINES_SAME_ALIASED_PROFILE')
    selected = compile_producer_poll(NativeResourceProducer.poll)
    _CORES[id(core)] = dict(core=core, birth=process_birth(os.getpid()), seal=_SEAL)
    producer.poll = MethodType(selected, producer)
    return dict(provider_change(), model_alias=alias_proof, original_poll_only_job_metadata_port=True,
                scientific_transport_or_header_or_timing_objects_changed=False,
                actual_cutover_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                admission_or_ACTIVATE_authorized=False)


def validate_header(header, job, *, now_ns=None):
    now_ns = time.time_ns() if now_ns is None else now_ns
    need(type(header) is dict and header.get('schema') == HEADER_SCHEMA and
         header.get('upstream_base_url') == NEW_BASE and header.get('owner') == job['owner'] and
         header.get('contract_sha256') == job['contract_sha256'], 'SAME_REAL_OWNER_PROVIDER_HEADER')
    at = header['observed_ns']
    need(type(at) is int and 0 <= now_ns - at <= 60 * 10**9, 'SOURCE_FRESH_NO_RESTAMP')
    n, m, u = (header[k] for k in ('sample_count', 'scientific_first_SSE_samples',
                                  'SYSTEM_total_latency_upper_samples'))
    need(all(type(v) is int and v >= 0 for v in (n, m, u)) and n == m + u and n <= 8192 and
         header['empty_is_unavailable_not_zero'] is (n == 0) and
         header['old_gateway_metrics_used'] is False and
         header['original_error_window_counts_unchanged'] is True, 'SOURCE_SAMPLE_COUNTS_NOT_BOOLEAN')
    p95 = header['p95_seconds']
    need((n == 0 and p95 is None) or (n > 0 and number(p95)), 'MISSING_NAN_NOT_HEALTHY')
    return p95


def select_sample(original, job, plan):
    """After exact18 selection; retain its complete scans/counts/lifecycle."""
    need(type(original) is FunctionType and original.__name__ == 'sample', 'ORIGINAL_SAMPLE_TYPE')
    pinned_source(original.__code__.co_filename, SAMPLER_PIN)
    header = job[HEADER_KEY]
    p95 = validate_header(header, job)
    outside = original.__globals__['outside_with_deadline']
    registered = outside.__globals__['registered_outside_projection']
    need(type(outside) is FunctionType and type(registered) is FunctionType,
         'EXACT18_ORIGINAL_PRIVATE_FUNCTIONS')
    pinned_source(outside.__code__.co_filename, SAMPLER_PIN)
    pinned_source(registered.__code__.co_filename, PROJECTION_PIN)
    previous_factory = registered.__globals__['frozen_observer']
    def private_observer():
        observer, performance = previous_factory()  # Includes original exact18 lifecycle guard.
        def own_ttft():
            value = validate_header(header, job)  # Recheck source age at actual use, not clone creation.
            need(value is not None, 'NO_REAL_NEW_BACKEND_TTFT_OBSERVATION')
            return value
        observer.ttft = own_ttft  # Newly privately imported observer, not live/shared module.
        return observer, performance
    selected_registered = FunctionType(registered.__code__,
        dict(registered.__globals__, frozen_observer=private_observer), registered.__name__,
        registered.__defaults__, registered.__closure__)
    selected_outside = FunctionType(outside.__code__,
        dict(outside.__globals__, registered_outside_projection=selected_registered),
        outside.__name__, outside.__defaults__, outside.__closure__)
    selected = FunctionType(original.__code__,
        dict(original.__globals__, outside_with_deadline=selected_outside), original.__name__,
        original.__defaults__, original.__closure__)
    for new, old in ((selected_registered, registered), (selected_outside, outside), (selected, original)):
        new.__kwdefaults__ = old.__kwdefaults__
        need(new.__code__ is old.__code__, 'ALL_COUNT_WINDOW_AND_SAMPLE_CODETYPES_IDENTICAL')
    return selected, dict(original_sample_outside_registered_CodeTypes_identical=True,
        original_exact18_factory_and_full_counts_retained=True,
        p95_seconds=p95, old_gateway_metrics_used=False, admission_qualified=False)
