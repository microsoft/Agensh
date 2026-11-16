"""Cold-only role lifecycle gate on the ORIGINAL admission condition.

No schema/financial method/formula changes, model retry or force termination.
Birth/end metadata is written only after releasing the original ledger lock.
All waits remain the original Condition.wait, which releases the same RLock.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import textwrap
import time
from types import MethodType

from admission_gate import AdmissionGate
from common import need

ORIGINAL_RESERVE_SHA256 = "f75e312bc89bc656f4795707b19c8ed4ba6b5912e3babac593dee18031bdf368"


def _compile_original_reserve():
    source = textwrap.dedent(inspect.getsource(AdmissionGate.reserve))
    need(hashlib.sha256(source.encode()).hexdigest() == ORIGINAL_RESERVE_SHA256,
         "DYNTEAM_ORIGINAL_ADMISSION_LOOP_PIN")
    tree = ast.parse(source)
    loops = [n for n in ast.walk(tree) if isinstance(n, ast.While) and
             isinstance(n.test, ast.Constant) and n.test.value is True]
    need(len(loops) == 1, "DYNTEAM_ONE_ORIGINAL_ADMISSION_LOOP")
    addition = ast.parse("if identity in self._dynteam_role_control.native_end_holds:\n"
                         "    need(False, 'ROLE_END_HOLD_NO_SEND')\n"
                         "elif identity in self._dynteam_role_control.held:\n"
                         "    self.condition.wait(timeout=0.25)\n"
                         "    continue\n").body[0]
    # Keep original HTTP-custody, shutdown and real accounting fault guards
    # BEFORE this local unsent hold: a disconnected waiter must still retire.
    position = next(i for i, n in enumerate(loops[0].body) if isinstance(n, ast.Assign) and
                    any(isinstance(t, ast.Name) and t.id == "f" for t in n.targets))
    loops[0].body.insert(position, addition)
    ast.fix_missing_locations(tree)
    # Reverse only this addition, proving all original schema/query/budget and
    # request-ID behavior (including reserve race protection) remains intact.
    removed = loops[0].body.pop(position)
    need(ast.dump(tree, include_attributes=False) == ast.dump(ast.parse(source), include_attributes=False),
         "DYNTEAM_ROLE_HOLD_NO_OTHER_ADMISSION_CHANGE")
    loops[0].body.insert(position, removed)
    namespace = {}
    exec(compile(tree, __file__ + ":original_reserve_with_role_hold", "exec"),
         AdmissionGate.reserve.__globals__, namespace)
    return namespace["reserve"]


class DynamicRoleGate:
    def __init__(self, ledger):
        need(hasattr(ledger, "_dynteam_catalogues"), "DYNTEAM_ONLY_NEW_SCOPE_ROLE_GATE")
        self.ledger = ledger
        self.held = {(t, role) for t, roles in ledger._dynteam_catalogues.items() for role in roles}
        self.births = {}
        self.epoch = 0
        self.gates = []
        # Only authenticated native END intents, never startup holds.
        self.native_end_holds = {}

    def install_cold(self, gate):
        need(type(gate) is AdmissionGate and gate.ledger is self.ledger and
             not hasattr(gate, "_dynteam_role_control"), "DYNTEAM_ORIGINAL_COLD_GATE_INSTALL_ONCE")
        reserve = _compile_original_reserve()
        with self.ledger.capacity_changed:
            need(not self.ledger.db.execute("SELECT 1 FROM requests LIMIT 1").fetchone() and
                 not gate.waiters, "DYNTEAM_ROLE_GATE_INSTALL_BEFORE_ANY_MODEL_OR_WAITER")
            gate._dynteam_role_control = self
            gate.reserve = MethodType(reserve, gate)
            self.gates.append(gate)
        return gate

    def open_birth(self, trajectory, role, birth_sha256, *, durable_metadata, previous_physical_clear):
        need(type(birth_sha256) is str and len(birth_sha256) == 64 and
             all(c in "0123456789abcdef" for c in birth_sha256), "DYNTEAM_NATIVE_BIRTH_CONTROL_SHA")
        with self.ledger.capacity_changed:
            key = (trajectory, role)
            need(trajectory in self.ledger._dynteam_catalogues and
                 role in self.ledger._dynteam_catalogues[trajectory], "DYNTEAM_REGISTERED_NATIVE_BIRTH")
            if self.births.get(key) == birth_sha256 and key not in self.held:
                return False
            need(self.gates and durable_metadata is True and previous_physical_clear is True,
                 "DYNTEAM_BIRTH_REQUIRES_DURABLE_METADATA_PHYSICAL_CLEAR")
            need(key not in self.births, "DYNTEAM_SLOT_PREVIOUS_BIRTH_NOT_ENDED")
            self.births[key] = birth_sha256
            self.held.discard(key)
            self.epoch += 1
            self.ledger.capacity_changed.notify_all()
            return True

    def hold_end(self, trajectory, role, birth_sha256):
        with self.ledger.capacity_changed:
            key = (trajectory, role)
            need(self.births.get(key) == birth_sha256, "DYNTEAM_RETIRE_EXACT_CURRENT_BIRTH")
            self.held.add(key)
            self.epoch += 1
            self.ledger.capacity_changed.notify_all()
            return self.epoch

    def hold_native_end(self, trajectory, role, birth_sha256, token_sha256):
        """Cold-bound exact current CLI END. Never cancels an admitted row."""
        need(type(token_sha256) is str and len(token_sha256) == 64,
             'DYNTEAM_NATIVE_END_EXACT_TOKEN_SHA')
        with self.ledger.capacity_changed:
            key = (trajectory, role)
            need(self.births.get(key) == birth_sha256,
                 'DYNTEAM_NATIVE_END_EXACT_CURRENT_BIRTH')
            old = self.native_end_holds.get(key)
            if old is not None:
                need(old['token_sha256'] == token_sha256 and old['birth'] == birth_sha256,
                     'DYNTEAM_NATIVE_END_INTENT_CANNOT_CHANGE')
                return False
            self.native_end_holds[key] = dict(token_sha256=token_sha256,
                birth=birth_sha256, since_ns=time.monotonic_ns())
            self.held.add(key)
            self.epoch += 1
            self.ledger.capacity_changed.notify_all()
            return True

    def complete_native_end(self, trajectory, role, token_sha256):
        with self.ledger.capacity_changed:
            key = (trajectory, role)
            old = self.native_end_holds.get(key)
            need(old is not None and old['token_sha256'] == token_sha256,
                 'DYNTEAM_NATIVE_END_COMPLETE_EXACT_INTENT')
            del self.native_end_holds[key]
            # A vacant or shut down role stays in the original held set.
            self.ledger.capacity_changed.notify_all()

    def native_end_status(self, trajectory):
        with self.ledger.capacity_changed:
            rows = [v for k, v in self.native_end_holds.items() if k[0] == trajectory]
            now = time.monotonic_ns()
            return dict(held_role_count=sum(k[0] == trajectory for k in self.held),
                        held_native_END_roles=len(rows), longest_native_END_hold_ns=
                        max((now-v['since_ns'] for v in rows), default=0))

    def reopen_same_logical_birth(self, trajectory, role, birth_sha256, *, previous_cli_exited,
                                 previous_physical_clear, new_cli_metadata_durable):
        # A checker/tester/racing CLI reconnect is not a new logical agent or
        # fresh budget. Same roster/ordinal/fee/session ledger remain intact.
        with self.ledger.capacity_changed:
            key = (trajectory, role)
            need(key in self.held and self.births.get(key) == birth_sha256 and
                 all(v is True for v in (previous_cli_exited, previous_physical_clear, new_cli_metadata_durable)),
                 "DYNTEAM_SAME_AGENT_CLI_REOPEN_EXACT_DRAINED_BOUNDARY")
            self.held.remove(key)
            # Original verified same-logical birth reopens admission.
            self.native_end_holds.pop(key, None)
            self.epoch += 1
            self.ledger.capacity_changed.notify_all()

    def original_role_counts(self, trajectory, role):
        """Only original financial/control COUNT projections, never bodies."""
        with self.ledger.mutex:
            key = (trajectory, role)
            need(key in self.held, "DYNTEAM_CLOSE_ROLE_GATE_BEFORE_DRAIN_CHECK")
            requests = self.ledger.db.execute(
                "SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=? AND state IN ('RESERVED','SENT','UNKNOWN')",
                key).fetchone()[0]
            tools = self.ledger.db.execute(
                "SELECT COUNT(*) FROM operations WHERE trajectory=? AND role=? AND state='ACTIVE'", key).fetchone()[0]
            # UNKNOWN is deliberately retained here. The production integration
            # must use the separately qualified original modern-v2 physical
            # custody projection; billing charge alone is NOT permission to end.
            return {"original_request_rows_not_proven_terminal": requests, "original_active_operations": tools}

    def finish_end(self, trajectory, role, birth_sha256, *, physical_models_clear,
                   physical_tools_clear, native_process_exited, durable_metadata):
        with self.ledger.capacity_changed:
            key = (trajectory, role)
            need(key in self.held and self.births.get(key) == birth_sha256,
                 "DYNTEAM_END_EXACT_HELD_BIRTH")
            need(all(v is True for v in (physical_models_clear, physical_tools_clear,
                                         native_process_exited, durable_metadata)),
                 "DYNTEAM_NORMAL_PHYSICAL_END_AND_DURABLE_METADATA_REQUIRED")
            del self.births[key]
            # Vacant/retired role stays held. Only a genuinely new durable
            # birth reopens it; no implicit empty-slot model admission.
            self.epoch += 1
            self.ledger.capacity_changed.notify_all()
