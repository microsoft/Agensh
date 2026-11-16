"""Future cold-native owner-loop ordering, not writer/paid/SDK authority.

Refuse BEFORE any original native handler/clock observation unless the SAME
actual original held writer is already bound. Metadata-only checks. No new
capability, clock reset, inbox drain, Popen, storage write or admission grant.
"""
from pathlib import Path
import hashlib
import importlib
import os
import threading

from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
import paid_cold_material as M

HELD_WRITER_SHA256='686247ad8d2ca768abf1dc0085ac4a18e58419f37e2bceb61b152d8f8b413261'
HOST_SHA256='dadf6ce97da5a7f57d239ac7f4bbbdd397308745c36fa9575d48c524c6ecfb85'


def _original(name,pin):
    value=importlib.import_module(name);p=Path(value.__file__)
    M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and
        hashlib.sha256(p.read_bytes()).hexdigest()==pin,
        'NATIVE_POLL_WRITER_GUARD_EXACT_ORIGINAL_SOURCE')
    return value


def _require_original_writer(stage,record,*,read_budget):
    """Private exact capability predicate; does not accept a replacement record.

    OWN qualifications may exercise this predicate on a genuine registered OWN
    stage. The production entry below ALWAYS requires original own=False T.
    Returning an existing writer here never opens or changes one.
    """
    M.need(type(read_budget)is ReadBudget,'NATIVE_POLL_WRITER_GUARD_FINITE_BUDGET');read_budget.check()
    H=_original('normal_held_financial_writer',HELD_WRITER_SHA256)
    M.need(H._GRAPHS.get(id(stage))is record and record['stage']is stage and
        stage.core.ledger is stage.ledger and stage.core.queue is stage.queue and
        stage.new_owner_birth==process_birth(os.getpid())and
        not stage.ledger.mutex._is_owned()and not stage.queue.mutex._is_owned(),
        'NATIVE_POLL_WRITER_GUARD_SAME_GENUINE_STAGE_BIRTH_AND_UNLOCKED_GRAPH')
    writer=record['writer']
    M.need(type(writer)is H.NormalHeldFinancialWriter and H._WRITERS.get(id(writer))is writer and
        writer._seal is H._SEAL and writer._stage is stage and
        writer._database is stage.ledger.db and
        writer.old_owner_birth==stage.old_owner_birth and writer.new_owner_birth==stage.new_owner_birth and
        writer.OWN is stage.OWN,
        'NATIVE_POLL_WAIT_ACTUAL_ORIGINAL_HELD_WRITER_BEFORE_HANDLER_OR_CLOCK')
    # Never reset the original clock's latched failure or make an inert method
    # readable merely for a control request. Every enabled method is the SAME
    # actual original bound method held by this stage, not a caller callback.
    M.need(all(getattr(stage.ledger,name)is stage._ledger_methods[name]for name in H._FINANCIAL)and
        all(getattr(stage.resources,name)is bound for name,bound in stage._resource_methods.items())and
        not writer._database.in_transaction and stage.core.active_clock.failure_type is None,
        'NATIVE_POLL_ORIGINAL_WRITER_METHODS_BOUND_NO_TRANSACTION_OR_CLOCK_FAULT')
    read_budget.check();return writer


def require_registered_poll_writer(graph,*,read_budget):
    """Production-only real host graph/T/services/writer ordering preflight."""
    M.need(type(read_budget)is ReadBudget,'NATIVE_POLL_WRITER_GUARD_FINITE_BUDGET');read_budget.check()
    H=_original('normal_held_financial_writer',HELD_WRITER_SHA256)
    host=_original('new_owner_host_control',HOST_SHA256)
    M.need(host.registered_stage_host_graph(graph.stage)is graph and graph.stage.OWN is False and
        graph.core is graph.stage.core and graph.registration.new_owner_birth==process_birth(os.getpid()),
        'NATIVE_POLL_ONLY_REAL_ORIGINAL_PRODUCTION_HOST_STAGE_NOT_OWN_OR_DICT')
    record=H._same(graph.stage,read_budget,own=False)
    return _require_original_writer(graph.stage,record,read_budget=read_budget)
