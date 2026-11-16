"""Private scientific IPC -> actual native ACP phase port, no model client.

One request, no retry. Connect/write is bounded before native admission; after
the complete request is written there is deliberately no deadline abort. The
original Game quorum can leave the future busy until natural completion.
No prompts/model data/tokens/errors are printed or exported as PUBLIC metadata.
"""
from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import socket
import stat
import threading
import uuid

from racing_native_binding import CompletedNativeTurn, NativePhaseUnadmitted


class _UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=3)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(3)
        # Formal scratch roots are longer than sockaddr_un.sun_path. Open the
        # exact role directory, then use its short same-process FD alias. This
        # is NOT a symlink shortcut to a different root/socket or a new relay.
        path=Path(self.path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:self.sock.connect('/proc/self/fd/'+str(fd)+'/'+path.name)
        finally:os.close(fd)


class NativeRacingPhaseClient:
    def __init__(self, *, routes, native_secret_owner_uid=None):
        if native_secret_owner_uid is not None and not (
                type(native_secret_owner_uid) is int and native_secret_owner_uid>=0 and
                (native_secret_owner_uid==os.geteuid() or os.geteuid()==0 and native_secret_owner_uid==10000)):
            raise ValueError('DYNTEAM_TRUSTED_NATIVE_SECRET_OWNER_UID')
        secret_owners={0,os.geteuid()}
        if native_secret_owner_uid is not None:secret_owners.add(native_secret_owner_uid)
        if not (type(routes) is dict and routes and all(type(role) is str and
                (role == "racing-background-00" or role in {f"racing-player-{i:02d}" for i in range(7)})
                for role in routes)):
            raise ValueError("DYNTEAM_RACING_PRIVATE_NATIVE_ROLE_ROUTES")
        # Only zero-model preparation is serialized. The lock is released
        # before the original paid phase request; original m7 model calls,
        # quorum, verdicts and physical draining remain concurrent/unchanged.
        self._native_zero_preparation = threading.Lock()
        self.routes = {}
        self._first_background_result = None
        for role, row in routes.items():
            if type(row) is not dict or set(row) != {"socket", "secret"}:
                raise ValueError("DYNTEAM_RACING_PRIVATE_NATIVE_ROUTE_FIELDS")
            path, secret = Path(row["socket"]), Path(row["secret"])
            if not (path.is_absolute() and path.parent.resolve() == path.parent and
                    secret.is_absolute() and secret.parent.resolve() == secret.parent):
                raise ValueError("DYNTEAM_RACING_PRIVATE_NATIVE_ROUTE_CANONICAL")
            fd = os.open(secret, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                s = os.fstat(fd)
                if not (stat.S_ISREG(s.st_mode) and not s.st_mode & 0o077 and
                        s.st_uid in secret_owners and 32 <= s.st_size <= 513):
                    raise ValueError("DYNTEAM_RACING_PRIVATE_NATIVE_SECRET_SCOPE")
                token = os.read(fd, 514).decode().strip()
            finally:
                os.close(fd)
            if not 32 <= len(token) <= 512 or any(c in token for c in "\r\n\0"):
                raise ValueError("DYNTEAM_RACING_PRIVATE_NATIVE_SECRET_FORMAT")
            self.routes[role] = (path, token)

    def __call__(self, role, content, phase):
        if role not in self.routes or phase not in ("background", "submit", "review", "defend", "prepare-zero-model", "setup-completion"):
            raise ValueError("DYNTEAM_RACING_PRIVATE_NATIVE_ROLE_PHASE")
        path, token = self.routes[role]
        request = dict(schema="count14-private-native-racing-phase-v1", role=role,phase=phase,parts=content)
        anchor = self._first_background_result
        if phase == "setup-completion":
            if not (role == "racing-background-00" and type(anchor) is CompletedNativeTurn and
                    anchor.stop_reason == "end_turn" and anchor.original_relay_receipts_complete is True and
                    anchor.physical_terminal is True and type(anchor.native_session_uuid) is str and
                    type(anchor.native_turn_id) is str and 0 < len(anchor.native_turn_id) <= 256):
                raise RuntimeError("RACING_SETUP_COMPLETION_EXACT_ORIGINAL_FIRST_BACKGROUND_ANCHOR")
            request["setup_resume"] = dict(session=anchor.native_session_uuid,turn=anchor.native_turn_id)
        raw = json.dumps(request, ensure_ascii=False).encode()
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError("DYNTEAM_RACING_PRIVATE_NATIVE_REQUEST_BOUND")
        if phase not in ('prepare-zero-model','setup-completion'):
            with self._native_zero_preparation:
                self.prepare_zero_model(role)
        connection = _UnixHTTP(path)
        try:
            connection.request("POST", "/native-racing-phase", body=raw,
                               headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            # Connect/write retain their original finite bound. Once this
            # one request is completely written, retain its original Future
            # through the original SDK handshake/physical-proof terminal.
            # The zero-model handshake may take longer than IPC connect;
            # do not drop its response or create another native turn.
            # Paid phases remain unbounded and are never cancelled/replayed.
            # No scientific/ledger lock is held during this private wait.
            connection.sock.settimeout(None)
            response = connection.getresponse()
            if response.status != 200:
                control = response.read(2049)
                if len(control) <= 2048:
                    try:
                        code = json.loads(control).get('PUBLIC_code')
                    except (ValueError, AttributeError):
                        code = None
                    if code == 'DYNTEAM_RACING_NATIVE_PHASE_HELD_UNADMITTED':
                        raise NativePhaseUnadmitted('DYNTEAM_RACING_NATIVE_PHASE_HELD_UNADMITTED')
                raise RuntimeError("DYNTEAM_RACING_NATIVE_PHASE_UNPROVEN_NO_REPLAY")
            body = response.read(10 * 1024 * 1024 + 1)
            if len(body) > 10 * 1024 * 1024:
                raise RuntimeError("DYNTEAM_RACING_NATIVE_PHASE_RESPONSE_BOUND_RETAIN")
            result = json.loads(body)
            if phase == 'prepare-zero-model' and result.get('ZERO_MODEL_NATIVE_SESSION_PREPARED') is not True:
                raise RuntimeError('DYNTEAM_RACING_ZERO_MODEL_PREPARE_EXACT_NATIVE_RECEIPT')
            sid = result["native_session_uuid"]
            if not (str(uuid.UUID(sid)) == sid and result["fresh_stateless_session"] is (phase != "setup-completion") and
                    type(result["text"]) is str and type(result.get("thinking", "")) is str and
                    result["original_relay_receipts_complete"] is True and result["physical_terminal"] is True):
                raise RuntimeError("DYNTEAM_RACING_NATIVE_PHASE_TYPED_RESULT_UNPROVEN")
            # Preserve only the existing ACP fixed control enum. No new call/retry.
            reason = result.get("stop_reason")
            allowed = ("end_turn", "max_tokens", "max_turn_requests", "refusal", "cancelled")
            reason = (reason if type(reason) is str and reason in allowed else
                      "UNAVAILABLE" if reason is None else "OTHER")
            turn = result.get("native_turn_id")
            if turn is not None and not (type(turn) is str and 0 < len(turn) <= 256):
                raise RuntimeError("RACING_SETUP_COMPLETION_BOUNDED_ORIGINAL_TURN_ID")
            if phase == "setup-completion" and not (result.get("setup_same_session_turn") is True and
                    (sid,turn) == (anchor.native_session_uuid,anchor.native_turn_id)):
                raise RuntimeError("RACING_SETUP_COMPLETION_NO_FRESH_OR_REPLACEMENT_SESSION")
            completed = CompletedNativeTurn(result["text"], True, True,
                result.get("thinking", ""), reason, sid, turn)
            if phase == "background" and self._first_background_result is None:
                self._first_background_result = completed
            return completed
        except NativePhaseUnadmitted:
            raise
        except Exception:
            raise RuntimeError("DYNTEAM_RACING_PRIVATE_NATIVE_PHASE_FAILED_RETAIN_NO_REPLAY") from None
        finally:
            connection.close()

    def prepare_zero_model(self, role):
        # Same actual private entry and original native handshake, no prompt.
        result = self(role, [], 'prepare-zero-model')
        if result.text or result.thinking:
            raise RuntimeError('DYNTEAM_RACING_ZERO_MODEL_PREPARE_UNEXPECTED_SCIENTIFIC_OUTPUT')
        return {'ZERO_MODEL_NATIVE_SESSION_PREPARED': True, 'model_prompt_sent': False}
