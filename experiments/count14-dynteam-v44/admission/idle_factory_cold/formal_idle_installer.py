"""One explicit cold-only original-watchdog install on the existing cohort."""
from pathlib import Path


def install(cohort, sources):
    from common import need
    from native_formal_cohort import NativeFormalCohort, FormalCohortSources
    from native_idle_source import NativeIdleSources
    from native_idle_watchdog import install_native_idle_watchdog
    need(type(cohort)is NativeFormalCohort and type(sources)is FormalCohortSources and
         cohort.sources is sources and not cohort.activation_attempted and
         not hasattr(cohort,'formal_retirement') and not hasattr(cohort,'native_idle_watchdog'),
         'FORMAL_IDLE_EXACT_BIND_COHORT_THEN_WATCHDOG_THEN_RETIREMENT_COLD_ORDER')
    path=Path(sources.native_pbench_source)
    # The same frozen native source, original library and opaque template tree.
    # NativeIdleWatchdog pins CODE; only native runtime opens the idle asset.
    return install_native_idle_watchdog(cohort,sources=NativeIdleSources(
        pbench_source=path,prompt_render_library=path.with_name('lib_prompts.sh'),
        opaque_prompts_directory=path.parent.parent/'prompts'))
