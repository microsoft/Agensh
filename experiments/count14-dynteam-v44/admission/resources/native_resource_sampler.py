"""Finite read-only sampler used by the SAME-owner resource supervisor.

No model/key/task/tool/evaluation action. A plan is frozen PUBLIC deployment
metadata, not a green proof. Only actual source projections may create the
receipt. Explicit OWN virtualization is refused by every production caller.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
from dataclasses import asdict
import json
import os
import signal
import time

from common import need,digest
from native_peer_registry import ProcessBirth,process_birth
from native_docker_scope import DockerRoute,ScopedDocker
from native_cohort_resources import SEARCH_HOST,SEARCH_DATA_ROOT,EVAL_HOST,GIB,PREACTIVATE_STORAGE,RUNTIME_STORAGE
from native_resource_projections import (frozen_observer,native_projection,system_projection,
    registered_outside_projection,merge_cohort_counts,kernel_projection,docker_projection)


def birth(value):
    need(type(value) is dict and set(value)==set(ProcessBirth.__dataclass_fields__),
         'DYNTEAM_SAMPLE_EXACT_PROCESS_BIRTH_FIELDS')
    return ProcessBirth(**value)


def read_public(path,limit=131072):
    O,_=frozen_observer();raw,s=O.read(path,limit)
    need(s.st_uid in (0,os.geteuid()) and not s.st_mode&0o022 and s.st_nlink==1,
         'DYNTEAM_SAMPLE_PUBLIC_SOURCE_OWNER_MODE')
    return json.loads(raw),raw


def allocation_envelope(job):
    owner=job['owner']
    return dict(schema='count14-dynteam-cohort-resource-binding-v1',contract_sha256=job['contract_sha256'],
        owner_pid=owner['pid'],owner_start_ticks=owner['start_ticks'],owner_boot_id=owner['boot_id'],
        inventory_sha256=job['inventory_sha256'],other_maximum_FP8_inflight=job['other_maximum_FP8_inflight'],
        SYSTEM_reserved_slots=2,no_active_unregistered_roots=True,
        other_bound_is_full_allocations_plus_retained_UNKNOWN=True)


def validate_promise_directories(directories):
    need(type(directories)is list,'DYNTEAM_SAMPLE_REGISTERED_STORAGE_PROMISE_ROOTS')
    retired={'ct14-dynteam-formal-msg232-20261109-v1'}|{
        'ct14-dynteam-formal-msg237-20261110-v'+str(n)for n in range(2,26)}
    for value in directories:
        need(type(value)is str and not retired.intersection(Path(value).parts),
             'DYNTEAM_N26_NO_RETIRED_FORMAL_PROMISE_DIRECTORIES')


def promises(directories,*,mount_device):
    validate_promise_directories(directories)
    from orphan_storage_retirement_reader import FrozenRetirements,effective_promises,EXACT29_MANIFEST,MANIFEST_PIN
    O,_=frozen_observer()
    return effective_promises(directories,mount_device=mount_device,observer=O,
                              frozen=FrozenRetirements(EXACT29_MANIFEST,MANIFEST_PIN))


def outside_with_deadline(plan,job,cache):
    # Original census owns a fixed25s SIGALRM. Preserve its body/limit and
    # restore the outer finite sampler's remaining deadline afterwards.
    previous=signal.getitimer(signal.ITIMER_REAL)
    need(previous[0]>=25,'DYNTEAM_SAMPLE_REMAINING_DEADLINE_BEFORE_ORIGINAL_CENSUS')
    signal.setitimer(signal.ITIMER_REAL,0);start=time.monotonic()
    try:
        v=plan['outside_registry']
        return registered_outside_projection(v['path'],v['sha256'],cache,
            contract_sha256=job['contract_sha256'],forbidden_native_ledgers=[job['ledger_path']],
            qualification_only=job['qualification_only'],
            OWN_metrics_url=None if plan['OWN_fixture'] is None else plan['OWN_fixture']['metrics_url'],
            allow_missing_health=True)
    finally:signal.setitimer(signal.ITIMER_REAL,max(.001,previous[0]-(time.monotonic()-start)))


def sample(job,plan):
    owner=birth(job['owner']);home=Path(job['core_home']);q=job['qualification_only']
    need(job.get('storage_lifecycle_phase')in(PREACTIVATE_STORAGE,RUNTIME_STORAGE),
         'DYNTEAM_SAMPLE_OWNER_INTENT_REAL_STORAGE_PHASE')
    need(type(q) is bool and process_birth(owner.pid)==owner and os.getppid()==owner.pid and
         home.resolve()==home and job['ledger_path']==str(home/'ledger/ledger.sqlite') and
         plan['schema']=='count14-dynteam-resource-production-plan-v1' and
         plan['contract_sha256']==job['contract_sha256'] and
         plan['other_maximum_FP8_inflight']==job['other_maximum_FP8_inflight'] and
         plan['no_active_unregistered_roots'] is True and
         plan['other_bound_is_full_allocations_plus_retained_UNKNOWN'] is True,
         'DYNTEAM_SAMPLE_EXACT_OWNER_AND_FROZEN_ALLOCATION_PLAN')
    if q:
        need(any(v.startswith('OWN-') for v in home.parts),'DYNTEAM_SAMPLE_OWN_HOME_ONLY')
    else:
        need(os.geteuid()==0 and os.uname().nodename==(_C14_HOSTNAME) and home.is_relative_to((_C14_SCRATCH)) and
             plan['OWN_fixture'] is None,'DYNTEAM_SAMPLE_PRODUCTION_NEVER_OWN_HOST_PROJECTION')
    outside,health=outside_with_deadline(plan,job,home/'resources/reader-cache')
    O,_=frozen_observer()
    from native_v2_dispositions import PHYSICAL_TERMINAL
    native=native_projection(Path(job['ledger_path']),job['trajectory_roots'],physical_clause=PHYSICAL_TERMINAL)
    system=system_projection(home/'system-health',contract_sha256=job['contract_sha256'],
                             registered=job['system_registered'],observer=O)
    # Raw counts remain usable for SYSTEM even if TTFT/health was unavailable.
    # No fake denominator, p95, healthy flag or current health timestamp is made.
    if health is None:
        rows=[*outside['roots'],*native['roots'],dict(root=system['root'],FP8_inflight=system['FP8_inflight'])]
        need(len({r['root'] for r in rows})==len(rows) and
             not any(Path(a['root']).is_relative_to(b['root']) or Path(b['root']).is_relative_to(a['root'])
                     for a in outside['roots'] for b in rows[len(outside['roots']):]),
             'DYNTEAM_SAMPLE_NO_OUTSIDE_OWN_DOUBLE_COUNT')
        own=dict(schema='count14-own-fp8-relay-counts-v1',observed_ns=min(outside['observed_ns'],native['observed_ns'],system['observed_ns']),
            all_count14_roots_included=True,counts_from_relay_ledgers=True,roots=rows,
            total_FP8_inflight=sum(r['FP8_inflight'] for r in rows),publish_observation_only_not_admission=True)
    else:
        own,health=merge_cohort_counts(outside,health,native,system,contract_sha256=job['contract_sha256'],
                                      outside_maximum=job['other_maximum_FP8_inflight'])
    raw_kernel=kernel_projection({k:v['mount'] for k,v in plan['storage'].items()})
    routes={};storage={};virtual=plan['OWN_fixture'] is not None
    for name,value in plan['docker_routes'].items():
        route=dict(value['route']);route['cli']=Path(route['cli']);route['socket_path']=Path(route['socket_path']);route['data_root']=Path(route['data_root'])
        need(route['qualification_only'] is q,'DYNTEAM_SAMPLE_NO_MIXED_DAEMON_QUALIFICATION')
        docker=ScopedDocker(DockerRoute(**route))
        r=docker_projection(docker,dockerd_birth=birth(value['dockerd_birth']),
            containerd_socket=Path(value['containerd_socket']),containerd_birth=birth(value['containerd_birth']),images=value['images'])
        label='scratch1_SEARCH_layers' if name=='SEARCH_BACKEND' else 'scratch2_roots_snapshots'
        fs=raw_kernel['storage'][label]
        if not virtual:
            need(fs['is_mount'] and fs['mount_uuid'] is not None and fs['device']!=fs['rootfs_device'] and
                 Path(r['data_root']).stat().st_dev==fs['device'],
                 'DYNTEAM_SAMPLE_REAL_DOCKER_DATA_ON_CORRECT_SCRATCH_MOUNT')
            need(r['docker_host']==(SEARCH_HOST if name=='SEARCH_BACKEND' else EVAL_HOST) and
                 (name!='SEARCH_BACKEND' or r['data_root']==SEARCH_DATA_ROOT) and
                 (name!='FINAL_AUX_DIRECT' or len(value['images'])==28),
                 'DYNTEAM_SAMPLE_EXACT_SEARCH_EVAL_ROUTES_AND_EVAL28_PINS')
        r.update(mount_uuid=fs['mount_uuid'],mount_device=fs['device'],rootfs_device=fs['rootfs_device'],
                 data_root_on_scratch_mount=fs['is_mount'] and fs['device']!=fs['rootfs_device'])
        routes[name]=r
    need(set(routes)=={'SEARCH_BACKEND','FINAL_AUX_DIRECT'},'DYNTEAM_SAMPLE_BOTH_DAEMONS_REQUIRED')
    for label,value in plan['storage'].items():
        fs=raw_kernel['storage'][label]
        need(value['all_current_promise_roots_included'] is True and
             all(type(value[k]) is int and value[k]>=0 for k in ('new_batch_estimate_bytes','minimum_reserve_bytes')) and
             value['minimum_reserve_bytes']>=200*GIB,'DYNTEAM_SAMPLE_NO_DISK_PROMISE_OR_ESTIMATE_DEFAULTS')
        promise=promises(value['promise_directories'],mount_device=fs['device'])
        storage[label]=dict(available_bytes=fs['available_bytes'],existing_reserved_bytes=promise['effective_promised_bytes'],
            orphan_storage_retirements=promise,new_batch_estimate_bytes=value['new_batch_estimate_bytes'],
            minimum_reserve_bytes=value['minimum_reserve_bytes'],future_cleanup_credit_bytes=0)
    memory=raw_kernel['MemAvailable_bytes']
    if virtual:
        need(q,'DYNTEAM_SAMPLE_NEVER_VIRTUALIZE_PRODUCTION_HOST')
        fixture=plan['OWN_fixture'];memory=fixture['MemAvailable_bytes']
        # Explicit OWN host/daemon substitute, retained alongside actual local
        # kernel facts. Original pure consumer predicates remain unmodified.
        for name,r in routes.items():
            r.update(docker_host=SEARCH_HOST if name=='SEARCH_BACKEND' else EVAL_HOST,
                data_root=SEARCH_DATA_ROOT if name=='SEARCH_BACKEND' else (_C14_SCRATCH + '/OWN-eval-data'),
                mount_uuid='OWN-only-not-real-mount',mount_device=2,rootfs_device=1,data_root_on_scratch_mount=True)
        for label,v in storage.items():v['available_bytes']=fixture['available_bytes'][label]
    observed=min(raw_kernel['observed_ns'],own['observed_ns'],native['observed_ns'],system['observed_ns'])
    need(process_birth(owner.pid)==owner,'DYNTEAM_SAMPLE_SAME_OWNER_STILL_LIVE_AFTER_IO')
    return dict(schema='count14-seed46-global-resource-admission-v1',observed_ns=observed,MemAvailable_bytes=memory,
        new_root=job['new_root'],storage_lifecycle_phase=job['storage_lifecycle_phase'],
        docker_routes=routes,storage=storage,own_FP8_relays=own,own_admission_health=health,
        dynteam_allocation=allocation_envelope(job),qualification_only=q,OWN_fixture_host_projection_used=virtual,
        OWN_actual_kernel_facts=raw_kernel if q else None,models=0,
        health_unavailable_exception_type=outside.get('health_unavailable_exception_type'))
