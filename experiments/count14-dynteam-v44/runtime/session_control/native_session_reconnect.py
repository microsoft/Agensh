"""Preflight for the upstream's existing normal CLI reconnect boundary.

No paid SDK census extension. The router closes its old connection only after
the original owner proves the old session physically clear. The unmodified
bridge then performs its real wait/archive/END, and the original CLI epoch
machinery qualifies a genuinely new direct child before any next prompt.
"""
from collections import deque
from dataclasses import dataclass
import hashlib
import json
import threading
import uuid

from common import need
from native_peer_registry import process_birth
from native_session_control import checked as checked_session
from native_bridge_owner import same_child_alive


SCHEMA = 'count14-native-normal-session-reconnect-v1'
# Original ClaimChecker and the existing private racing phase adapter use
# stateless freshSession boundaries. Workers/tester remain unmodified.
ROLE = frozenset(('checker-00', 'racing-background-00',
                  *(f'racing-player-0{i}' for i in range(7))))


def checked(row):
    need(type(row) is dict and set(row) == {
        'schema', 'source_commit', 'trajectory_id', 'block', 'role_slot',
        'logical_birth_sha256', 'native_turn_sha256', 'native_session_uuid',
        'reconnect_id'}, 'DYNTEAM_RECONNECT_EXACT_CONTROL_FIELDS')
    need(row['schema'] == SCHEMA and row['role_slot'] in ROLE,
         'DYNTEAM_RECONNECT_ONLY_ORIGINAL_SAME_ACCOUNT_ROLES')
    projected = {k: v for k, v in row.items() if k != 'reconnect_id'}
    projected['schema'] = 'count14-dynteam-native-session-ready-v1'
    checked_session(projected)
    try:
        canonical = str(uuid.UUID(row['reconnect_id']))
    except (ValueError, TypeError, AttributeError):
        canonical = None
    need(type(row['reconnect_id']) is str and canonical == row['reconnect_id'],
         'DYNTEAM_RECONNECT_CANONICAL_NONCE')
    return row


class NativeSessionReconnectInbox:
    """Fresh owner checks, finite waiters and no completed-grant ACK cache."""
    def __init__(self, *, timeout=30, maximum=128):
        from native_control_inbox import OwnerControlQueue
        self._queue=OwnerControlQueue(checked=checked,timeout=timeout,maximum=maximum)
        self.timeout,self.maximum=self._queue.timeout,self._queue.maximum
        self.lock,self.pending=self._queue.lock,self._queue.pending

    def receive(self,row,peer):
        return self._queue.receive(row,peer) is True

    def poll_once(self,epochs):
        def handle(row,peer):
            try:return epochs.reconnect.prepare(row,peer) is True
            except Exception as error:
                owner=getattr(epochs,'reconnect',None)
                if type(owner) is NativeSessionReconnectOwner:
                    places=[];tb=error.__traceback__
                    while tb is not None:
                        places.append(dict(file=tb.tb_frame.f_code.co_filename,
                            function=tb.tb_frame.f_code.co_name,line=tb.tb_lineno));tb=tb.tb_next
                    owner.failures.append(dict(exception_type=type(error).__name__,
                        PUBLIC_code='DYNTEAM_NORMAL_RECONNECT_RETAIN_NO_CLOSE',locations=places))
                    owner.failures=owner.failures[-128:]
                raise
        return self._queue.poll_once(handle)['accepted']

    def public(self):
        return self._queue.public()


@dataclass(frozen=True)
class Permit:
    request_sha256: str
    role_key: tuple
    old_epoch: object
    old_session: tuple
    request_anchor: int
    logical_birth: str
    peer_birth: object


class NativeSessionReconnectOwner:
    def __init__(self, epochs):
        self.epochs, self.core = epochs, epochs.core
        self.pending = {}
        self.completed = set()
        self.intents = {}
        self.owner_thread = threading.get_ident()
        self.failures = []

    def _owner(self):
        self.epochs._owner()
        need(threading.get_ident() == self.owner_thread,
             'DYNTEAM_RECONNECT_EXISTING_SINGLE_OWNER_LOOP_ONLY')

    def pending_trajectory(self, trajectory):
        return any(key[0] == trajectory for key in self.pending)

    def prepare(self, row, peer):
        checked(row)
        e, core = self.epochs, self.core
        self._owner()
        key = row['trajectory_id'], row['role_slot']
        need(core.publisher.bindings.get(key) == row['block'] and
             core.peers.validate(row, peer) is True,
             'DYNTEAM_RECONNECT_SAME_ACTUAL_REGISTERED_ROUTER')
        raw = json.dumps(row, sort_keys=True, separators=(',', ':')).encode()
        request = hashlib.sha256(raw).hexdigest()
        need(request not in self.completed, 'DYNTEAM_RECONNECT_CONSUMED_INTENT_NO_REPLAY')
        need(self.intents.get(row['reconnect_id'], request) == request,
             'DYNTEAM_RECONNECT_NONCE_CANNOT_CHANGE_BINDING')
        epoch = e.current.get(key)
        cli = core.bridge_owner.clis.get(key)
        need(epoch is not None and cli is not None and not cli['archived'] and
             key not in e.partial and key not in e.pending and epoch.first_session and
             epoch.owner_birth == e.owner and epoch.contract_sha256 == e.sha and
             cli['birth'] == epoch.child and cli['token'] == epoch.token and
             row['logical_birth_sha256'] == cli['raw_birth'] and
             row['native_turn_sha256'] == epoch.token[3] and
             same_child_alive(epoch.child),
             'DYNTEAM_RECONNECT_EXACT_EXISTING_LIVE_CLI_EPOCH')
        session = e._session(key)
        birth = core.roles.births.get(key)
        need(type(session) is tuple and session == (birth, row['native_session_uuid']) and
             (key, row['native_session_uuid']) in e.session_bound,
             'DYNTEAM_RECONNECT_ONLY_PREVIOUS_DURABLY_BOUND_SESSION')
        with core.peers._lock:
            actual_peer = core.peers._peers.get((*key, 'router'))
        need(actual_peer is not None and process_birth(actual_peer.pid) == actual_peer,
             'DYNTEAM_RECONNECT_ROUTER_FULL_BIRTH_STILL_EXACT')
        previous = self.pending.get(key)
        if previous is not None:
            need(previous.request_sha256 == request and previous.old_epoch == epoch and
                 previous.old_session == session and previous.peer_birth == actual_peer and
                 previous.request_anchor == e._count(key) and key in core.roles.held and
                 core.membership_fences[key[0]].public_counts()['cut_held'] is False,
                 'DYNTEAM_RECONNECT_SAME_PENDING_INTENT_ONLY')
            e._project_epoch(epoch)  # fresh original zero + unchanged old kernel set
            return True
        with core.ledger.mutex:
            frontier = core.ledger.frontier(key[0])
        need(frontier['state'] == 'RUNNING' and key[0] not in core.gate.startup_held and
             key not in core.roles.held and
             core.membership_fences[key[0]].public_counts()['cut_held'] is False,
             'DYNTEAM_RECONNECT_BEFORE_CUT_ONLY_LIVE_RELEASED_ROLE')
        e._project_epoch(epoch)  # NEVER adopts any unknown paid process
        count = e._count(key)
        permit = Permit(request, key, epoch, session, count, birth, actual_peer)
        # Close only original unsent admission, never alter a financial record.
        core.roles.hold_end(*key, birth)
        self.pending[key] = permit  # retain before fallible durable publication
        self.intents[row['reconnect_id']] = request
        e.partial.add(key)
        # Admission and the physical projection are separate locks. Recheck
        # AFTER holding the unsent gate, so a racing admitted request cannot
        # receive a close permit on the basis of an earlier zero projection.
        e._project_epoch(epoch)
        need(e._count(key) == count,
             'DYNTEAM_RECONNECT_NO_ADMISSION_RACE_BEFORE_DURABLE_PERMIT')
        e._receipt(epoch, 'NORMAL_RECONNECT_PREPARED_' + request,
                   reconnect_intent_sha256=request,
                   cumulative_reconnect_request_anchor=count,
                   old_session_durable=True, old_models_HTTP_tools_clear=True,
                   paid_census_extended=False, original_close_not_yet_called=True)
        e.partial.remove(key)
        return True

    def bound_new_epoch(self, key, epoch):
        """Only called AFTER the existing genuine new-CLI and session commit."""
        permit = self.pending.get(key)
        if permit is None:
            return None
        e, core = self.epochs, self.core
        self._owner()
        old = permit.old_epoch
        cli = core.bridge_owner.clis.get(key)
        session = e._session(key)
        need(key == (epoch.trajectory,epoch.role) and e.current.get(key) == epoch and
             key not in e.partial and key not in e.pending and
             old.child != epoch.child and old.ordinal + 1 == epoch.ordinal and
             old.token in core.bridge_owner.finished and not same_child_alive(old.child) and
             any(h.child == old.child and h.archived for h in e.history) and
             epoch.owner_birth == e.owner and epoch.contract_sha256 == e.sha and
             epoch.request_anchor == permit.request_anchor == e._count(key) and
             cli is not None and cli['birth'] == epoch.child and cli['token'] == epoch.token and
             cli['archived'] is False and same_child_alive(epoch.child) and
             type(session) is tuple and session[0] == permit.logical_birth and
             session != permit.old_session and (key, session[1]) in e.session_bound and
             process_birth(permit.peer_birth.pid) == permit.peer_birth,
             'DYNTEAM_RECONNECT_GENUINE_OLD_ARCHIVED_EXIT_NEW_CLI_AND_SID_BOUND')
        with core.peers._lock:
            peer = core.peers._peers.get((*key, 'router'))
        need(peer == permit.peer_birth, 'DYNTEAM_RECONNECT_SAME_ROUTER_THROUGH_NEW_BIND')
        e._project_epoch(epoch)
        e.partial.add(key)
        e._receipt(epoch, 'NORMAL_RECONNECT_BOUND_' + permit.request_sha256,
                   reconnect_intent_sha256=permit.request_sha256,
                   cumulative_reconnect_request_anchor=permit.request_anchor,
                   old_original_archived_END=True, original_new_CLI_epoch=True,
                   original_new_session_durable=True, paid_census_extended=False)
        self.completed.add(permit.request_sha256)
        del self.pending[key]
        e.partial.remove(key)
        return epoch
