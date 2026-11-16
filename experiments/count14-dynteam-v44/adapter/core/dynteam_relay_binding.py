"""Reuse TWO original v2 functions, not a second model transport or ledger.

This seam must be installed BEFORE native launcher activation. Real lifecycle
hooks/34-role registration/cold owner/checkpoint/K3 still need qualification.
It is a component, NOT a runnable experiment owner or permission to send.
"""
from dynteam_metadata import need
from dynteam_sessions import CohortSessions


def install(engine, sessions, *, key_path):
    from scientific_relay import ScientificRelay
    from fresh48_session import before_admission
    from glm_session_header import install_search
    from feasibility_relay import Rejected
    from types import MethodType

    need(type(engine) is ScientificRelay and type(sessions) is CohortSessions,
         "DYNTEAM_ORIGINAL_RELAY_COHORT_MAPPING")
    need(not getattr(engine, "_dynteam_affinity_installed", False), "DYNTEAM_AFFINITY_INSTALL_ONCE")
    # Critical ordering: missing birth/SID must be refused BEFORE reserve/SENT,
    # not first discovered by the raw opener (which would create an UNKNOWN).
    original_run = before_admission(engine, sessions)
    guarded_run = engine.run
    opener = install_search(engine, sessions, key_path=key_path)
    # Enter the context separately so only the initial mapping lookup can be
    # translated; no scientific exception/result is reclassified or retried.
    def request_bound_run(_, request, identity, emit=None, *, http_custody=None):
        scope = sessions.original_request(identity)
        try:
            scope.__enter__()
        except KeyError:
            raise Rejected("ORIGINAL_CLI_SESSION_METADATA_NOT_YET_AVAILABLE", 503) from None
        try:
            return guarded_run(request, identity, emit=emit, http_custody=http_custody)
        finally:
            scope.__exit__(None, None, None)
    engine.run = MethodType(request_bound_run, engine)
    engine._dynteam_affinity_installed = True
    return {"original_run": original_run, "original_header_opener": opener,
            "same_original_payload_transport": True,
            "ledger_or_retry_rules_modified": False, "models_started": 0}
