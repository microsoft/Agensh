"""Finite SAME-owner smoke retirement, original shutdown/thaw/Docker controls.

No cancellation, SIGKILL, rm/prune/root removal, fee update, model retry or new
owner. Unproven tools and ordinary still-live children remain WAITING. Every
normal Docker action has one retained Popen, serially polled without timeout.
"""
from __future__ import annotations

import copy
import math
import os
from pathlib import Path
import time

from common import need, digest, private_dir, publish, wire, strict
from original_relay_core import OriginalRelayCore
from native_peer_registry import process_birth
from native_container_retirement import ContainerBinding
from smoke_checkpoint_final_controller import SmokeFinalController


def _acceptance_value(*, search=None, aux_sent=None, snapshots=None, audits=None):
    """Anonymous evidence only; lifecycle completion never implies science PASS."""
    reasons = []
    def positive(value):return type(value) is int and value > 0
    if search is None:reasons.append('SEARCH_REPORTED_USAGE_PROOF_UNKNOWN')
    elif not (positive(search['settled_model_calls']) and positive(search['reported_tokens'])):
        reasons.append('SEARCH_NO_POSITIVE_REPORTED_MODEL_USAGE')
    if aux_sent is None:reasons.append('AUX_SENT_MODEL_CALL_PROOF_UNKNOWN')
    elif not positive(aux_sent):reasons.append('AUX_NO_SENT_MODEL_CALL')
    if snapshots is not True:reasons.append('TWO_ORIGINAL_SNAPSHOT_PROOF_UNKNOWN')
    known = type(audits) is list and len(audits) == 2 and all(type(a) is dict for a in audits)
    complete = known and all(a['complete'] and a['evaluation_complete'] and a['replicates_complete'] == 3 for a in audits)
    reported = sum(a['reported_tokens'] for a in audits) if known else None
    nonempty = any(a['unique_candidates_mean'] > 0 for a in audits) if known else None
    if not complete:reasons.append('TWO_ORIGINAL_K3_PUBLIC_AUDIT_PROOF_UNKNOWN')
    if reported is None:reasons.append('AUX_REPORTED_USAGE_PROOF_UNKNOWN')
    elif not positive(reported):reasons.append('AUX_NO_POSITIVE_REPORTED_MODEL_USAGE')
    if nonempty is None:reasons.append('OFFICIAL_EVALUATION_EXECUTION_PROOF_UNKNOWN')
    elif not nonempty:reasons.append('K3_EMPTY_CANDIDATE_EVALUATION_NOOP')
    return {'schema': 'count14-smoke-scientific-acceptance-public-v1',
        'smoke_acceptance': not reasons, 'reason_codes': reasons,
        'SEARCH_settled_model_calls': None if search is None else search['settled_model_calls'],
        'SEARCH_reported_tokens': None if search is None else search['reported_tokens'],
        'AUX_sent_model_calls': aux_sent, 'AUX_reported_tokens': reported,
        'two_original_snapshot_points_proven': snapshots,
        'two_original_K3_audits_complete': complete if known else None,
        'official_evaluator_invocations': None,
        'official_evaluator_invocations_lower_bound': 1 if complete and nonempty else 0 if known else None,
        'official_execution_lower_bound_basis': 'ORIGINAL_AUDITED_NONEMPTY_VALID_14_TASK_GRAPH' if complete and nonempty else None,
        'exact_official_execution_count_unknown': True, 'private_body_or_matrix_read': False}


class SmokeFinalRetirement:
    def __init__(self, core, *, checkpoint, final, launch):
        from native_dynamic_checkpoint import DynamicCheckpointPorts
        from smoke_bootstrap_task_launch import NativeSameCoreSmokeLaunch
        need(type(core) is OriginalRelayCore and type(checkpoint) is DynamicCheckpointPorts and
             type(final) is SmokeFinalController and type(launch) is NativeSameCoreSmokeLaunch and
             checkpoint.core is final.core is launch.core is core and checkpoint.t == launch.t and
             core.smoke_final_controller is final and core.smoke_checkpoint_ports[checkpoint.t] is checkpoint and
             core.native_spawn_launches[checkpoint.t] is launch and not core.qualification_only and
             not hasattr(core, 'smoke_retirement'), 'SMOKE_RETIREMENT_ONE_REAL_SAME_CORE_GRAPH')
        self.core, self.checkpoint, self.final, self.launch = core, checkpoint, final, launch
        self.t = checkpoint.t; self.owner = process_birth(os.getpid())
        self.state = 'SEARCH_AND_K3_COMPLETE_NOT_RETIRED'; self.failure = None
        self.child = None; self.child_action = None; self.started_ns = None
        self.action_history = []; self.stopped = []; self.index = 0
        self.warning120 = False; self.cached_public = None; self.sequence = 0
        self.acceptance = _acceptance_value()
        core.smoke_retirement = self  # retain before fallible I/O/checks
        self.home = private_dir(core.home/'smoke-retirement', create=True)
        need(not any(self.home.iterdir()), 'SMOKE_RETIREMENT_NEW_RECEIPT_HOME_NO_RETRY')
        self._complete_final_point()
        self.writer = checkpoint.writer
        self.reference = copy.deepcopy(checkpoint.reference)
        self.domain_by_name = dict(zip(sorted(self.writer.containers), self.writer.domains))
        self.items = self._stop_inventory()
        self.role_items = [r for r in self.items if r['component'] != 'infra']
        self.infra_items = [r for r in self.items if r['component'] == 'infra']
        self.acceptance = self._collect_smoke_acceptance()
        self._receipt('BOUND_COMPLETE_K3_NOT_RETIRED', containers=len(self.items))

    def _same_owner(self):
        need(process_birth(os.getpid()) == self.owner and self.core.smoke_retirement is self and
             not self.core.closed, 'SMOKE_RETIREMENT_ORIGINAL_OWNER_RETAINED')
        need(not self.core.ledger.mutex._is_owned(), 'SMOKE_RETIREMENT_NO_IO_UNDER_SCIENCE_LOCK')

    def _complete_final_point(self):
        cp, core = self.checkpoint, self.core
        need(cp.state == 'FINAL_PARKED' and cp.writer is not None and
             cp.writer.writer_fence.state == 'PARKED' and len(cp.points) == 2 and
             [r['target_tokens'] for r in cp.points] == [500000, 1000000] and
             all(len(r['jobs']) == len(set(r['jobs'])) == 3 for r in cp.points),
             'SMOKE_RETIREMENT_ONLY_TWO_ORIGINAL_K3_POINTS_FINAL_PARKED')
        with core.ledger.mutex:
            f = core.ledger.frontier(self.t); account = core.ledger.account(self.t)
            need(f['state'] == 'COMMITTED_PARKED' and f['target'] == 1000000 and
                 account['stage'] == 1 and f['generation'] == cp.points[-1]['generation'] and
                 core.ledger.global_unresolved() == 0 and
                 core.ledger.db.execute("SELECT COUNT(*) FROM aux_permits WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0] == 0,
                 'SMOKE_RETIREMENT_ORIGINAL_PAID_MODEL_PHYSICAL_ZERO')
        need(core.queue.frontier() == {'COMPLETE': 6} and
             len(self.final.dispatcher.points) == 2 and all(p['audited'] for p in self.final.dispatcher.points.values()) and
             all(r['child'] is not None and r['terminal'] is not None and r['child'].returncode is not None
                 for r in self.final.dispatcher.children.values()),
             'SMOKE_RETIREMENT_ORIGINAL_AUDIT_K3_AND_REAL_CHILD_WAIT_REQUIRED')
        need(core.servers[self.t].trajectory_park_ready(self.t)['safe_to_park_writers'],
             'SMOKE_RETIREMENT_ORIGINAL_HTTP_PHYSICAL_DRAIN_REQUIRED')
        snap = core.cas.verify_snapshot(cp.reference, expected=f)
        need(cp.reference == cp.points[-1]['snapshot'] and cp.writer.reference == cp.reference and
             snap['pins']['native_writer_fence'] == cp.writer.writer_fence.receipt['sha256'] and
             cp.writer.cut.cut['generation'] == f['generation'],
             'SMOKE_RETIREMENT_EXACT_SEALED_FINAL_SNAPSHOT_AND_CUT')
        with core.peers._lock:
            need(all(t == self.t for t, _role, _purpose in core.peers._peers),
                 'SMOKE_RETIREMENT_NO_OTHER_TRAJECTORY_LIVE_PEERS')

    def _collect_smoke_acceptance(self):
        # Optional scientific proof cannot obstruct safe lifecycle retirement.
        # Unknown means acceptance=False; never fall back to private body parse.
        search = aux_sent = snapshots = audits = None
        try:
            with self.core.ledger.mutex:
                count, tokens = self.core.ledger.db.execute(
                    "SELECT COUNT(*),COALESCE(SUM(input+output),0) FROM requests WHERE trajectory=? AND state='SETTLED'",
                    (self.t,)).fetchone()
                need(type(count) is int and type(tokens) is int and count >= 0 and tokens >= 0,
                     'SMOKE_ACCEPTANCE_ORIGINAL_SEARCH_COUNTERS')
                search = {'settled_model_calls': count, 'reported_tokens': tokens}
                aux_sent = self.core.ledger.db.execute(
                    "SELECT COUNT(*) FROM aux_permits p JOIN aux_scopes s ON p.scope=s.scope WHERE s.trajectory=? AND p.request_id IS NOT NULL AND p.state='TERMINAL'",
                    (self.t,)).fetchone()[0]
                rows = {(r[0], r[1], r[2]) for r in self.core.ledger.db.execute(
                    'SELECT generation,target,ref_sha FROM snapshots WHERE trajectory=?', (self.t,))}
                snapshots = all((p['generation'], p['target_tokens'], p['snapshot']['sha256']) in rows
                                for p in self.checkpoint.points) and len({p['snapshot']['sha256'] for p in self.checkpoint.points}) == 2
        except Exception:
            pass  # fixed unknown codes below; no private exception text
        try:
            audits = [self._public_k3_projection(point) for point in self.checkpoint.points]
        except Exception:
            audits = None
        return _acceptance_value(search=search, aux_sent=aux_sent, snapshots=snapshots, audits=audits)

    def _public_k3_projection(self, checkpoint_point):
        import native_replicate_attempts
        point_id = digest({'trajectory': self.t, 'target': checkpoint_point['target_tokens']})
        point = self.final.dispatcher.points[point_id]
        need(point['audited'] is True, 'SMOKE_ACCEPTANCE_REAL_ORIGINAL_AUDITED_POINT')
        aux = Path(point['aux']); path = aux/'K3_AUDIT.json'
        need(aux.is_absolute() and aux.resolve() == aux and not path.is_symlink() and
             path.resolve() == path and path.is_file() and path.stat().st_size <= 1024*1024,
             'SMOKE_ACCEPTANCE_ONLY_CANONICAL_OWN_PUBLIC_K3_SUMMARY')
        audit = strict(path.read_bytes())
        protocol = self.final.scope.protocol(self.t)
        need(type(audit) is dict and audit.get('schema') == 'count14-agensh-v21-k3-summary-v1' and
             audit.get('trajectory') == self.t and audit.get('setting') == self.core.rows[self.t]['arm'] and
             audit.get('nominal_budget') == checkpoint_point['target_tokens'] and
             audit.get('input_policy_sha256') == checkpoint_point['input_policy_sha256'] and
             audit.get('protocol_sha256') == protocol['final_v21'] and
             audit.get('source_sha256') == protocol['source_bundle'] and
             audit.get('complete') is True and audit.get('evaluation_complete') is True and
             audit.get('replicates_complete') == 3 and audit.get('search_feedback') is False and
             audit.get('billing_domain') == 'AUX_FINALIZATION', 'SMOKE_ACCEPTANCE_EXACT_PUBLIC_K3_IDENTITY')
        reported = audit.get('finalization_reported_tokens')
        candidates = audit.get('means', {}).get('unique_candidates')
        need(type(reported) is int and reported >= 0 and type(candidates) in (int, float) and
             math.isfinite(candidates) and candidates >= 0, 'SMOKE_ACCEPTANCE_PUBLIC_NUMERIC_COUNTERS')
        selected = native_replicate_attempts.selected(self.final.dispatcher, point)
        need(selected is not None, 'SMOKE_ACCEPTANCE_ORIGINAL_SELECTED_K3')
        # Bind this exact public summary to original durable COMPLETE metadata.
        queue = self.core.queue
        with queue.mutex:
            completions = [strict(r[0].encode()) for r in queue.db.execute(
                "SELECT metadata FROM events WHERE kind='COMPLETE'")]
            for record in selected:
                job = queue._job(record['job']['id'])
                expected = {'job_id': job['id'], 'result_sha256': job['result'], 'complete': True,
                    'unresolved_physical_custody': 0, 'original_k3_audit_sha256': digest(audit)}
                need(job['state'] == 'COMPLETE' and any(e.get('job_id') == job['id'] and
                     e.get('result_sha256') == job['result'] and e.get('audit_sha256') == digest(expected)
                     for e in completions), 'SMOKE_ACCEPTANCE_ORIGINAL_COMPLETE_AUDIT_DIGEST_BINDING')
        return {'complete': True, 'evaluation_complete': True, 'replicates_complete': 3,
                'reported_tokens': reported, 'unique_candidates_mean': candidates}

    def _stop_inventory(self):
        core = self.core; result = []; hosts = core.native_host_environment['trajectories'][self.t]
        for name, row in sorted(self.checkpoint.writer.containers.items()):
            labels = row['labels']; component = labels['component']; role = labels['role']
            binding = None
            if component in ('agent', 'router'):
                key = self.t, role, component
                binding = core.native_containers.records.get(key) or core.native_containers.boot_plans.get(key)
                need(binding is not None and binding.cid == row['cid'] and binding.image_id == row['image'] and
                     {'pid': binding.init_birth.pid, 'start_ticks': binding.init_birth.start_ticks,
                      'boot_id': binding.init_birth.boot_id} == row['process'],
                     'SMOKE_RETIREMENT_EXACT_ORIGINAL_ROLE_LAUNCH_BINDING')
            else:
                need(component == 'infra' and role.startswith('infra-'), 'SMOKE_RETIREMENT_EXACT_INFRA_COMPONENT')
                short = role[len('infra-'):]
                need(hosts['image_ids'][short] == row['image'], 'SMOKE_RETIREMENT_ORIGINAL_INFRA_IMAGE_PIN')
            result.append({'name': name, 'cid': row['cid'], 'image': row['image'], 'process': copy.deepcopy(row['process']),
                           'labels': copy.deepcopy(labels), 'component': component, 'role': role,
                           'binding': binding, 'phase': 'CHECK', 'prestop_clear': False})
        # Agent bridge must retain live router/services until archive ACK. All
        # role containers precede infrastructure; no daemon/root is removed.
        return sorted(result, key=lambda r: (0 if r['component'] == 'agent' else 1 if r['component'] == 'router' else 2, r['name']))

    def _receipt(self, kind, **metadata):
        self.sequence += 1
        value = {'schema': 'count14-smoke-same-owner-retirement-public-v1', 'sequence': self.sequence,
                 'kind': kind, 'state': self.state, 'at_monotonic_ns': time.monotonic_ns(),
                 'fees_changed': False, 'model_replays': 0, 'rm_prune_or_root_deletion': False, **metadata}
        publish(self.home/(str(self.sequence).zfill(4)+'-'+kind+'.json'), wire(value), mode=0o400)

    def _paid_zero(self):
        core = self.core
        with core.ledger.mutex:
            return (core.ledger.global_unresolved() == 0 and core.ledger.db.execute(
                "SELECT COUNT(*) FROM aux_permits WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0] == 0)

    def _check(self, item, *, running):
        row = self.core.native_containers.docker.inspect(item['cid'])
        need(row['id'] == item['cid'] and row['image'] == item['image'] and row['labels'] == item['labels'] and
             not row['paused'] and not row['restarting'] and row['stop_signal'] not in ('SIGKILL', '9'),
             'SMOKE_RETIREMENT_EXACT_CID_IMAGE_LABELS_AND_NORMAL_SIGNAL')
        if item['binding'] is not None:
            binding = item['binding']
            if not isinstance(binding, ContainerBinding):
                binding = ContainerBinding(self.t, item['role'], item['component'], binding.cid,
                    binding.image_id, binding.init_birth, binding.init_birth)
            self.core.native_containers.validate(binding, row, running=running)
        elif running:
            need(row['running'] and not row['dead'] and row['pid'] == item['process']['pid'],
                 'SMOKE_RETIREMENT_EXACT_LIVE_INFRA_INIT')
            birth = process_birth(row['pid'])
            need({'pid': birth.pid, 'start_ticks': birth.start_ticks, 'boot_id': birth.boot_id} == item['process'],
                 'SMOKE_RETIREMENT_INFRA_PID_START_BOOT_UNCHANGED')
        else:
            need(not row['running'] and row['pid'] == 0, 'SMOKE_RETIREMENT_ACTUAL_STOPPED_INFRA_REQUIRED')
            try:birth = process_birth(item['process']['pid'])
            except FileNotFoundError:birth = None
            need(birth is None or {'pid': birth.pid, 'start_ticks': birth.start_ticks,
                 'boot_id': birth.boot_id} != item['process'], 'SMOKE_RETIREMENT_OLD_INFRA_INIT_STILL_LIVE')
        return row

    def _empty_original_domain(self, item):
        """Fresh kernel populated=0, or exact retained cgroup inode unlinked.

        A vanished /proc PID alone is never this proof. No census is synthesized
        and no cgroup/process is created, migrated, removed or signalled here.
        """
        domain = self.domain_by_name[item['name']]
        st = os.fstat(domain.fd)
        need((st.st_dev, st.st_ino) == domain.inode,
             'SMOKE_RETIREMENT_RETAINED_ORIGINAL_CGROUP_FD_IDENTITY')
        try:
            raw = domain.read('cgroup.events')
        except OSError:
            # Linux cannot remove a populated cgroup. The original open fd must
            # identify the now-unlinked exact inode, not a path lookup failure.
            from native_retired_cgroup import exact_removed_cgroup2_leaf
            return (os.fstat(domain.fd).st_nlink == 0 or
                    exact_removed_cgroup2_leaf(domain, container_id=item['cid']))
        rows = dict(line.split() for line in raw.splitlines())
        need(rows.get('populated') in ('0', '1'), 'SMOKE_RETIREMENT_REAL_KERNEL_POPULATED_FIELD')
        return rows['populated'] == '0'

    def _remaining_router_clear(self, item):
        """Original startup-bound tool predicate for the still-live component.

        After a genuinely stopped/archived agent, the old two-LIVE-container
        projection must not be called as if that agent were still alive. Keep
        its proven terminal domain and check the remaining router using the
        SAME immutable original startup baseline + fresh original kernel census.
        """
        agent = next((r for r in self.role_items if r['role'] == item['role'] and r['component'] == 'agent'), None)
        if agent is None or agent['phase'] != 'DONE' or not self._empty_original_domain(agent):return False
        cli = self.core.bridge_owner.clis.get((self.t, item['role']))
        if cli is not None:
            from native_bridge_owner import same_child_alive
            if not cli['archived'] or cli['end_lease'] is not None or same_child_alive(cli['birth']):return False
        custody = self.core.native_kernel_tool_custody
        from smoke_racing_tools_fresh_baseline import FreshStartupBaseline
        from smoke_racing_tools_kernel_custody import kernel_census, _control_chain
        from smoke_racing_tools_cold_control_builder import control_snapshot_clear
        baseline = getattr(custody, 'fresh_startup_baselines', {}).get((self.t, item['role']))
        if baseline is None:
            with self.core.ledger.mutex:
                paid = self.core.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=?',
                                                  (self.t, item['role'])).fetchone()[0]
            if paid:return False
            binding = item['binding']
            if binding is None:return False
            allowed = set(_control_chain(binding.peer_birth, binding.init_birth)) if hasattr(binding, 'peer_birth') else {binding.init_birth}
            return set(kernel_census(binding.init_birth).members) <= allowed
        need(type(baseline) is FreshStartupBaseline and baseline.owner_birth == self.owner and
             baseline.contract_sha256 == digest(self.core.contract), 'SMOKE_RETIREMENT_ORIGINAL_UNPAID_STARTUP_BASELINE')
        component = next(c for c in baseline.components if c.component == 'router')
        binding = item['binding']
        need(binding is not None and (binding.cid, binding.image_id, binding.init_birth) ==
             (component.container_id, component.image_id, component.init_birth),
             'SMOKE_RETIREMENT_NO_ROUTER_REBASELINE_OR_NEW_CONTAINER')
        census = kernel_census(binding.init_birth)
        need((census.domain, census.domain_device, census.domain_inode) ==
             (component.domain, component.domain_device, component.domain_inode),
             'SMOKE_RETIREMENT_SAME_ORIGINAL_ROUTER_KERNEL_DOMAIN')
        allowed = set(component.members)
        if cli is None or not control_snapshot_clear(custody, self.t, item['role'], cli['birth']):
            if not hasattr(binding, 'peer_birth'):return False
            allowed = set(_control_chain(binding.peer_birth, binding.init_birth))
        return set(census.members) <= allowed

    def _role_clear(self, item):
        need(self._paid_zero(), 'SMOKE_RETIREMENT_NO_NEW_PAID_REQUEST_CAN_ENTER')
        if item['component'] == 'infra':return True
        if item['component'] == 'router':
            agent = next((r for r in self.role_items if r['role'] == item['role'] and r['component'] == 'agent'), None)
            if agent is not None and agent['phase'] == 'DONE':return self._remaining_router_clear(item)
        proof = self.core.native_physical_projection(self.t, item['role'])
        need(type(proof) is dict and set(proof) == {'models_clear', 'tools_clear'} and
             all(type(v) is bool for v in proof.values()), 'SMOKE_RETIREMENT_ORIGINAL_PHYSICAL_PROJECTION')
        return proof == {'models_clear': True, 'tools_clear': True}

    def _start_action(self, item, action):
        need(self.child is None and self._paid_zero(), 'SMOKE_RETIREMENT_SERIAL_ORIGINAL_CONTROL_ONLY')
        self._receipt('ACTION_INTENT', action=action, cid=item['cid'], component=item['component'])
        # ScopedDocker supplies the ORIGINAL update --restart=no / stop -t -1.
        self.child = self.core.native_containers.docker.mutate_once(action, item['cid'])
        self.child_action = action; self.started_ns = time.monotonic_ns(); self.warning120 = False
        self.action_history.append({'cid': item['cid'], 'action': action, 'child': self.child})
        self._receipt('ACTION_STARTED', action=action, cid=item['cid'], own_control_pid=self.child.pid)

    def _retire_role_peer(self, item):
        if item['component'] == 'infra':return True
        # A normal agent stop must finish the genuine native archive handshake;
        # administratively suspended logical history is not relabelled END.
        cli = self.core.bridge_owner.clis.get((self.t, item['role']))
        if item['component'] == 'agent' and cli is not None:
            from native_bridge_owner import same_child_alive
            if not cli['archived'] or cli['end_lease'] is not None or same_child_alive(cli['birth']):return False
        purpose = 'bridge' if item['component'] == 'agent' else 'router'
        key = self.t, item['role'], purpose
        with self.core.peers._lock:birth = self.core.peers._peers.get(key)
        if birth is not None:
            need(item['prestop_clear'] and self._paid_zero(), 'SMOKE_RETIREMENT_ORIGINAL_PRESTOP_PROOF_RETAINED')
            self.core.peers.retire_after_exit(self.t, item['role'], birth,
                original_physical_clear=True, purpose=purpose)
        return True

    def _stop_one(self, item):
        if self.child is not None:
            code = self.child.poll()
            if code is None:
                if not self.warning120 and time.monotonic_ns()-self.started_ns >= 120*10**9:
                    self.warning120 = True
                    self._receipt('CONTROL120_RETAIN_SAME_CHILD_NO_SIGNAL', cid=item['cid'], action=self.child_action)
                return False
            self._receipt('ACTION_EXIT', cid=item['cid'], action=self.child_action, exit_code=code)
            need(code == 0, 'SMOKE_RETIREMENT_ORIGINAL_DOCKER_CHILD_FAILED_RETAIN_NO_RETRY')
            prior = self.child_action; self.child = None; self.child_action = None
            item['phase'] = 'STOP' if prior == 'DISABLE_RESTART' else 'STOPPED'
        if item['phase'] == 'CHECK':
            row = self.core.native_containers.docker.inspect(item['cid'])
            if not row['running']:
                self._check(item, running=False)
                # Unexpected spontaneous exit is not manufactured tool/archive
                # evidence. Require its original lifecycle to prove clear.
                if not self._empty_original_domain(item):return False
                if item['component'] == 'agent':
                    cli = self.core.bridge_owner.clis.get((self.t, item['role']))
                    if cli is not None and (not cli['archived'] or cli['end_lease'] is not None):return False
                item['prestop_clear'] = True; item['phase'] = 'STOPPED'
            else:
                self._check(item, running=True)
                if not self._role_clear(item):return False  # ordinary natural progress
                item['prestop_clear'] = True; item['phase'] = 'UPDATE_PENDING'
                self._start_action(item, 'DISABLE_RESTART');return False
        if item['phase'] == 'STOP':
            row = self._check(item, running=True)
            need(row['restart_policy'] == 'no', 'SMOKE_RETIREMENT_RESTART_DISABLED_BEFORE_NORMAL_STOP')
            if not self._role_clear(item):return False
            item['prestop_clear'] = True; item['phase'] = 'STOP_PENDING'
            self._start_action(item, 'NORMAL_STOP');return False
        if item['phase'] == 'STOPPED':
            stopped_row = self._check(item, running=False)
            if not self._empty_original_domain(item):return False
            if not self._retire_role_peer(item):return False
            item['phase'] = 'DONE'; self.stopped.append(item['cid'])
            self._receipt('EXACT_CONTAINER_STOPPED_RETAINED', cid=item['cid'], component=item['component'],
                          container_exit_code=stopped_row['exit_code'])
            return True
        return item['phase'] == 'DONE'

    def _launcher_terminal(self):
        child = self.launch.child
        need(child is not None and self.launch.birth is not None and child.pid == self.launch.birth.pid,
             'SMOKE_RETIREMENT_ORIGINAL_LAUNCHER_POPEN_RETAINED')
        code = child.poll()
        if code is None:return False
        need(type(code) is int, 'SMOKE_RETIREMENT_REAL_LAUNCHER_WAIT_REQUIRED')
        key = self.t, 'worker-00', 'launcher'
        with self.core.peers._lock:birth = self.core.peers._peers.get(key)
        if birth is not None:
            need(birth == self.launch.birth and self._paid_zero(), 'SMOKE_RETIREMENT_EXACT_LAUNCHER_BIRTH')
            self.core.peers.retire_after_exit(self.t, 'worker-00', birth,
                original_physical_clear=True, purpose='launcher')
        self._receipt('ORIGINAL_LAUNCHER_WAITED', exit_code=code)
        return True

    def step(self):
        if self.state in ('SMOKE_FULLY_RETIRED', 'PARTIAL_RETAINED_NO_RETRY'):return self.public()
        try:
            self._same_owner()
            # Original same owner continues native archive/END receipts. Sources
            # stop new observation/model admission, never an accepted child.
            if self.state == 'SEARCH_AND_K3_COMPLETE_NOT_RETIRED':
                self.core.system_health.stop_admission();self.core.resource_producer.stop_admission()
                self.state = 'WAITING_ORIGINAL_SYSTEM_AND_RESOURCE_TERMINAL';return self.public()
            self.core.poll_native_control_once()
            if self.state == 'WAITING_ORIGINAL_SYSTEM_AND_RESOURCE_TERMINAL':
                if not self.core.system_health.physical_clear() or not self.core.resource_producer.physical_clear():return self.public()
                need(self._paid_zero(), 'SMOKE_RETIREMENT_PAID_CUSTODY_REAPPEARED')
                self.core.gate.shutdown()  # wake UNSENT only; accepted paid work is already zero
                self.core.membership_fences[self.t].begin_final_retirement(
                    original_snapshot_sha256=self.reference['sha256'],
                    original_ledger_generation=self.writer.generation, original_models_closed=True)
                from native_checkpoint_clock_rearm import rearm_before_native_thaw
                rearm_before_native_thaw(self.writer,final_retirement=True)
                self.writer.writer_fence.request_final_retirement_thaw()
                self.state = 'THAWING_FINAL_WRITERS_NO_SEARCH_RESUME';return self.public()
            if self.state == 'THAWING_FINAL_WRITERS_NO_SEARCH_RESUME':
                if not self.writer.writer_fence.poll_final_retirement_thaw():return self.public()
                self.state = 'STOPPING_PROVEN_CLEAR_ROLE_CONTAINERS';self.index = 0;return self.public()
            if self.state == 'STOPPING_PROVEN_CLEAR_ROLE_CONTAINERS':
                if self.index < len(self.role_items):
                    if self._stop_one(self.role_items[self.index]):self.index += 1
                    return self.public()
                self.state = 'WAITING_ORIGINAL_LAUNCHER_EXIT';return self.public()
            if self.state == 'WAITING_ORIGINAL_LAUNCHER_EXIT':
                if not self._launcher_terminal():return self.public()
                self.state = 'STOPPING_EXACT_INFRASTRUCTURE';self.index = 0;return self.public()
            if self.state == 'STOPPING_EXACT_INFRASTRUCTURE':
                if self.index < len(self.infra_items):
                    if self._stop_one(self.infra_items[self.index]):self.index += 1
                    return self.public()
                self.state = 'CLOSING_TERMINAL_ORIGINAL_CONTROLLERS';return self.public()
            if self.state == 'CLOSING_TERMINAL_ORIGINAL_CONTROLLERS':
                need(self._paid_zero() and not self.core.peers._peers and
                     self.core.system_health.physical_clear() and self.core.resource_producer.physical_clear(),
                     'SMOKE_RETIREMENT_ALL_ORIGINAL_CHILD_MODEL_AND_PEER_CUSTODY_TERMINAL')
                self.final.close_after_drained()
                # Cache BEFORE queue.close inside original core close. No later
                # PUBLIC path should query that closed SQLite queue connection.
                f = self.core.ledger.frontier(self.t)
                self.cached_public = {'schema': 'count14-smoke-retirement-public-v1',
                    'state': 'CLOSING_TERMINAL_ORIGINAL_CONTROLLERS', 'containers_stopped_retained': len(self.stopped),
                    'normal_docker_actions': len(self.action_history), 'SEARCH_state': f['state'],
                    'SEARCH_generation': f['generation'], 'SEARCH_actual': f['actual'],
                    'original_final_queue_counts': copy.deepcopy(self.core.queue.frontier()),
                    'original_final': copy.deepcopy(self.final.public()), 'all_paid_physical_clear': True,
                    'all_peers_retired': True, 'launcher_exit_code': self.launch.child.returncode,
                    'rm_prune_root_deletion': False, 'fully_retired': False,
                    'smoke_acceptance': self.acceptance['smoke_acceptance'],
                    'smoke_acceptance_evidence': copy.deepcopy(self.acceptance)}
                self.core.smoke_terminal_public = copy.deepcopy(self.cached_public)
                self.core.close_original_transports_after_drained()
                self.state = 'SMOKE_FULLY_RETIRED'
                self.cached_public.update(state=self.state, fully_retired=True)
                self.core.smoke_terminal_public = copy.deepcopy(self.cached_public)
                self._receipt('SMOKE_FULLY_RETIRED', containers_stopped_retained=len(self.stopped))
            return self.public()
        except Exception as error:
            self.failure = {'exception_type': type(error).__name__, 'refusal_code': getattr(error, 'code', None),
                            'phase': self.state}
            self.state = 'PARTIAL_RETAINED_NO_RETRY'
            self._receipt('FAILED_RETAINED', **self.failure)
            return self.public()

    def public(self):
        if self.cached_public is not None:
            value = copy.deepcopy(self.cached_public)
            value['state'] = self.state; value['failure'] = copy.deepcopy(self.failure)
            return value
        return {'schema': 'count14-smoke-retirement-public-v1', 'state': self.state,
                'containers_stopped_retained': len(self.stopped), 'normal_docker_actions': len(self.action_history),
                'control_child_retained': self.child is not None, 'fully_retired': False,
                'rm_prune_root_deletion': False, 'failure': copy.deepcopy(self.failure),
                'smoke_acceptance': self.acceptance['smoke_acceptance'],
                'smoke_acceptance_evidence': copy.deepcopy(self.acceptance)}


def create_smoke_retirement(core, *, checkpoint, final, launch):
    previous = getattr(core, 'smoke_retirement', None)
    try:return SmokeFinalRetirement(core, checkpoint=checkpoint, final=final, launch=launch)
    except Exception as error:
        partial = getattr(core, 'smoke_retirement', None)
        if partial is not previous and type(partial) is SmokeFinalRetirement:
            partial.failure = {'exception_type': type(error).__name__,
                               'refusal_code': getattr(error, 'code', None), 'phase': partial.state}
            partial.state = 'PARTIAL_RETAINED_NO_RETRY'
        raise
