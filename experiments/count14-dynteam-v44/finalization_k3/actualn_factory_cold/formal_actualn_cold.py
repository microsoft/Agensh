"""One cold actual-n source using the pre-existing same-owner allowance control.

No owner/control/controller/dispatcher constructor, grant, SQL write or loop is
introduced here. The outer allowance factory must ensure its control first.
"""
from pathlib import Path
import hashlib


def need(ok,code):
    if not ok:raise ValueError(code)


def original_kernel_paths():
    root=Path(__file__).resolve().parent/'original-public-kernels'
    return {name:root/filename for name,filename in (
        ('policy','partial_n_policy.py'),('selection','partial_n_selection.py'),
        ('durable','durable_final.py'),('raw4','aux_allowance.py'))}


def original_sidecar_path():
    return Path(__file__).resolve().parent/'original-public-kernels/terminal.py'


def create_actualn_source(cohort,*,rows_provider=None):
    from native_formal_cohort import NativeFormalCohort
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from allowance_control import FormalAllowanceControl
    from allowance_original import PINS,load_kernels
    from formal_nlt3_source import FormalActualNTerminalSource,FormalTypedQueueRows
    need(type(cohort)is NativeFormalCohort and type(cohort.owner)is NativeColdOwner and
         type(cohort.core)is OriginalRelayCore and cohort.owner.core is cohort.core and
         cohort.owner.scientific_smoke is cohort and not cohort.activation_attempted and
         not cohort.core.closed and not cohort.core.qualification_only and
         set(cohort.core.gate.startup_held)==set(cohort.tracks) and
         hasattr(cohort,'native_idle_watchdog') and hasattr(cohort,'formal_tester_cold_sources') and
         not hasattr(cohort,'formal_retirement') and not hasattr(cohort,'formal_actualn_source'),
         'FORMAL_ACTUALN_AFTER_IDLE_TESTER_BEFORE_RETIREMENT_COLD_ONLY')
    core=cohort.core;control=getattr(core,'formal_allowance_control',None)
    need(type(control)is FormalAllowanceControl and control.owner is cohort.owner and
         control.core is core,'FORMAL_ACTUALN_REUSE_OUTER_SAME_OWNER_EXACT_CONTROL_NO_SECOND_CTOR')
    control.fresh()
    need(control.kernels.source_sha256==PINS and
         load_kernels(control.kernels.source_paths).source_sha256==PINS,
         'FORMAL_ACTUALN_EXISTING_CONTROL_ORIGINAL_POLICY_AND_SOURCE_BYTES')
    # Paths may differ after an authorized cold copy; original complete byte
    # pins, not guessed/historical paths, authenticate the same kernels.
    with core.ledger.mutex:
        need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0 and
             core.ledger.db.execute('SELECT COUNT(*) FROM aux_permits').fetchone()[0]==0,
             'FORMAL_ACTUALN_NEW_COLD_ZERO_REQUESTS_AND_PERMITS')
    need(cohort.final is None,'FORMAL_ACTUALN_SOURCE_BEFORE_SINGLE_CONTROLLER_PREPARE')
    provider=control if rows_provider is None else rows_provider
    # Existing exact typed validator checks same queue/core and rejects OWN
    # carrier authority. Both all/effective ports use this one provider.
    FormalTypedQueueRows(core,provider)
    source=FormalActualNTerminalSource(cohort,
        original_kernel_paths=control.kernels.source_paths,
        sidecar_public_code=original_sidecar_path(),rows_provider=provider)
    cohort.formal_actualn_source=source
    return source


def install_actualn_retirement(cohort,*,terminal_source=None):
    from formal_nlt3_source import FormalActualNTerminalSource
    from formal_nlt3_binding import bind_retirement_source
    from formal_cohort_retirement import install_formal_retirement
    need(type(terminal_source)is FormalActualNTerminalSource and
         getattr(cohort,'formal_actualn_source',None)is terminal_source and
         terminal_source.cohort is cohort and terminal_source.core is cohort.core,
         'FORMAL_ACTUALN_ONE_SAME_COLD_SOURCE_RETIREMENT')
    retirement=install_formal_retirement(cohort,terminal_source=None)
    # Original constructor remains exact; private typed aliases are installed
    # only at its existing all-held WAIT_SOURCE seam. No fake evidence/home.
    return bind_retirement_source(retirement,terminal_source)
