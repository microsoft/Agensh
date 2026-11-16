"""Registered original FINAL control capture, NOT owner-lineage consumption.

No constructor/DDL/claim/reap/wait/config-file/candidate/result/private-body I/O.
Only original framework RAM controls, fixed PUBLIC receipts and private RO SQL.
Original authorization owner/domain/epoch values are retained, never retagged.
"""
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import importlib
import json
import os
import subprocess
import threading

from common import need, digest
from bounded_metadata_ro import ReadBudget, readonly, ram_lock
from fixed_queue_control_projection import projected_readonly
from observed_cut_control_witness import observed_six_cut_witness

SCHEMA = 'count14-paid-final-registered-source-control-CANDIDATE-v1'
PINS = dict(queue_control='a3b01a4712d958048d58ab8c9c3ebd1e78b7143728ac0d9686532fdd4d80d382',
    approved_queue_reader='d5c50721a656ba99448009281ed61374908773c1749bb0f3d56833d9936dea33',
    allowance_control='47d996bedd7b6fcd662238577d000a1690003d3422f4f60090998e8e2f08c090',
    native_final_dispatch='ad316ddeaf332178f31598539ff66c6ff4d79280e2c5149f152719cd2d212201',
    bounded_metadata_ro='621cd0db6da2d1e6422537f6ae2188ac8466627efe803d8b4d39f260bfb7c249')
JOB_FIELDS = ('id','point','replicate','state','claim','attempt','original_job',
              'trajectory','setting','target','input_root','input_policy')
CONFIG_FIELDS = ('schema','trajectory','k','input_root','input_policy_sha256','aux_root',
                 'native_directory','space_home','scope','host_socket','replicate_attempt','point_id')


def verify_sources():
    for name, pin in PINS.items():
        path = Path(importlib.import_module(name).__file__)
        need(path.resolve() == path and not path.is_symlink()
             and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
             'PAID_FINAL_CAPTURE_FIXED_ORIGINAL_SOURCE_PINS')
    return dict(PINS)


def unlocked(ledger, queue):
    need(not ledger.mutex._is_owned() and not queue.mutex._is_owned(),
         'PAID_FINAL_CAPTURE_NO_SQL_OR_FILE_IO_WITH_LIVE_SCIENCE_QUEUE_LOCK')


def job_controls(row):
    value = {k: copy.deepcopy(row[k]) for k in JOB_FIELDS if k in row}
    value.setdefault('attempt', 1)
    # Deliberately never project/hash/read a result file or config capability.
    return value


def queue_control_view(domain, *, read_budget):
    """Original all/effective and registration code on SAME DB's finite RO view.

    Exposed only to the focused OWN qualification; a result is never authority.
    Production entry below rejects OWN and validates the whole registered graph.
    """
    from budget import Ledger
    from final_queue import FinalQueue
    from queue_control import CarrierQueueDomain, AUTH
    from allowance_control import read_public
    from approved_queue_reader import ApprovedCarrierReader
    need(type(read_budget) is ReadBudget and type(domain) is CarrierQueueDomain
         and domain.installed and type(domain.q) is FinalQueue and type(domain.l) is Ledger,
         'PAID_FINAL_CAPTURE_EXACT_CURRENT_CARRIER_LEDGER_QUEUE_AND_BUDGET')
    l, q = domain.l, domain.q
    free = lambda: unlocked(l, q)
    free(); read_budget.check(); domain.fresh()
    descriptor = read_public(domain.descriptor, root=domain.home, expected=domain.pin)
    need(descriptor['owner'] == domain.owner, 'PAID_FINAL_CAPTURE_ORIGINAL_DESCRIPTOR_OWNER')
    reader = ApprovedCarrierReader(domain.descriptor, domain.pin, allow_OWN=domain.offline_OWN)
    installed = (None if domain.offline_OWN else read_public(domain.home/'APPROVED_INSTALL_PUBLIC.json',
        root=domain.home, expected=descriptor['installed_receipt_sha256']))
    # Original _bind_private_original_ports creates instance methods only on
    # a non-escaping RO metadata view, never on a restored runtime/paid object.
    with projected_readonly(q.home/'queue.sqlite', read_budget, free) as db:
        view = FinalQueue.__new__(FinalQueue)
        view.home, view.db, view.mutex = q.home, db, threading.RLock()
        carrier = CarrierQueueDomain.__new__(CarrierQueueDomain)
        carrier.q, carrier.l, carrier.owner, carrier.pin = view, l, domain.owner, domain.pin
        def no_runtime(*a, **k): need(False, 'PAID_FINAL_CAPTURE_RO_VIEW_NOT_RUNTIME')
        carrier._bind_private_original_ports(no_runtime)
        all_rows = carrier.attempts.all_rows(view)
        effective = carrier.attempts.effective_rows(view)
        partials = {r[0]: json.loads(r[1]) for r in db.execute(
            'SELECT job_id,metadata FROM replicate_partials ORDER BY job_id')}
        registrations, claims = {}, {}
        for row in all_rows:
            if row.get('attempt', 1) >= 4:
                original, pin = carrier._registration_locked(row)
                public = read_public(domain.home/(row['id']+'_REGISTRATION_PUBLIC.json'),
                    root=domain.home, expected=pin)
                need(public == original, 'PAID_FINAL_CAPTURE_ORIGINAL_REGISTERED_PUBLIC_EQUALS_DB')
                registrations[row['id']] = dict(metadata=copy.deepcopy(original), sha256=pin)
                if row['claim'] is not None:
                    claim = reader.authorization(row['point'],row['replicate'],row['attempt'],
                        trajectory=row['trajectory'],input_policy=row['input_policy'])
                    need(claim['claim'] == row['claim'], 'PAID_FINAL_CAPTURE_SAME_ORIGINAL_RAW4_CLAIM')
                    claims[row['id']] = claim
        need(db.execute('SELECT COUNT(*) FROM '+AUTH).fetchone()[0] == len(registrations),
             'PAID_FINAL_CAPTURE_EVERY_ORIGINAL_RAW4_AUTHORIZATION_BOUND')
        # Child/terminal JSON is framework control, not candidate/result data.
        custody = {r['id']: dict(child=None if r['child'] is None else json.loads(r['child']),
            terminal=None if r['terminal'] is None else json.loads(r['terminal'])) for r in all_rows}
        points = [dict(r) for r in db.execute(
            'SELECT point,trajectory,setting,target,input_root,input_policy FROM points ORDER BY point')]
        need(all(r['state'] not in ('CLAIMED','RUNNING','CUSTODY_UNKNOWN') for r in all_rows),
             'PAID_FINAL_CAPTURE_WAIT_ORIGINAL_ACTIVE_QUEUE_CUSTODY')
        for row in all_rows:
            if row['state'] == 'CHILD_EXITED_HOLD':
                proof = partials.get(row['id'])
                need(proof is not None and proof['disposition'] == 'PARTIAL'
                     and proof['model_unresolved'] == proof['evaluator_unresolved'] == 0
                     and proof['terminal_sha256'] == digest(custody[row['id']]['terminal']),
                     'PAID_FINAL_CAPTURE_WAIT_UNDISPOSED_EXITED_HOLD')
        read_budget.check(); free()
    return dict(descriptor_path=str(domain.descriptor), descriptor_sha256=domain.pin,
        descriptor=descriptor, original_approved_install_receipt=installed,
        original_authorization_owner=copy.deepcopy(domain.owner),
        original_raw4_registrations=registrations, original_raw4_claims=claims, all_jobs=[job_controls(r) for r in all_rows],
        effective_jobs=[job_controls(r) for r in effective], original_partial_controls=partials,
        original_child_terminal_controls=custody, original_point_descriptors=points,
        offline_OWN=domain.offline_OWN, methods_are_original_RO_metadata_views=True)


def configuration_controls(config):
    need(type(config) is dict, 'PAID_FINAL_CAPTURE_ORIGINAL_EXISTING_CONFIG_REQUIRED')
    result = {k: copy.deepcopy(config[k]) for k in CONFIG_FIELDS if k in config}
    need(all(type(v) in (str,int) for v in result.values()),
         'PAID_FINAL_CAPTURE_CONFIG_FIXED_SCALAR_CONTROL_FIELDS')
    for name in ('manifest','model_policy','profile','image_freeze'):
        need(type(config.get(name)) is dict, 'PAID_FINAL_CAPTURE_CONFIG_FIXED_POLICY_PIN_METADATA')
        result[name+'_metadata_sha256'] = digest(config[name])
    services = config.get('services')
    need(type(services) is dict, 'PAID_FINAL_CAPTURE_ORIGINAL_SERVICE_CONTROL_FIELDS')
    result['services'] = {k: copy.deepcopy(services[k]) for k in
        ('schema','purpose','framework_root','docker_host','docker_config','dependency_freeze_sha256') if k in services}
    need(all(type(v) is str for v in result['services'].values()),
         'PAID_FINAL_CAPTURE_SERVICE_CONTROLS_ARE_STRINGS')
    return result


def dispatcher_controls(dispatcher, queue_view, *, read_budget):
    from native_final_dispatch import NativeFinalDispatcher
    need(type(dispatcher) is NativeFinalDispatcher, 'PAID_FINAL_CAPTURE_EXACT_ORIGINAL_DISPATCHER')
    unlocked(dispatcher.ledger, dispatcher.queue)
    with ram_lock(dispatcher.lock, read_budget):
        children = []
        for key, record in sorted(dispatcher.children.items()):
            read_budget.check()
            child, terminal = record['child'], record['terminal']
            need(type(child) is subprocess.Popen and type(child.returncode) is int
                 and type(terminal) is dict and terminal.get('wait_observed') is True,
                 'PAID_FINAL_CAPTURE_WAIT_REAL_ORIGINAL_POPEN_GENUINE_WAIT')
            need(set(terminal) == {'identity','exit_code','signal','wait_observed'}
                 and type(terminal['identity']) is dict
                 and set(terminal['identity']) == {'pid','start','boot_id','ppid'}
                 and terminal['identity']['pid'] == child.pid
                 and terminal['exit_code'] == (child.returncode if child.returncode >= 0 else None)
                 and terminal['signal'] == (-child.returncode if child.returncode < 0 else None)
                 and queue_view['original_child_terminal_controls'][key] ==
                     dict(child=terminal['identity'], terminal=terminal),
                 'PAID_FINAL_CAPTURE_SAME_ORIGINAL_QUEUE_AND_POPEN_WAIT')
            children.append(dict(job=job_controls(record['job']), pid=child.pid,
                returncode=child.returncode, terminal=copy.deepcopy(terminal),
                config_control=configuration_controls(record['config']),
                original_config_path=str(record['path']), scope=record.get('scope'),
                partial=record.get('partial', False), replacement_job_id=record.get('replacement_job_id'),
                approved_carrier_successor=record.get('approved_carrier_successor')))
        points = {}
        for point, row in sorted(dispatcher.points.items()):
            need(set(row) == {'aux','jobs','audited'} and type(row['audited']) is bool,
                 'PAID_FINAL_CAPTURE_FIXED_ORIGINAL_DISPATCHER_POINT_FIELDS')
            points[point] = dict(aux=str(row['aux']), jobs=list(row['jobs']), audited=row['audited'])
        faulted = dispatcher.faulted
    read_budget.check(); unlocked(dispatcher.ledger, dispatcher.queue)
    by_id = {r['job']['id'] for r in children}
    need(all(r['id'] in by_id for r in queue_view['all_jobs'] if r['state'] != 'QUEUED'),
         'PAID_FINAL_CAPTURE_NO_MISSING_HISTORICAL_GENUINE_CHILD_HANDLES')
    return dict(original_children=children, original_points=points, faulted=faulted,
        root=str(dispatcher.root), entry=str(dispatcher.entry), entry_pin=copy.deepcopy(dispatcher.entry_pin),
        command=list(dispatcher.command), config_capability_or_config_file_body_read=False)


def capture_registered(owner, *, read_budget):
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from normal_cold_barrier import NormalCheckpointBarrier
    from normal_cold_sealer import NormalColdCandidateSealer
    from formal_controller import FormalFinalController
    from queue_control import CarrierQueueDomain
    from allowance_control import FormalAllowanceControl
    from final_queue import process_identity
    need(type(read_budget) is ReadBudget and type(owner) is NativeColdOwner
         and type(owner.core) is OriginalRelayCore and not owner.core.qualification_only,
         'PAID_FINAL_CAPTURE_REGISTERED_PRODUCTION_OWNER_ONLY')
    core = owner.core; barrier = owner.normal_cold_barrier; source = owner.normal_cold_sealer
    unlocked(core.ledger, core.queue); read_budget.check(); verify_sources()
    need(type(barrier) is NormalCheckpointBarrier and type(source) is NormalColdCandidateSealer
         and source.owner is owner and source.barrier is barrier,
         'PAID_FINAL_CAPTURE_ORIGINAL_REGISTERED_SOURCE_BARRIER')
    source._current(); view = observed_six_cut_witness(owner)
    need(view['requested'] and view['observed_six_original_frozen_cut_stability'] is True
         and len(view['tracks']) == 6, 'PAID_FINAL_CAPTURE_WAIT_TRUE_SIX_ORIGINAL_FROZEN_CUTS')
    final = barrier.cohort.final; domain = barrier.approved; control = domain.control
    need(type(final) is FormalFinalController and final is barrier.final_record[0]
         and final.dispatcher is barrier.final_record[2] and type(domain) is CarrierQueueDomain
         and not domain.offline_OWN and type(control) is FormalAllowanceControl
         and control.owner is owner and domain.q is core.queue and domain.l is core.ledger
         and domain.owner == control.birth == process_identity(os.getpid()),
         'PAID_FINAL_CAPTURE_CURRENT_ORIGINAL_FINAL_CARRIER_ALLOWANCE_PROVENANCE')
    control.fresh()
    with readonly(core.ledger.home/'ledger.sqlite', read_budget, lambda: unlocked(core.ledger, core.queue)) as db:
        need(db.execute("SELECT COUNT(*) FROM aux_permits WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0] == 0,
             'PAID_FINAL_CAPTURE_WAIT_NO_ACTIVE_OR_UNKNOWN_AUX_CUSTODY')
    queue = queue_control_view(domain, read_budget=read_budget)
    dispatch = dispatcher_controls(final.dispatcher, queue, read_budget=read_budget)
    from allowance_control import read_public
    allowance = dict(descriptor_path=str(control.path), descriptor_sha256=control.reader.pin,
        descriptor=read_public(control.path, root=control.home, expected=control.reader.pin),
        original_owner=copy.deepcopy(control.birth), approved_repair_sources=copy.deepcopy(control.approved),
        attempt_authorizations={})
    for row in queue['all_jobs']:
        if row['attempt'] <= 3 and row['claim'] is not None:
            allowance['attempt_authorizations'][row['id']] = control.reader.authorization(
                row['point'],row['replicate'],row['attempt'],trajectory=row['trajectory'],input_policy=row['input_policy'])
    source._current(); domain.fresh(); control.fresh(); read_budget.check()
    return dict(schema=SCHEMA, original_owner_birth=asdict(source.birth),
        original_control_owner=copy.deepcopy(domain.owner), original_owner_epoch=getattr(source.domain,'_paid_writer_epoch',1),
        contract_sha256=source.source_binding, source_pins=verify_sources(),
        original_queue=queue, original_dispatcher=dispatch, original_allowance=allowance,
        observed_registered_six_frozen_cuts=True, captured_original_authorizations_not_retagged=True,
        is_transactional_whole_owner_seal=False, owner_lineage_consume_implemented=False,
        runtime_constructed_or_queue_adopted=False, whole_cold_ready=False, safe_to_TERM=False,
        state='CAPTURED_CONTROL_CANDIDATE_WAIT_TRUSTED_WHOLE_SEAL_AND_TYPED_OWNER_LINEAGE')
