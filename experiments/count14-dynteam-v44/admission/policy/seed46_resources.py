"""PUBLIC admission proof guard; no Docker/configuration/model operations."""
from pathlib import PurePosixPath
import time
from seed46_manifest import need, ROOT

EVAL_HOST = 'unix:///mnt/ptb-scratch2/count14-eval-docker-20261030/docker.sock'
SEARCH_HOST = 'unix:///mnt/ptb-scratch/cg-count14-search-block456-20261031/docker/docker.sock'
SEARCH_DATA_ROOT = '/mnt/ptb-scratch/cg-count14-search-block456-20261031/docker/data'
GiB = 2**30


def scratch_path(value):
    need(type(value) is str, 'SEED46_SCRATCH_PATH_TYPE')
    p = PurePosixPath(value)
    need(p.is_absolute() and str(p) == value and '..' not in p.parts and
         p.is_relative_to(PurePosixPath('/mnt/ptb-scratch2')) and
         p != PurePosixPath('/mnt/ptb-scratch2'), 'SEED46_NO_ROOT_DISK_DEPLOYMENT_PATH')
    return p


def search_path(value):
    need(type(value) is str, 'SEED46_SEARCH_PATH_TYPE')
    p = PurePosixPath(value)
    base = PurePosixPath('/mnt/ptb-scratch/cg-count14-search-block456-20261031/docker')
    need(p.is_absolute() and str(p) == value and '..' not in p.parts and
         p.is_relative_to(base) and p != base, 'SEED46_ONLY_NEW_FIXED_SCRATCH1_SEARCH_PATH')
    return p


def validate(value, *, now_ns=None, for_system_health=False):
    need(value.get('schema') == 'count14-seed46-global-resource-admission-v1',
         'SEED46_RESOURCE_SCHEMA')
    now_ns = time.time_ns() if now_ns is None else now_ns
    need(type(value.get('observed_ns')) is int and 0 <= now_ns-value['observed_ns'] <= 60*10**9,
         'SEED46_FRESH_RESOURCE_PROOF_60_SECONDS')
    need(type(value.get('MemAvailable_bytes')) is int and
         value['MemAvailable_bytes']-16*GiB >= 64*GiB, 'SEED46_MEMORY_KEEP_SMOKE16_PLUS64')
    q = value['allocations']
    need(set(q) == {'Agensh-1-8-b456', 'scale16-agg-b456'} and
         all(type(q[k]) is int and q[k] > 0 for k in q), 'SEED46_TWO_REAL_OWNER_ALLOCATIONS')
    old = value['retained_other_physical_slots_including_UNKNOWN']
    need(type(old) is int and old >= 0 and old+sum(q.values()) <= 96,
         'SEED46_GLOBAL96_INCLUDES_RETAINED_OLD_UNKNOWN')
    need(value.get('retained_UNKNOWN_slots_released') == 0 and
         value.get('old_ledgers_rewritten') is False and
         value.get('global_physical_counts_fresh') is True, 'SEED46_NO_HEADROOM_BY_FORGIVING_UNKNOWN')
    # Gateway global load belongs to other projects too: reference ONLY.
    # The same original numeric refresher supplies fresh own-relay metadata.
    own = value.get('own_FP8_relays')
    need(type(own) is dict and own.get('schema') == 'count14-own-fp8-relay-counts-v1',
         'SEED46_OWN_RELAY_COUNTERS_REQUIRED')
    need(own.get('all_count14_roots_included') is True and
         own.get('counts_from_relay_ledgers') is True and
         type(own.get('observed_ns')) is int and
         0 <= now_ns-own['observed_ns'] <= 60*10**9,
         'SEED46_FRESH_ALL_OWN_RELAY_LEDGER_COUNTS')
    rows = own.get('roots')
    need(type(rows) is list and rows and
         all(type(r) is dict and type(r.get('root')) is str and
             type(r.get('FP8_inflight')) is int and r['FP8_inflight'] >= 0
             for r in rows), 'SEED46_OWN_RELAY_NUMERIC_ROOT_ROWS')
    need(len({r['root'] for r in rows}) == len(rows) and
         all(PurePosixPath(r['root']).is_absolute() and str(PurePosixPath(r['root'])) == r['root'] and '..' not in PurePosixPath(r['root']).parts and any(PurePosixPath(r['root']).is_relative_to(base) and PurePosixPath(r['root']) != base for base in (PurePosixPath('/mnt/ptb-scratch'),PurePosixPath('/mnt/ptb-scratch2'))) for r in rows),
         'SEED46_OWN_ROOTS_UNIQUE_SCRATCH_ONLY')
    total = sum(r['FP8_inflight'] for r in rows)
    need(type(own.get('total_FP8_inflight')) is int and
         own['total_FP8_inflight'] == total and total <= 96,
         'SEED46_ALL_OWN_FP8_RELAY_INFLIGHT_AT_MOST96')
    if not for_system_health:
        health = value.get('own_admission_health')
        need(type(health) is dict and health.get('schema') == 'count14-own-resource-health-v1' and
             type(health.get('observed_ns')) is int and
             0 <= now_ns-health['observed_ns'] <= 60*10**9,
             'SEED46_FRESH_ADMISSION_HEALTH')
        p95 = health.get('gateway_FP8_TTFT_p95_seconds')
        need(type(p95) in (int,float) and 0 <= p95 <= 60,
             'SEED46_GATEWAY_TTFT_P95_AT_MOST60_SECONDS')
        need(health.get('own_window_seconds') == 600 and
             type(health.get('own_requests')) is int and health['own_requests'] >= 0 and
             type(health.get('own_5xx_or_UNKNOWN_requests')) is int and
             0 <= health['own_5xx_or_UNKNOWN_requests'] <= health['own_requests'],
             'SEED46_OWN_10MIN_REQUEST_HEALTH_COUNTS')
        covered = health.get('own_window_covered_seconds')
        need(type(covered) in (int,float) and 0 <= covered <= 600,
             'SEED46_OWN_WINDOW_OBSERVED_COVERAGE')
        defined = covered == 600 and health['own_requests'] > 0
        need(type(health.get('own_rate_defined')) is bool and
             health['own_rate_defined'] is defined,
             'SEED46_RATE_UNDEFINED_DURING_WARMUP_OR_ZERO_DENOMINATOR')
        if defined:
            need(health['own_5xx_or_UNKNOWN_requests']*100 <= health['own_requests']*20,
                 'SEED46_OWN_10MIN_5XX_UNKNOWN_AT_MOST20_PERCENT')
    need(value.get('new_root') == ROOT, 'SEED46_RESOURCE_EXACT_NEW_ROOT')
    d = value['docker_routes']
    need(set(d) == {'SEARCH_BACKEND', 'FINAL_AUX_DIRECT'}, 'SEED46_EXPLICIT_TWO_DOCKER_ROUTES')
    for name, row in d.items():
        host = row['docker_host']
        need(type(host) is str and host.startswith('unix:///'), 'SEED46_PRIVATE_DOCKER_UNIX_ONLY')
        if name == 'SEARCH_BACKEND':
            need(host == SEARCH_HOST and row['data_root'] == SEARCH_DATA_ROOT,
                 'SEED46_EXACT_SCRATCH1_SEARCH_DAEMON')
            search_path(host[7:]); search_path(row['data_root'])
        else:
            scratch_path(host[7:]); scratch_path(row['data_root'])
        need(row['data_root_on_scratch_mount'] is True and row['healthy'] is True and
             row['uses_system_containerd'] is False and row['system_fallback'] is False,
             'SEED46_REAL_CONTAINER_WRITABLE_LAYERS_NOT_ROOT_DISK')
        need(type(row['mount_uuid']) is str and bool(row['mount_uuid']) and
             row['mount_device'] != row['rootfs_device'], 'SEED46_REAL_MOUNT_IDENTITY')
        need(row['immutable_image_identity_verified'] is True,
             'SEED46_ORIGINAL_IMAGE_IDS_DIGESTS_NOT_REBUILT')
    need(d['FINAL_AUX_DIRECT']['docker_host'] == EVAL_HOST and
         d['FINAL_AUX_DIRECT']['existing_daemon_content_overwritten'] is False,
         'SEED46_EXISTING_COUNT14_EVAL_DAEMON_PROTECTED')
    storage = value['storage']
    need(set(storage) == {'scratch1_SEARCH_layers', 'scratch2_roots_snapshots'},
         'SEED46_TWO_MOUNTS_ACCOUNTED_SEPARATELY')
    for disk in storage.values():
        need(all(type(disk[k]) is int and disk[k] >= 0 for k in
                 ('available_bytes', 'existing_reserved_bytes', 'new_batch_estimate_bytes', 'minimum_reserve_bytes')),
             'SEED46_NUMERIC_FRESH_STORAGE_NO_ASSUMED_DELETE_CREDIT')
        need(disk['minimum_reserve_bytes']>=200*GiB,'SEED46_EACH_SCRATCH_MOUNT_MINIMUM200_GIB')
        need(disk['available_bytes']-disk['existing_reserved_bytes']-disk['new_batch_estimate_bytes'] >=
             disk['minimum_reserve_bytes'] and disk.get('future_cleanup_credit_bytes') == 0,
             'SEED46_EACH_MOUNT_BATCH_FITS_ITS_ACTUAL_FREE_SPACE')
    return value


def new_agensh_quota(value, *, now_ns=None):
    validate(value, now_ns=now_ns)
    cap = value['allocations']['Agensh-1-8-b456']
    need(cap >= 4, 'SEED46_SEARCH_AND_AUX_BOTH_POSITIVE')
    aux = min(6, max(1, cap//8))
    return dict(global_cap=cap, search_cap=cap-aux, auxiliary_cap=aux, final_cap=min(3, aux))
