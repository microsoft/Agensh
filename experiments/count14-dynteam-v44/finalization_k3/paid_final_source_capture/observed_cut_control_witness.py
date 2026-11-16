"""Validate already-observed original six-cut RAM witness; never re-poll HTTP.

Not a fresh global cut/whole-seal authority. Original full base pre-capture must
have really observed the barrier; post-retired HTTP custody is a separate guard.
"""
import copy
from common import need


def observed_six_cut_witness(owner):
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from normal_cold_barrier import NormalCheckpointBarrier, HELD_PHASES
    from normal_cold_sealer import NormalColdCandidateSealer
    from native_dynamic_checkpoint import DynamicCheckpointPorts
    need(type(owner) is NativeColdOwner and type(owner.core) is OriginalRelayCore,
         'FINAL_WITNESS_EXACT_ORIGINAL_OWNER_CORE')
    core=owner.core;barrier=owner.normal_cold_barrier;source=owner.normal_cold_sealer
    need(type(barrier) is NormalCheckpointBarrier and type(source) is NormalColdCandidateSealer
         and source.owner is owner and source.core is core and source.barrier is barrier
         and barrier.owner is owner and barrier.core is core
         and barrier.cohort is owner.scientific_smoke and barrier.cohort.owner is owner
         and barrier.cohort.core is core,
         'FINAL_WITNESS_SAME_ORIGINAL_REGISTERED_SOURCE_BARRIER_COHORT')
    barrier._current();source._current()
    need(barrier.requested and barrier.last_static_observation is True and barrier.failure is None
         and len(core.rows)==6 and set(core.rows)==set(barrier.observed)==set(barrier.checkpoints)==set(barrier.cohort.tracks),
         'FINAL_WITNESS_REAL_PRIOR_SIX_STATIC_OBSERVATION_REQUIRED')
    for t,record in barrier.checkpoints.items():
        cp=record[0];row=barrier.cohort.tracks[t];observed=barrier.observed[t]
        need(type(cp) is DynamicCheckpointPorts and cp is row['checkpoint'] and cp.core is core and cp.t==t
             and cp.state in HELD_PHASES and observed['phase']==cp.state
             and observed['held_phase'] is True and observed['original_frozen_checkpoint_verified'] is True
             and cp.writer is not None and cp.writer.writer_fence.state=='PARKED'
             and row['host'].held is True and cp.formal_host_writers is row['host']
             and cp.reference==cp.writer.reference and cp.reference['sha256']==observed['snapshot_sha256'],
             'FINAL_WITNESS_SAME_ORIGINAL_HELD_CHECKPOINT_PARKED_WRITER_AND_REFERENCE')
    return dict(requested=barrier.requested,
        observed_six_original_frozen_cut_stability=barrier.last_static_observation,
        tracks=copy.deepcopy(barrier.observed))
