"""Read original durable n3 point proofs; partial-n remains strictly WAIT.

No audit/metrics/evaluation is rerun. Only original PUBLIC K3 summaries and
host queue/process control metadata are consumed. This WIP does not implement
or pretend to authorize an n<3 producer; missing/unsupported evidence is never
filled with a Boolean. No ledger/queue mutation or scientific action in reads.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import copy
import json
import os
import stat

from common import need, digest, hash_file, strict
from formal_scope import FORMAL_CUTS, validate_contract
from native_peer_registry import process_birth


@dataclass(frozen=True)
class FormalPointTerminalEvidence:
    contract_sha256: str
    original_owner_birth_sha256: str
    basis_sha256: str
    points: tuple

    def public(self):
        return {'schema': 'count14-formal100m-verified-point-terminals-public-v1',
            'contract_sha256': self.contract_sha256,
            'original_owner_birth_sha256': self.original_owner_birth_sha256,
            'basis_sha256': self.basis_sha256, 'terminal_points': len(self.points),
            'effective_n': [p[3] for p in self.points],
            'original_n3_only': True, 'nlt3_producer_implemented': False,
            'physical_unknown_slot_release_claimed': False}


class FormalPointTerminalSource:
    """One exact new cohort, original controller and readonly verification chain."""
    def __init__(self, cohort):
        from native_formal_cohort import NativeFormalCohort
        from native_cold_owner import NativeColdOwner
        from original_relay_core import OriginalRelayCore
        need(type(cohort) is NativeFormalCohort and type(cohort.owner) is NativeColdOwner and
             type(cohort.core) is OriginalRelayCore and cohort.owner.core is cohort.core and
             cohort.owner.scientific_smoke is cohort and not cohort.core.qualification_only,
             'FORMAL_TERMINAL_SOURCE_SAME_EXACT_ORIGINAL_OWNER_COHORT')
        validate_contract(cohort.core.contract, digest(cohort.core.contract))
        need(cohort.birth == process_birth(os.getpid()), 'FORMAL_TERMINAL_SOURCE_SAME_OWNER_BIRTH')
        self.cohort, self.core, self.birth = cohort, cohort.core, copy.deepcopy(cohort.birth)
        self.contract_sha256, self.rows_sha256 = digest(self.core.contract), digest(self.core.rows)
        self._issued = None

    @staticmethod
    def _public_audit(path):
        path = Path(path)
        info = path.lstat()
        need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
             stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid() and
             not info.st_mode & 0o022 and info.st_nlink == 1 and info.st_size <= 16 * 1024 * 1024,
             'FORMAL_TERMINAL_ORIGINAL_REGULAR_PUBLIC_AUDIT')
        before = hash_file(path)
        audit = strict(path.read_bytes())
        need(hash_file(path) == before, 'FORMAL_TERMINAL_PUBLIC_AUDIT_STABLE')
        return audit, before

    def _snapshot(self, cohort):
        from formal_controller import FormalFinalController
        import final_attempts
        need(cohort is self.cohort and cohort.core is self.core and self.birth == process_birth(os.getpid()) and
             digest(self.core.contract) == self.contract_sha256 and digest(self.core.rows) == self.rows_sha256,
             'FORMAL_TERMINAL_CURRENT_SAME_ORIGINAL_OWNER_AND_REGISTERED_SCOPE')
        final = cohort.final
        if final is None or final.state != 'RELEASED':
            return None
        need(type(final) is FormalFinalController and final.core is self.core and
             final.dispatcher.ledger is self.core.ledger and final.dispatcher.queue is self.core.queue,
             'FORMAL_TERMINAL_ORIGINAL_SHARED_FINAL_CONTROLLER')
        ledger, queue, dispatcher = self.core.ledger, self.core.queue, final.dispatcher
        need(not ledger.mutex._is_owned() and not queue.mutex._is_owned(),
             'FORMAL_TERMINAL_NO_FILES_OR_WAIT_WITH_SCIENCE_LOCK_HELD')
        if not dispatcher.lock.acquire(timeout=0.25):
            return None
        try:
            points = {k: {'aux': Path(v['aux']), 'jobs': tuple(v['jobs']), 'audited': v['audited']}
                      for k, v in dispatcher.points.items()}
        finally:
            dispatcher.lock.release()
        expected = {digest({'trajectory': t, 'target': cut}): (t, cut)
                    for t in self.core.rows for cut in FORMAL_CUTS}
        if set(points) != set(expected) or not all(p['audited'] is True for p in points.values()):
            # Includes all partial-n cases until its separate legitimate producer
            # and accepted-receipt consumer are actually integrated.
            return None
        if not queue.mutex.acquire(timeout=0.25):
            return None
        try:
            queued_points = {r['point']: dict(r) for r in queue.db.execute('SELECT * FROM points')}
            effective = copy.deepcopy(final_attempts.effective_rows(queue))
            completions = [strict(r[0]) for r in queue.db.execute(
                "SELECT metadata FROM events WHERE kind='COMPLETE' LIMIT 10001")]
        finally:
            queue.mutex.release()
        need(len(completions) <= 10000, 'FORMAL_TERMINAL_BOUNDED_PUBLIC_COMPLETE_EVENTS')
        if set(queued_points) != set(expected) or len(effective) != 72 or any(j['state'] != 'COMPLETE' for j in effective):
            return None
        evidence, basis = [], []
        protocol = self.core.contract['v2_baseline_reference_protocol']
        for point, (t, cut) in sorted(expected.items()):
            row, record = queued_points[point], points[point]
            need(row['trajectory'] == t and row['target'] == cut and row['setting'] == self.core.rows[t]['arm'],
                 'FORMAL_TERMINAL_QUEUE_ORIGINAL_POINT_IDENTITY')
            facade = final.facades[t]
            need(point in facade.points and facade.points[point]['ready'] is True and
                 record['aux'] == Path(facade.points[point]['home']) and
                 record['aux'].is_relative_to(Path(self.core.rows[t]['root']) / 'final' / 'final-points'),
                 'FORMAL_TERMINAL_AUX_FROM_ACTUAL_ORIGINAL_FACADE_NOT_RECONSTRUCTED_RAW_POINT')
            audit, file_pin = self._public_audit(record['aux'] / 'K3_AUDIT.json')
            need(audit.get('schema') == 'count14-agensh-v21-k3-summary-v1' and
                 audit.get('trajectory') == t and audit.get('setting') == row['setting'] and
                 audit.get('nominal_budget') == cut and audit.get('input_policy_sha256') == row['input_policy'] and
                 audit.get('source_sha256') == protocol['source_bundle'] and
                 audit.get('protocol_sha256') == protocol['final_v21'] and
                 audit.get('complete') is True and audit.get('evaluation_complete') is True and
                 type(audit.get('replicates_complete')) is int and audit['replicates_complete'] == 3 and
                 audit.get('billing_domain') == 'AUX_FINALIZATION' and audit.get('search_feedback') is False,
                 'FORMAL_TERMINAL_ORIGINAL_N3_PUBLIC_AUDIT_EXACT_SCOPE')
            reps = audit.get('evidence')
            need(type(reps) is list and len(reps) == 3 and
                 {r['replicate_index'] for r in reps} == {1, 2, 3},
                 'FORMAL_TERMINAL_ORIGINAL_N3_REPLICATE_EVIDENCE')
            jobs = sorted((j for j in effective if j['point'] == point), key=lambda j: j['replicate'])
            need(len(jobs) == 3 and [j['replicate'] for j in jobs] == [1, 2, 3],
                 'FORMAL_TERMINAL_THREE_ORIGINAL_EFFECTIVE_QUEUE_JOBS')
            for job in jobs:
                rep = next(r for r in reps if r['replicate_index'] == job['replicate'])
                terminal = strict(job['terminal'])
                identity = strict(job['child'])
                need(terminal.get('wait_observed') is True and terminal.get('identity') == identity and
                     terminal.get('exit_code') == 0 and terminal.get('signal') is None and
                     job['result'] == rep['aggregate']['sha256'] and
                     job.get('attempt', 1) == rep.get('replicate_attempt', 1),
                     'FORMAL_TERMINAL_NATIVE_EFFECTIVE_JOB_TRUE_WAIT_RESULT_AND_ATTEMPT')
                proof = {'job_id': job['id'], 'result_sha256': job['result'], 'complete': True,
                         'unresolved_physical_custody': 0, 'original_k3_audit_sha256': digest(audit)}
                matching = [e for e in completions if e.get('job_id') == job['id']]
                need(len(matching) == 1 and matching[0].get('result_sha256') == job['result'] and
                     matching[0].get('audit_sha256') == digest(proof),
                     'FORMAL_TERMINAL_ORIGINAL_DURABLE_COMPLETE_EVENT_AUDIT_BINDING')
            evidence.append((t, cut, point, 3, file_pin['sha256']))
            basis.append({'point': row, 'audit': file_pin, 'jobs': jobs})
        return tuple(evidence), digest(basis)

    def read_verified_terminal_points(self, cohort):
        snapshot = self._snapshot(cohort)
        if snapshot is None:
            return None
        points, basis = snapshot
        evidence = FormalPointTerminalEvidence(digest(self.core.contract), digest(asdict(self.birth)), basis, points)
        self._issued = evidence
        return evidence

    def verify(self, cohort, evidence):
        need(type(evidence) is FormalPointTerminalEvidence and evidence is self._issued,
             'FORMAL_TERMINAL_ONLY_THIS_SOURCES_ACTUAL_ISSUED_EVIDENCE')
        snapshot = self._snapshot(cohort)
        need(snapshot is not None and snapshot == (evidence.points, evidence.basis_sha256),
             'FORMAL_TERMINAL_FRESH_UNCHANGED_PUBLIC_AND_QUEUE_PROOFS')
        return evidence.public()

    def close_shared_final_after_drained(self, final, evidence):
        need(final is self.cohort.final and final.core is self.core,
             'FORMAL_TERMINAL_CLOSE_ONLY_SAME_ORIGINAL_SHARED_FINAL')
        self.verify(self.cohort, evidence)
        # Full n3 path retains BOTH original close guards and original server
        # close. An n<3 close is deliberately NOT substituted or made up here.
        return final.close_after_drained()
