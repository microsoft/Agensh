#!/usr/bin/env python3
"""Collect ALL no-model dry-start failures; no services, releases or RPCs.

Host checks are OPS assertions linked to original sanitized evidence, not facts
inferred by this collector. A PASS means only the declared pre-CLI dry startup;
it is never real gate4 PASS or a scientific launch authorization.
"""
from pathlib import Path
import argparse
import json
import re
from native_dry_start_probe import Checks, SCHEMA, PLAN_SCHEMA, validate_plan, canonical, sha, strict, require, PUBLIC8, EXECUTABLES, READONLY, WRITABLE, PRIVATE_FILES, SOCKETS, ENTRY

HOST_CHECKS = (
    'fresh_independent_root_no_stale_release',
    'all_native_containers_exact_images_state_bounds',
    'all_public_host_dependencies_read_execute_sha_umask',
    'owned_bwrap_original_flags_physical_exec',
    'native_gitea_mm_nonadmin_team2_private_channel_visibility',
    'actual_original_sdk_prime_all_roles',
    'delivery_same_inode_role_only_readonly_no_backend_credentials',
    'all_eight_host_uds_addresses_direct_or_private_dirfd_under107bytes',
    'actual_worker_uid_pid_start_mount_pidns_netns',
    'loopback_git_front_exact_pid_start_listener',
    'namespace_fence_relay_only_no_generic_proxy_no_egress',
    'role_credentials_injected_without_backend_authority',
    'original_router_config_dependencies_precli_no_connections',
    'relay_health_no_model_dispatch_no_business_rpc',
    'fresh_memory64gib_pty_disk_inflight96_final12',
)

def expected_worker_checks(plan):
    checks = {'plan.valid', 'identity.actual_uid_gid', 'identity.actual_umask', 'identity.no_extra_groups',
              'environment.ACP_CHILD_UID', 'environment.ACP_CHILD_GID', 'environment.native_onlyrelay',
              'release.before', 'release.after', 'runtime.acp_unix_bind', 'runtime.sqlite_exclusive_lock',
              'runtime.agent_node_read_execute', 'syntax:worker_hold.sh', 'syntax:original_entrypoint',
              'runtime.native_node_loader_dependencies', 'network.relay_health_get_only'}
    checks |= {'mount.readonly:' + n for n in READONLY}
    checks |= {'mount.write_uid_fsync:' + n for n in WRITABLE}
    checks |= {'public.read_sha:' + n for n in plan['public_pins']}
    checks |= {'runtime.read_execute:' + n for n in EXECUTABLES}
    checks |= {'syntax.python:' + n for n in ('/opt/omcgitea/acp-bridge.py', '/opt/omcgitea/archive.py') + tuple('/opt/count14/' + n for n in PUBLIC8 if n.endswith('.py'))}
    if plan['phase'] == 'ports':
        checks |= {'export.uid_read:' + n for n in PRIVATE_FILES}
        checks |= {'export.socket_stat_access:' + n for n in SOCKETS}
        checks |= {'export.original_mcp_guards', 'network.loopback_git_nonbusiness_403', 'runtime.original_entrypoint_precli'}
    return checks

def verify_worker(plan, report):
    validate_plan(plan)
    require(report['schema'] == SCHEMA and report['status'] == 'WORKER_CHECKS_PASS_NOT_HOST_OR_GATE4_PASS', 'WORKER_REPORT_NOT_PASS')
    require(report['actor'] == plan['actor'] and report['phase'] == plan['phase']
            and report['plan_sha256'] == sha(canonical(plan)), 'WORKER_PLAN_REPORT_BINDING')
    require(report['uid'] == report['gid'] == 10000 and type(report['pid']) is int and report['pid'] > 0, 'WORKER_REPORT_UID_PID')
    require(report['model_requests'] == report['tool_business_rpc'] == 0
            and report['started_cli_or_acp'] is report['published_release'] is False, 'WORKER_NO_MODEL_NO_RELEASE')
    require(report['failed_checks'] == [] and type(report['checks']) is list, 'WORKER_FAILURE_LIST')
    names = [row['check'] for row in report['checks']]
    require(len(names) == len(set(names)) and set(names) == expected_worker_checks(plan)
            and all(row['ok'] is True for row in report['checks']), 'WORKER_REQUIRED_CHECK_COVERAGE')

def collect(host, workers):
    c = Checks()
    c.check('host.schema', lambda: require(host.get('schema') == 'agensh-native-no-model-host-preflight-v1', 'HOST_SCHEMA'))
    c.check('host.run_id', lambda: require(type(host.get('run_id')) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}', host['run_id']), 'HOST_RUN_ID'))
    c.check('host.no_model_release', lambda: require(host.get('model_requests_before') == host.get('model_requests_after') == 0
                        and host.get('business_rpc') == 0 and host.get('allow_cli_published') is False, 'HOST_NO_MODEL_NO_RELEASE'))
    rows = host.get('checks', {})
    for name in HOST_CHECKS:
        def check_host(name=name):
            row = rows[name]
            require(row['ok'] is True and type(row['evidence']) is list and bool(row['evidence']), 'HOST_CHECK_NOT_PROVEN')
            for pin in row['evidence']:
                # Evidence is previously sanitized by OPS; do not open private logs.
                require(type(pin) is dict and type(pin.get('bytes')) is int and pin['bytes'] > 0
                        and type(pin.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256'])
                        and type(pin.get('path')) is str and bool(pin['path']), 'HOST_ORIGINAL_EVIDENCE_PIN_REQUIRED')
        c.check('host.' + name, check_host)
    c.check('workers.exact_team2', lambda: require(type(workers) is list and len(workers) == 2
                    and len({w['held_plan']['actor'] for w in workers}) == 2, 'EXACT_TWO_NATIVE_WORKERS'))
    seen = []
    if type(workers) is list:
        for i, item in enumerate(workers):
            for phase in ('held', 'ports'):
                def check_worker(item=item, phase=phase):
                    plan = item[phase + '_plan']
                    require(plan['phase'] == phase, 'EXACT_PROBE_PHASE')
                    verify_worker(plan, item[phase + '_report'])
                c.check('worker.' + str(i) + '.' + phase, check_worker)
            c.check('worker.' + str(i) + '.same_actor_pins', lambda item=item: require(
                {k:v for k,v in item['held_plan'].items() if k != 'phase'} ==
                {k:v for k,v in item['ports_plan'].items() if k != 'phase'}, 'WORKER_PHASE_SAME_FROZEN_PLAN'))
    result = c.result('native-team2', 'collected-precli', sha(canonical({'host': host, 'workers': workers})))
    result['schema'] = 'agensh-native-team2-no-model-dry-start-summary-v1'
    result['status'] = 'PRECLI_DRY_START_PASS_NOT_REAL_GATE4_PASS' if not result['failed_checks'] else 'FAIL'
    result['host_assertions_require_ops_original_evidence'] = True
    result['real_gate4_attempts_consumed_by_collector'] = 0
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='OPS-created metadata-only JSON: host and workers')
    a = parser.parse_args()
    try:
        raw = Path(a.input).read_bytes()
        require(len(raw) <= 2 * 1024 * 1024, 'COLLECTION_INPUT_BOUND')
        value = strict(raw)
        result = collect(value['host'], value['workers'])
    except Exception:
        result = {'schema': 'agensh-native-team2-no-model-dry-start-summary-v1', 'status': 'FAIL',
                  'failed_checks': ['collection.input'], 'model_requests': 0, 'published_release': False}
    print(canonical(result).decode())
    return 0 if result['status'] == 'PRECLI_DRY_START_PASS_NOT_REAL_GATE4_PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
