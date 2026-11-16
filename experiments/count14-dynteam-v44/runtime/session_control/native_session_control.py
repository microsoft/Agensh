"""Bounded AF_UNIX ingress for our native router's control metadata ONLY.

No scientific payload, dispatcher, model transport or ledger writes. A trusted
owner supplies exact peer validation and an already-durable metadata receiver.
Receiver/peer code MUST use bounded locking and no I/O while holding scientific
locks. A receipt means native session registered, never SEARCH/model completion.
This module alone does not construct an experiment owner or authorize activation.
"""
from __future__ import annotations

import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import struct
import threading
from collections import deque
from dataclasses import dataclass
from native_control_inbox import ControlUnstartedExpired

COMMIT = "70e2ca54c078597e3314755064d2ef1a83344c8e"
FIELDS = {"schema", "source_commit", "trajectory_id", "block", "role_slot", "logical_birth_sha256",
          "native_turn_sha256", "native_session_uuid"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
ROLE = re.compile(r"(?:worker-(?:[0-2][0-9]|3[01])|checker-00|tester-00|racing-background-00|racing-player-0[0-6])\Z")


def checked(envelope):
    if not (type(envelope) is dict and set(envelope) == FIELDS and
            envelope["schema"] == "count14-dynteam-native-session-ready-v1" and
            envelope["source_commit"] == COMMIT and type(envelope["trajectory_id"]) is str and
            0 < len(envelope["trajectory_id"]) <= 512 and
            type(envelope["block"]) is int and envelope["block"] in (1, 2, 3) and
            type(envelope["role_slot"]) is str and ROLE.fullmatch(envelope["role_slot"]) and
            all(type(envelope[k]) is str and SHA.fullmatch(envelope[k])
                for k in ("logical_birth_sha256", "native_turn_sha256")) and
            type(envelope["native_session_uuid"]) is str and UUID.fullmatch(envelope["native_session_uuid"])):
        raise ValueError("DYNTEAM_EXACT_NATIVE_SESSION_CONTROL_FIELDS")
    return envelope


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False

    def handle_error(self, request, address):
        # A timed-out receipt peer may already be gone. Do not let socketserver
        # print an exception message/request representation/private stack.
        self.control_errors += 1

    def process_request(self, request, address):
        # A hung/slow owner metadata publisher cannot create unbounded receipt
        # threads. This is a CONTROL limit, not a model/agent limit.
        if not self.control_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.control_slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            return super().process_request_thread(request, address)
        finally:
            self.control_slots.release()


@dataclass
class SessionTicket:
    key: str
    envelope: dict
    peer: tuple
    complete: threading.Event
    accepted: bool | None = None


class NativeSessionInbox:
    """Existing owner publisher, finite fresh metadata receipts, no ACK cache."""
    def __init__(self, *, receipt_timeout=30, maximum_pending=128):
        from native_control_inbox import OwnerControlQueue
        self._queue=OwnerControlQueue(checked=checked,timeout=receipt_timeout,maximum=maximum_pending)
        self.timeout,self.maximum_pending=self._queue.timeout,self._queue.maximum
        self.lock,self.pending,self.tickets=self._queue.lock,self._queue.pending,self._queue.tickets

    @property
    def unresolved(self):
        with self.lock:return len(self.tickets)

    def receive(self,envelope,peer):
        return self._queue.receive(envelope,peer,report_unstarted_expiry=True) is True

    def drain(self,maximum=128):
        return self._queue.drain(maximum)

    def resolve(self,ticket,*,durable):
        if type(durable) is not bool:raise ValueError('DYNTEAM_CONTROL_DURABILITY_BOOLEAN')
        self._queue.resolve(ticket,durable)

    def public(self):
        return self._queue.public()


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # no raw route, body, SID, error message or inherited access log

    def handle(self):
        self.request.settimeout(3)
        return super().handle()

    def answer(self, status, row):
        raw = json.dumps(row, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def note_session_ready(self, ordinal, outcome):
        # Fixed PUBLIC observer only; never authorizes or changes a decision.
        try:
            with self.server.session_ready_observation_lock:
                value=self.server.session_ready_resubmission_counts
                if outcome=='REQUEST_RECEIVED':
                    value['authenticated_resubmissions']+=1
                    value['by_ordinal'][str(ordinal)]['requests']+=1
                    value['latest_result']='RESUBMISSION_WAITING'
                elif outcome=='UNSTARTED_NO_EFFECT':
                    value['negative_unstarted_no_effect_responses']+=1
                    if ordinal:
                        value['by_ordinal'][str(ordinal)]['unstarted']+=1
                    if ordinal==3:
                        value['exhausted_unstarted_outcomes']+=1
                        value['latest_result']='EXHAUSTED_UNSTARTED_RETAIN'
                    else:value['latest_result']='UNSTARTED_NO_EFFECT_AWAIT_RESUBMIT'
                elif ordinal and outcome in ('DURABLE_ACK_WRITTEN','RETAINED_NON_UNSTARTED'):
                    key='durable'if outcome=='DURABLE_ACK_WRITTEN'else'retained'
                    value['by_ordinal'][str(ordinal)][key]+=1
                    value['durable_ack_responses_after_resubmission'if key=='durable'else'retained_outcomes_after_resubmission']+=1
                    value['latest_result']=outcome
                value['latest_resubmission_ordinal']=ordinal
        except Exception:
            pass # Observer failure must not change the original ACK/refusal.

    def do_POST(self):
        resubmission_ordinal=0
        try:
            proof_route = self.path == "/native-phase-physical-proof"
            lifecycle_route = self.path == "/native-bridge-lifecycle"
            spawn_route = self.path == '/native-spawn-control'
            reconnect_route = self.path == '/native-session-reconnect'
            if self.path not in ("/native-session-ready", "/native-phase-physical-proof", "/native-bridge-lifecycle",'/native-spawn-control','/native-session-reconnect') or self.headers.get("Transfer-Encoding"):
                raise ValueError("DYNTEAM_NATIVE_CONTROL_ROUTE")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= 2048:
                raise ValueError("DYNTEAM_NATIVE_CONTROL_BODY_BOUND")
            raw = self.rfile.read(int(lengths[0]))
            if len(raw) != int(lengths[0]):
                raise ValueError("DYNTEAM_NATIVE_CONTROL_BODY_INCOMPLETE")
            if reconnect_route:
                from native_session_reconnect import checked as checked_reconnect
                envelope=checked_reconnect(json.loads(raw))
            elif spawn_route:
                from native_spawn_protocol import checked_spawn
                envelope=checked_spawn(json.loads(raw))
            elif lifecycle_route:
                from native_bridge_protocol import checked_lifecycle
                envelope = checked_lifecycle(json.loads(raw))
            elif proof_route:
                from native_phase_proof import checked_proof
                envelope = checked_proof(json.loads(raw))
            else:
                envelope = checked(json.loads(raw))
            peer = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            # Exact (trajectory,role,pid/start/boot/uid) validator is provided by
            # the original owner/launcher custody graph, never by the sender.
            if self.server.peer_validator(envelope, peer) is not True:
                raise ValueError("DYNTEAM_NATIVE_CONTROL_PEER_REFUSED")
            if self.path=='/native-session-ready':
                # Frozen sender uses this ordinal for observation only. The
                # original checked envelope/raw binding and all peer/kernel/
                # physical/affinity decisions remain the sole authority.
                ordinal=self.headers.get('X-Count14-Control-Resubmission','0')
                if ordinal in ('1','2','3'):
                    resubmission_ordinal=int(ordinal)
                    self.note_session_ready(resubmission_ordinal,'REQUEST_RECEIVED')
            if reconnect_route:
                if not callable(self.server.reconnect_receiver) or self.server.reconnect_receiver(envelope,peer) is not True:
                    raise ValueError('DYNTEAM_RECONNECT_NO_DURABLE_ORIGINAL_PREFLIGHT')
                self.answer(200,dict(schema='count14-native-normal-session-reconnect-ack-v1',
                    binding_sha256=hashlib.sha256(raw).hexdigest(),accepted=True))
                return
            if spawn_route:
                if not callable(self.server.spawn_receiver):raise ValueError('DYNTEAM_NATIVE_SPAWN_NOT_BOUND')
                result=self.server.spawn_receiver(envelope,peer)
                if not(type(result) is dict and set(result)=={'status','active_seconds','operation_id'} and
                       result['status'] in ('RUNNING','HOLD','FINAL','ALLOW','RETAINED','DONE') and
                       type(result['active_seconds']) is int and result['active_seconds']>=0 and
                       type(result['operation_id']) is str and len(result['operation_id'])==32):
                    raise ValueError('DYNTEAM_NATIVE_SPAWN_RESULT_REQUIRED')
                self.answer(200,dict(schema='count14-native-spawn-control-ack-v1',
                    binding_sha256=hashlib.sha256(raw).hexdigest(),**result))
                return
            if lifecycle_route:
                if not callable(self.server.lifecycle_receiver):
                    raise ValueError("DYNTEAM_NATIVE_BRIDGE_LIFECYCLE_NOT_BOUND")
                allow = self.server.lifecycle_receiver(envelope, peer)
                if type(allow) is not bool:
                    raise ValueError("DYNTEAM_NATIVE_BRIDGE_LIFECYCLE_UNPROVEN")
                self.answer(200, {"schema": "count14-native-bridge-lifecycle-ack-v1",
                                  "binding_sha256": hashlib.sha256(raw).hexdigest(), "allow": allow})
                return
            if proof_route:
                if not callable(self.server.phase_proof_receiver):
                    raise ValueError("DYNTEAM_RACING_NATIVE_PHASE_PROOF_NOT_BOUND")
                proof = self.server.phase_proof_receiver(envelope, peer)
                if not (type(proof) is dict and set(proof) == {"models_clear", "tools_clear"} and
                        all(type(v) is bool for v in proof.values())):
                    raise ValueError("DYNTEAM_RACING_NATIVE_PHASE_PROOF_UNPROVEN")
                self.answer(200, {"schema": "count14-native-phase-physical-proof-ack-v1",
                                  "binding_sha256": hashlib.sha256(raw).hexdigest(), **proof})
                return
            if self.server.receiver(envelope, peer) is not True:
                raise ValueError("DYNTEAM_NATIVE_CONTROL_METADATA_NOT_DURABLE")
            self.answer(200, {"schema": "count14-dynteam-native-session-ack-v1", "accepted": True,
                              "binding_sha256": hashlib.sha256(raw).hexdigest()})
            if resubmission_ordinal:self.note_session_ready(resubmission_ordinal,'DURABLE_ACK_WRITTEN')
        except Exception as error:
            # Preserve only fixed original control refusal metadata. A missing
            # observer never changes the original 503 or admission decision.
            try:
                code = str(error)
                path = self.path if self.path in (
                    '/native-session-ready', '/native-phase-physical-proof',
                    '/native-bridge-lifecycle', '/native-spawn-control',
                    '/native-session-reconnect') else 'OTHER'
                self.server.last_refusals.append(dict(route=path,
                    exception_type=type(error).__name__,
                    fixed_guard_code=code if re.fullmatch(r'DYNTEAM_[A-Z0-9_]{1,240}', code) else None))
                self.server.last_refusals = self.server.last_refusals[-128:]
            except Exception:
                pass
            if self.path=='/native-session-ready' and type(error) is ControlUnstartedExpired:
                # Exact authenticated/checked ticket was removed BEFORE any
                # owner callback. Not a grant, not proof of models/tools clear.
                self.answer(503, {'PUBLIC_code':'DYNTEAM_SESSION_READY_UNSTARTED_EXPIRED_NO_EFFECT',
                                  'unstarted_no_effect':True})
                self.note_session_ready(resubmission_ordinal,'UNSTARTED_NO_EFFECT')
                return
            if resubmission_ordinal:self.note_session_ready(resubmission_ordinal,'RETAINED_NON_UNSTARTED')
            self.answer(503, {"status": "DYNTEAM_NATIVE_CONTROL_REFUSED_RETAIN_NO_PROMPT",
                              "exception_type": type(error).__name__})


class NativeSessionControl:
    def __init__(self, path, *, peer_validator, receiver, phase_proof_receiver=None,
                 socket_uid=None, socket_gid=None, lifecycle_receiver=None, spawn_receiver=None,
                 reconnect_receiver=None):
        self.path = Path(path)
        if (not self.path.is_absolute() or self.path.parent.resolve() != self.path.parent or
                self.path.exists() or self.path.is_symlink() or
                not callable(peer_validator) or not callable(receiver)):
            raise ValueError("DYNTEAM_NEW_EXACT_CONTROL_SOCKET")
        self.server = _Server(str(self.path), _Handler)
        self.server.control_slots = threading.BoundedSemaphore(16)
        self.server.control_errors = 0
        self.server.last_refusals = []
        self.server.session_ready_observation_lock=threading.Lock()
        self.server.session_ready_resubmission_counts=dict(
            schema='count14-native-session-ready-proven-unstarted-resubmission-public-v1',
            maximum_resubmissions_per_original_registration=3,
            authenticated_resubmissions=0,negative_unstarted_no_effect_responses=0,
            durable_ack_responses_after_resubmission=0,retained_outcomes_after_resubmission=0,
            exhausted_unstarted_outcomes=0,latest_result='NOT_OBSERVED',latest_resubmission_ordinal=0,
            by_ordinal={str(i):dict(requests=0,unstarted=0,durable=0,retained=0)for i in(1,2,3)},
            counts_are_authenticated_observations_not_authority=True,
            not_model_or_physical_terminal_proof=True)
        uid = os.geteuid() if socket_uid is None else socket_uid
        gid = os.getegid() if socket_gid is None else socket_gid
        if not (type(uid) is int and uid >= 0 and type(gid) is int and gid >= 0):
            self.server.server_close()
            raise ValueError("DYNTEAM_NEW_SOCKET_EXACT_NATIVE_OWNER")
        # Only the fresh own socket inode, before exposure; never chmod a host
        # directory/daemon or elevate native UID. Peer PID/start/ns still bind
        # each role even if native containers share an unprivileged UID.
        os.chown(self.path, uid, gid)
        os.chmod(self.path, 0o600)
        self.server.peer_validator = peer_validator
        self.server.receiver = receiver
        self.server.phase_proof_receiver = phase_proof_receiver
        self.server.lifecycle_receiver = lifecycle_receiver
        self.server.spawn_receiver = spawn_receiver
        self.server.reconnect_receiver = reconnect_receiver
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.05}, daemon=True,
                                       name="count14-dynteam-own-native-session-control")
        self.started = False

    def public_session_ready_resubmissions(self):
        from copy import deepcopy
        with self.server.session_ready_observation_lock:
            return deepcopy(self.server.session_ready_resubmission_counts)

    def start(self):
        if self.started:
            raise ValueError("DYNTEAM_CONTROL_START_ONCE")
        self.started = True
        self.thread.start()

    def close(self):
        if self.started:
            self.server.shutdown()
            self.thread.join(timeout=3)
            if self.thread.is_alive():
                raise ValueError("DYNTEAM_CONTROL_NORMAL_STOP_TIMEOUT_RETAIN")
        self.server.server_close()
        # Keep the socket inode as evidence. No unlink/delete/rebind is done.
