"""Equivalent fresh full-team cgroup coverage with O(P+D) kernel observations.

No persisted caches, no skipped PID/cgroup/domain/owner checks. The membership
matrix is still exhaustively evaluated, using a fresh, double-observed local
snapshot; not O(P*D) repetitions of expensive filesystem/kernel observations.
"""
from pathlib import Path
import hashlib,inspect,os,time
import native_writer_fence as w
from common import need,digest,hash_file
from bridge import process_identity

ORIGINAL_COVERAGE_SHA256='529f69390cd4bda8cf3ccf3b45cc7ccff263c48b9252fafb460c08e289f9fe9c'

def coverage_linear(self):
    start=time.monotonic_ns()
    current=w.registered_participants(self.owner)
    if self.whole_team is not None:current.update(self.whole_team.current())
    need(current==self.participants,'WRITER_FENCE_REGISTERED_PROCESSES_CHANGED')
    domains=tuple(self.domains)
    # Every pinned domain still checks original inode, path, owner exclusion.
    # Recheck at end: no old result can be reused by the next call/cut/archive.
    for domain in domains:domain.current()
    groups={key:w.process_cgroup_v2(identity)for key,identity in current.items()}
    covered=set()
    for key,relative in groups.items():
        matches=[i for i,d in enumerate(domains)if relative.is_relative_to(d.relative)]
        need(len(matches)==1,'WRITER_FENCE_EVERY_WORKER_AND_SDK_EXACTLY_ONE_DOMAIN')
        covered.update(matches)
    need(covered==set(range(len(domains))),'WRITER_FENCE_NO_UNRELATED_DOMAIN')
    # Fresh endpoint validation includes PID/start/boot on both cgroup reads,
    # catching moves/replacements DURING this observation, not after a TTL.
    for key,identity in current.items():
        need(w.process_cgroup_v2(identity)==groups[key],
             'WRITER_FENCE_CGROUP_CHANGED_DURING_COVERAGE')
    for domain in domains:domain.current()
    after=w.registered_participants(self.owner)
    if self.whole_team is not None:after.update(self.whole_team.current())
    need(after==current==self.participants and tuple(self.domains)==domains,
         'WRITER_FENCE_REGISTERED_PROCESSES_CHANGED')
    self._r16_coverage_metrics={'participants':len(current),'domains':len(domains),
        'domain_current_calls':2*len(domains),'participant_cgroup_calls':2*len(current),
        'membership_pairs_evaluated':len(current)*len(domains),
        'duration_ns':time.monotonic_ns()-start,'cross_call_cache':False}

def install_driver_linear_coverage(driver):
    """Same live driver only. Class/object/locks/frozen domains stay untouched.

    This cannot magically rewrite a currently executing old _coverage frame.
    Such a frame runs to completion; all subsequent calls use this method.
    Install before acquiring ledger.mutex so long old observations need not
    block the method change itself. Provenance append can wait for old owner.
    """
    from run_native_scientific6 import ScientificSixDriver
    need(type(driver)is ScientificSixDriver and driver.shared_started
         and not driver.failed and not driver.finished,'R16_COVERAGE_LIVE_ORIGINAL_DRIVER')
    old=w.NativeWriterFence._coverage
    if old is coverage_linear:
        return {'schema':'r16-same-owner-linear-coverage-v1','already_installed':True,
                'no_model_task_charge_or_freeze_request':True}
    need(hashlib.sha256(inspect.getsource(old).encode()).hexdigest()==ORIGINAL_COVERAGE_SHA256,
         'R16_COVERAGE_ORIGINAL_SOURCE_PIN')
    fences=[]
    for t,r in driver.records.items():
        launch=r.get('launch');c=getattr(launch,'controller',None)
        need(c is not None and r.get('phase')=='ORIGINAL_TASK_RELEASED',
             'R16_COVERAGE_ALL_ORIGINAL_TASKS_REQUIRED')
        fence=c.fence
        need(type(fence)is w.NativeWriterFence and fence.ledger is driver.ledger
             and fence.owner is c.team and fence.t==t and fence.whole_team is not None,
             'R16_COVERAGE_ORIGINAL_FULL_TEAM_FENCE')
        need(process_identity(os.getpid())==fence.owner._stage_owner_identity,
             'R16_COVERAGE_ORIGINAL_PROCESS_OWNER')
        fences.append(fence)
    driver._r16_original_coverage_method=old
    w.NativeWriterFence._coverage=coverage_linear
    proof={'schema':'r16-same-owner-linear-coverage-v1','same_owner':True,
        'fences':len(fences),'no_model_task_charge_or_freeze_request':True,
        'original_method_sha256':ORIGINAL_COVERAGE_SHA256,
        'implementation_sha256':hash_file(Path(__file__))['sha256'],
        'domain_owner_inode_path_cgroup_pid_guards_retained':True,
        'no_cross_call_cache':True,'ledger_lock_and_existing_old_frames_not_forced':True}
    driver._r16_linear_coverage_installation=proof
    with driver.ledger.tx():driver.ledger.event('GLOBAL','R16_LINEAR_FRESH_CGROUP_COVERAGE_INSTALLED',proof)
    return proof
