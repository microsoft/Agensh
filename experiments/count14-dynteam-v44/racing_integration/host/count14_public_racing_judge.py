"""m7 execution feedback using ONLY the original SEARCH public-task tools.

This module runs inside the scientific runtime, not the coordinator. It does
not open candidates, task/source, outputs, an evaluator socket or a reference
binary itself. The original sandbox/tool port supplies opaque signed public
outcomes; management never reads the scientific signatures or case contents.
No model call/retry, financial write, privileged Docker or cleanup is added.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import threading
from concurrent.futures import Future, TimeoutError as FutureTimeout

from common import need, digest


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True)
class PublicToolScope:
    original_v2_tool_binding_sha256: str
    original_count14_catalogue_sha256: str
    native_scope_sha256: str
    original_public_tools_only: bool
    official_evaluator_access: bool
    private_reference_access: bool

    def checked(self):
        need(all(_sha(x) for x in (self.original_v2_tool_binding_sha256,
                                   self.original_count14_catalogue_sha256, self.native_scope_sha256)) and
             self.original_public_tools_only is True and self.official_evaluator_access is False and
             self.private_reference_access is False, "DYNTEAM_RACING_PUBLIC_TOOL_ONLY_NO_EVALUATOR_OR_REFERENCE")
        return self


@dataclass(frozen=True)
class PublicRunOutcome:
    native_scope_sha256: str
    original_tool_receipt_sha256: str
    task_slot: int
    valid_public_execution: bool
    observed_public_failure: bool
    failure_signature_sha256: str | None
    physical_terminal: bool

    def checked(self, scope):
        need(self.native_scope_sha256 == scope.native_scope_sha256 and
             _sha(self.original_tool_receipt_sha256) and type(self.task_slot) is int and 1 <= self.task_slot <= 14 and
             all(type(v) is bool for v in (self.valid_public_execution, self.observed_public_failure,
                                          self.physical_terminal)) and
             (self.failure_signature_sha256 is None or _sha(self.failure_signature_sha256)) and
             (not self.observed_public_failure or _sha(self.failure_signature_sha256)),
             "DYNTEAM_RACING_ORIGINAL_PUBLIC_TOOL_OUTCOME_FIELDS")
        return self


class NativePublicProbePort:
    """Owner-bound ORIGINAL SDK/sandbox operations, never an evaluator shim.

    run_case takes the native opaque case directory and deadline; existing_cases
    enumerates only the original team's public cases (not official test inputs).
    physical_clear is the original tool-custody boolean. Callbacks are invoked
    outside all metadata/science locks and must carry their native time limits.
    """
    def __init__(self, *, scope, run_case, existing_cases, physical_clear):
        need(type(scope) is PublicToolScope and all(callable(p) for p in
             (run_case, existing_cases, physical_clear)), "DYNTEAM_RACING_ORIGINAL_PUBLIC_PORTS")
        self.scope = scope.checked()
        self.run_case, self.existing_cases, self.physical_clear = run_case, existing_cases, physical_clear


class Count14PublicRacingJudge:
    """Keep m7 run-result/defend and failure-signature novelty mechanics.

    Domain adaptation: reproduce a public count14 target failure TWICE, rather
    than compare ProgramBench's private reference to a replacement program.
    These are public-tool outcomes, NOT official count14 success verdicts.
    Distinct original tool receipts are mandatory; no old result is replayed.
    """
    def __init__(self, port, *, active_now):
        need(type(port) is NativePublicProbePort and callable(active_now),
             "DYNTEAM_RACING_COUNT14_ORIGINAL_PUBLIC_JUDGE_PORT")
        self.port, self.active_now = port, active_now
        self._existing = None
        self._lock = threading.Lock()
        self._busy = 0
        self._seen_receipts = set()
        self._existing_future = None
        self.existing_partial = False

    def _run(self, case_directory, deadline):
        outcome = self.port.run_case(case_directory, deadline)
        need(type(outcome) is PublicRunOutcome, "DYNTEAM_RACING_TYPED_ORIGINAL_TOOL_OUTCOME")
        outcome.checked(self.port.scope)
        with self._lock:
            need(outcome.original_tool_receipt_sha256 not in self._seen_receipts,
                 "DYNTEAM_RACING_PUBLIC_TOOL_RECEIPT_MUST_BE_NEW")
            self._seen_receipts.add(outcome.original_tool_receipt_sha256)
        return outcome

    def judge(self, test_dir, deadline=None, budget_s=None):
        now = self.active_now()
        end = float("inf") if deadline is None else deadline
        if budget_s is not None:
            need(type(budget_s) in (int, float) and math.isfinite(budget_s) and budget_s > 0,
                 "DYNTEAM_RACING_PUBLIC_TOOL_BOUNDED_EXECUTION")
            end = min(end, now + budget_s)
        if now >= end:
            return self._invalid("PUBLIC_TOOL_NOT_ADMITTED_DEADLINE")
        with self._lock:
            self._busy += 1
        try:
            first = self._run(test_dir, end)
            if not first.physical_terminal:
                return self._pending()
            if not first.valid_public_execution:
                return self._invalid("PUBLIC_TOOL_INVALID_OR_INFRASTRUCTURE")
            if self.active_now() >= end:
                return self._invalid("PUBLIC_TOOL_REPEAT_NOT_ADMITTED_DEADLINE")
            second = self._run(test_dir, end)
            if not second.physical_terminal:
                return self._pending()
            if (not second.valid_public_execution or first.task_slot != second.task_slot or
                    first.observed_public_failure != second.observed_public_failure or
                    first.failure_signature_sha256 != second.failure_signature_sha256):
                return self._invalid("PUBLIC_TOOL_NOT_REPRODUCIBLE")
            signature = None if not first.observed_public_failure else digest([
                "COUNT14_PUBLIC_REPRODUCIBLE_FAILURE_V1", self.port.scope.original_count14_catalogue_sha256,
                first.task_slot, first.failure_signature_sha256])
            return dict(valid=True, fail=first.observed_public_failure, signature=signature,
                        judge="count14-original-public-tools", official_verdict=False)
        except Exception:
            # Scientific result remains infrastructure-unknown/invalid, never
            # fabricate a pass/fail, expose an error message or retry a model.
            return self._invalid("PUBLIC_TOOL_FAILED_RETAIN_CUSTODY")
        finally:
            with self._lock:
                self._busy -= 1

    def _invalid(self, code):
        return dict(valid=False, fail=False, signature=None, error=code,
                    judge="count14-original-public-tools", official_verdict=False)

    def _pending(self):
        return dict(valid=False, fail=False, signature=None, pending=True,
                    judge="count14-original-public-tools", official_verdict=False)

    def physical_clear(self):
        with self._lock:
            busy = self._busy
        return busy == 0 and self.port.physical_clear() is True

    def existing_signature_map(self):
        # Native Game requests this serially after its original preload future.
        with self._lock:
            cached = None if self._existing is None else dict(self._existing)
        if cached is not None:
            return cached
        with self._lock:
            leader = self._existing_future is None
            if leader:
                self._existing_future = Future()
            future = self._existing_future
        if not leader:
            try:
                return dict(future.result(timeout=2))  # never wait under our lock
            except FutureTimeout:
                self.existing_partial = True
                return {}
        result = {}
        try:
            cases = self.port.existing_cases()
            need(type(cases) is tuple and len({identifier for identifier, _ in cases}) == len(cases),
                 "DYNTEAM_RACING_ORIGINAL_EXISTING_PUBLIC_CASE_CATALOGUE")
            end = self.active_now() + 120  # original native existing-case budget
            for identifier, directory in cases:
                if self.active_now() >= end:
                    self.existing_partial = True
                    break
                verdict = self.judge(directory, deadline=end)
                if verdict["valid"] and verdict["fail"]:
                    result[identifier] = verdict["signature"]
                elif not verdict["valid"]:
                    self.existing_partial = True
        except Exception:
            self.existing_partial = True
        with self._lock:
            if self._existing is None:
                self._existing = result
            completed = dict(self._existing)
        future.set_result(completed)
        return completed

    def existing_signatures(self):
        return set(self.existing_signature_map().values())
