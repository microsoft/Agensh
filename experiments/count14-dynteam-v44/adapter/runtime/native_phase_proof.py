"""Bounded read-only proof inbox on the existing owner's metadata loop.

Only own source/role/native-session control metadata and two booleans. No
scientific prompt/result/command, financial mutation or new scientific loop.
Receipt threads wait with deadlines OUTSIDE every ledger/queue/science lock.
"""
from collections import deque
from dataclasses import dataclass
import threading
import uuid

COMMIT = "70e2ca54c078597e3314755064d2ef1a83344c8e"
FIELDS = {"schema", "source_commit", "trajectory_id", "role_slot", "native_session_uuid"}


def checked_proof(row):
    if not (type(row) is dict and set(row) == FIELDS and
            row["schema"] == "count14-native-phase-physical-proof-v1" and row["source_commit"] == COMMIT and
            type(row["trajectory_id"]) is str and 0 < len(row["trajectory_id"]) <= 512 and
            type(row["role_slot"]) is str and (row["role_slot"] == "racing-background-00" or
            row["role_slot"] in {f"racing-player-{i:02d}" for i in range(7)})):
        raise ValueError("DYNTEAM_RACING_EXACT_NATIVE_PHASE_PROOF_FIELDS")
    sid = row["native_session_uuid"]
    if sid is not None:
        try:
            valid = type(sid) is str and str(uuid.UUID(sid)) == sid
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("DYNTEAM_RACING_EXACT_NATIVE_PHASE_PROOF_SESSION")
    return row


@dataclass
class ProofTicket:
    row: dict
    peer: tuple
    complete: threading.Event
    result: dict | None = None


def _checked_control_proof_result(proof):
    if proof is None:return None
    if not (type(proof) is dict and set(proof)=={'models_clear','tools_clear'} and
            all(type(v) is bool for v in proof.values())):
        raise ValueError('DYNTEAM_RACING_PHASE_PROOF_ORIGINAL_BOOLEAN_PROJECTION')
    return dict(proof)


class NativePhaseProofInbox:
    def __init__(self, *, timeout=30):
        from native_control_inbox import OwnerControlQueue
        self._queue=OwnerControlQueue(checked=checked_proof,timeout=timeout,
                                     result_normalizer=_checked_control_proof_result)
        self.timeout,self.lock,self.pending=self._queue.timeout,self._queue.lock,self._queue.pending

    def receive(self,row,peer):
        return self._queue.receive(row,peer)

    def poll_once(self, *, sessions, original_physical_projection):
        def original_proof(row,peer):
            key=(row['trajectory_id'],row['role_slot']);sid=row['native_session_uuid']
            try:bound_sid=sessions[key]
            except KeyError:bound_sid=None
            if sid!=bound_sid:raise ValueError('DYNTEAM_RACING_PHASE_PROOF_EXACT_CURRENT_SESSION')
            return _checked_control_proof_result(original_physical_projection(*key))
        return self._queue.poll_once(original_proof)['processed']

    def public(self):return self._queue.public()
