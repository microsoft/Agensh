"""Pure control fence around native membership effects during original cuts.

NOT a replacement checkpoint state machine, dispatcher or snapshotter. Native
CLAIM decisions/events can queue while held; only starting a birth/rotation/end
effect is gated. Caller polls; no waiting, IO, SQL or callback under this lock.
Only ORIGINAL ledger/native quiescence and opaque snapshot receipts qualify a
cut. There is no cancellation, refund, retry, model request or agent-count cap.
"""
from dataclasses import dataclass
import threading
import uuid

from dynteam_metadata import catalogue, digest, integer, need


@dataclass(frozen=True)
class Lease:
    operation_id: str
    role: str
    action: str
    epoch_before: int


class MembershipFence:
    def __init__(self, *, worker_slots=32, racing_players=0):
        self.roles = catalogue(worker_slots, racing_players=racing_players)
        self._lock = threading.Lock()
        self._leases = {}
        self._role_busy = set()
        self._epoch = 0
        self._cut = None
        self._sealed = None
        self._last_generation = 0
        self._final_retirement = None

    def public_counts(self):
        with self._lock:
            return dict(registered_roles=len(self.roles),pending_native_effects=len(self._leases),
                        cut_held=self._cut is not None,membership_epoch=self._epoch)

    def owns(self,lease,role):
        with self._lock:
            return (type(lease) is Lease and lease.role==role and
                    self._leases.get(lease.operation_id)==lease)

    def acquire(self, role, action):
        need(role in self.roles, "DYNTEAM_FENCE_REGISTERED_SLOT")
        need(action in ("BIRTH", "SESSION_REPLACE", "NATIVE_END"), "DYNTEAM_FENCE_NATIVE_EFFECT")
        with self._lock:
            retirement=(self._final_retirement==(self._cut,self._sealed) and
                        self._final_retirement is not None and action=='NATIVE_END')
            if (self._cut is not None and not retirement) or role in self._role_busy:
                return None  # native launcher defers; never wait under a lock
            lease = Lease(uuid.uuid4().hex, role, action, self._epoch)
            self._leases[lease.operation_id] = lease
            self._role_busy.add(role)
            return lease

    def begin_final_retirement(self,*,original_snapshot_sha256,original_ledger_generation,
                               original_models_closed):
        """After sealed final capture ONLY: admit END, never a new birth/model.

        Physical final model/HTTP/AUX checks belong to the same trusted owner
        outside this pure control lock. No ledger, subprocess, IO or wait here.
        This does not release the checkpoint or reopen scientific admission.
        """
        need(type(original_models_closed) is bool and original_models_closed,
             'DYNTEAM_RETIREMENT_REQUIRES_ORIGINAL_MODELS_CLOSED')
        integer(original_ledger_generation,'DYNTEAM_RETIREMENT_ORIGINAL_GENERATION',1)
        with self._lock:
            token=(original_ledger_generation,original_snapshot_sha256)
            need(self._cut==original_ledger_generation and self._sealed==original_snapshot_sha256 and
                 self._sealed is not None and not self._leases,
                 'DYNTEAM_RETIREMENT_ONLY_SEALED_ORIGINAL_FINAL_CUT_WITH_NO_EFFECTS')
            need(self._final_retirement in (None,token),'DYNTEAM_RETIREMENT_TOKEN_CANNOT_CHANGE')
            if self._final_retirement==token:return False
            self._final_retirement=token
            return True

    def finish(self, lease, *, original_control_receipt_sha256):
        need(type(original_control_receipt_sha256) is str and len(original_control_receipt_sha256) == 64 and
             all(c in "0123456789abcdef" for c in original_control_receipt_sha256),
             "DYNTEAM_NATIVE_CONTROL_RECEIPT_REQUIRED")
        with self._lock:
            need(type(lease) is Lease and self._leases.get(lease.operation_id) == lease,
                 "DYNTEAM_EXACT_NATIVE_EFFECT_LEASE")
            del self._leases[lease.operation_id]
            self._role_busy.remove(lease.role)
            self._epoch += 1

    def request_cut(self, original_ledger_generation):
        integer(original_ledger_generation, "DYNTEAM_ORIGINAL_CUT_GENERATION", 1)
        with self._lock:
            if self._cut == original_ledger_generation:
                return False
            need(self._cut is None and original_ledger_generation > self._last_generation,
                 "DYNTEAM_NO_OVERLAPPING_OR_REPLAYED_CUT")
            self._cut = original_ledger_generation
            self._sealed = None
            return True

    def ready(self, *, original_models_quiescent, original_tools_quiescent):
        need(type(original_models_quiescent) is bool and type(original_tools_quiescent) is bool,
             "DYNTEAM_ORIGINAL_QUIESCENCE_BOOLEANS")
        with self._lock:
            if self._cut is None or self._leases or not original_models_quiescent or not original_tools_quiescent:
                return None
            return {"original_generation": self._cut, "membership_epoch": self._epoch,
                    "native_membership_admission_closed": True, "pending_native_effects": 0,
                    "full_static_role_catalogue_sha256": digest(self.roles)}

    def verify_after_original_capture(self, token):
        with self._lock:
            need(type(token) is dict and token == {
                "original_generation": self._cut, "membership_epoch": self._epoch,
                "native_membership_admission_closed": True, "pending_native_effects": 0,
                "full_static_role_catalogue_sha256": digest(self.roles)} and
                self._cut is not None and not self._leases,
                "DYNTEAM_MEMBERSHIP_UNCHANGED_THROUGH_ORIGINAL_CAPTURE")
            return True

    def note_original_snapshot(self, token, *, original_snapshot_sha256):
        need(type(original_snapshot_sha256) is str and len(original_snapshot_sha256) == 64 and
             all(c in "0123456789abcdef" for c in original_snapshot_sha256), "DYNTEAM_ORIGINAL_OPAQUE_SNAPSHOT_RECEIPT")
        with self._lock:
            # Inline pure comparison, avoiding recursive non-reentrant locks.
            need(self._cut is not None and not self._leases and token == {
                "original_generation": self._cut, "membership_epoch": self._epoch,
                "native_membership_admission_closed": True, "pending_native_effects": 0,
                "full_static_role_catalogue_sha256": digest(self.roles)},
                "DYNTEAM_MEMBERSHIP_UNCHANGED_THROUGH_ORIGINAL_CAPTURE")
            need(self._sealed in (None, original_snapshot_sha256), "DYNTEAM_SNAPSHOT_CANNOT_BE_REPLACED")
            self._sealed = original_snapshot_sha256

    def after_original_resume(self, *, previous_snapshot_sha256, new_ledger_generation):
        integer(new_ledger_generation, "DYNTEAM_ORIGINAL_NEXT_GENERATION", 2)
        with self._lock:
            need(self._final_retirement is None and self._cut is not None and self._sealed is not None and
                 self._sealed == previous_snapshot_sha256 and new_ledger_generation == self._cut + 1 and
                 not self._leases, "DYNTEAM_ORIGINAL_DURABLE_SNAPSHOT_AND_RESUME_REQUIRED")
            self._last_generation = self._cut
            self._cut = None
            self._sealed = None
