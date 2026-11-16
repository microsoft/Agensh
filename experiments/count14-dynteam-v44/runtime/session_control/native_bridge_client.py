"""Cold native bridge hooks. No model transport/replay or data deletion.

Each metadata HTTP probe is bounded. Native custodial wait is outside locks;
existing paid work continues naturally. SIGTERM is the ONLY signal generated.
Only local child PID/start/boot is examined; no stack, argv or process scan.
"""
from pathlib import Path
import hashlib
import http.client
import json
import os
import signal
import socket
import subprocess
import threading
import time

from native_bridge_protocol import BASE, checked_lifecycle


def _digest(row):
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _start(pid):
    raw = Path('/proc', str(pid), 'stat').read_bytes()
    return int(raw[raw.rfind(b')') + 2:].split()[19])


class _Unix(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__('localhost', timeout=32)
        self.path = str(path)
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(32)
        self.sock.connect(self.path)


class BridgeLifecycle:
    def __init__(self, route):
        if not (type(route) is dict and route.get('source_commit') == BASE and
                route.get('schema') == 'count14-dynteam-router-cold-route-v1' and
                route.get('mode') in ('production', 'smoke', 'own-zero')):
            raise ValueError('DYNTEAM_NATIVE_BRIDGE_FROZEN_ROUTE')
        self.route = dict(route)
        self.lock = threading.Lock()
        self.children = {}
        self.current = None

    @classmethod
    def from_environment(cls):
        path = Path(os.environ.get('COUNT14_NATIVE_ROUTE', '/run/count14-dynteam/route.json'))
        if path.resolve() != path or path.is_symlink():
            raise ValueError('DYNTEAM_NATIVE_BRIDGE_ROUTE_CANONICAL')
        if path.stat().st_size > 32768:
            raise ValueError('DYNTEAM_NATIVE_BRIDGE_ROUTE_BOUND')
        return cls(json.loads(path.read_bytes()))

    def ready(self, stopping=None):
        # Authenticated control-peer registration only, before any CLI. This
        # does NOT claim BIRTH, archive, tool clear, model/session readiness or
        # an empty baseline. Original SO_PEERCRED/Docker/namespace checks apply.
        row=self._row('BRIDGE_READY',None,None,None)
        while stopping is None or not stopping.is_set():
            if self.request(row):return True
            time.sleep(.1)
        return False

    def request(self, row):
        checked_lifecycle(row)
        raw = json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode()
        connection = _Unix(self.route['control_socket'])
        try:
            connection.request('POST', '/native-bridge-lifecycle', body=raw, headers={'Content-Type':'application/json'})
            response = connection.getresponse(); body = response.read(2049)
            if response.status != 200 or len(body) > 2048:
                return False
            value = json.loads(body)
            return (value.get('schema') == 'count14-native-bridge-lifecycle-ack-v1' and
                    value.get('binding_sha256') == hashlib.sha256(raw).hexdigest() and value.get('allow') is True)
        except Exception:
            return False  # no raw exception/message or private file path output
        finally:
            connection.close()

    def _row(self, event, proc, identity, turn, *, archive=False, reason='NONE'):
        names = {'retire':'RETIRE', 'terminated':'TERMINATED', 'shutdown':'SHUTDOWN', 'disconnect':'DISCONNECT',
                 'tester_release':'TESTER_RELEASE', 'startup_recovery':'STARTUP_RECOVERY', 'NONE':'NONE'}
        with self.lock:
            context = self.children.get(proc.pid) if proc is not None else self.current
        if context is None:
            context = dict(pid=0, start=0, account='STARTUP', turn='STARTUP')
        if identity is not None:
            context = {**context, 'account':identity['username']}
        if turn is not None:
            context = {**context, 'turn':turn.name}
        t, role = self.route['trajectory_id'], self.route['role_slot']
        return dict(schema='count14-native-bridge-lifecycle-v1', source_commit=BASE, trajectory_id=t, role_slot=role,
            logical_birth_sha256=_digest([BASE,t,role,context['account']]),
            native_turn_sha256=_digest([BASE,t,role,context['turn']]), event=event,
            child_namespace_pid=context['pid'], child_start_ticks=context['start'],
            child_running=proc is not None and proc.poll() is None, archive_durable=archive,
            end_kind=names.get(reason,'OTHER'))

    def wait(self, event, proc=None, identity=None, turn=None, *, archive=False, reason='NONE'):
        # All science/stop/input locks belong to original code. Hook sites MUST
        # call before acquiring them; repeated READ/ACK probes are not models.
        while not self.request(self._row(event, proc, identity, turn, archive=archive, reason=reason)):
            time.sleep(0.1)

    def born(self, proc, identity, turn):
        if proc is None or identity is None or turn is None:
            raise ValueError('DYNTEAM_NATIVE_BRIDGE_TRACKED_TEAM_CHILD_REQUIRED')
        context = dict(pid=proc.pid, start=_start(proc.pid), account=identity['username'], turn=turn.name,
                       boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        with self.lock:
            self.children[proc.pid] = context
            self.current = context
        self.wait('CLI_BIRTH', proc, identity, turn)

    def before_end(self, proc):
        self.wait('END_REQUEST', proc)

    def stop_normal(self, proc):
        if proc is None:
            return  # no global UID scan, no unrelated process/signal action
        self.before_end(proc)
        if proc.poll() is None:
            with self.lock:
                context = dict(self.children[proc.pid])
            if _start(proc.pid) != context['start'] or Path('/proc/sys/kernel/random/boot_id').read_text().strip() != context['boot']:
                raise ValueError('DYNTEAM_NATIVE_CHILD_BIRTH_CHANGED_NO_SIGNAL')
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            raise RuntimeError('DYNTEAM_NATIVE_CHILD_NORMAL_TERM_TIMEOUT_RETAIN_NO_KILL') from None
        self.wait('CHILD_EXIT', proc)

    def before_cleanup(self, turn, reason):
        self.wait('BEFORE_CLEANUP', turn=turn, archive=True, reason=reason)

    def archived(self, proc, identity, turn, reason):
        self.wait('ARCHIVED_END', proc, identity, turn, archive=True, reason=reason)

    def preserve_startup(self, state, recovery):
        # Native startup recovery otherwise clears HOME/workspace before a paid
        # SDK/session restoration can run. Keep every byte instead: original
        # archive producer, no cleanup, no historical ledger/PKL access/reset.
        from archive import save
        if state.active != recovery:
            raise ValueError('DYNTEAM_NATIVE_STARTUP_EXACT_NEW_LOCAL_ARCHIVE_OWNER')
        save(recovery,state.home,state.workspace)
        state._manifest(recovery,status='complete',startup_contents_preserved=True)
        state.active=None  # only this new process's just-created startup turn


_INSTANCE = None
def bridge_lifecycle():
    # One original bridge main thread constructs before TurnState import/use.
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = BridgeLifecycle.from_environment()
    return _INSTANCE
