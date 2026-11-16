"""Same-owner original HTTP transport retirement, NOT whole-cold recovery.

No core/engine/queue/FINAL close, model cancellation, financial mutation,
request reconstruction, old archive/control/SID edit or production opcode.
"""
from dataclasses import asdict
from pathlib import Path
import copy
import hashlib
import json
import os
import re
import stat
import threading
import time


class TransportWait(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(ok, code):
    if not ok:
        raise TransportWait(code)


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(wire(value)).hexdigest()


def outside_science(ledger):
    need(not ledger.mutex._is_owned(), 'NORMAL_TRANSPORT_NO_OUTER_SCIENCE_LOCK')


def capture_unsent_http(server):
    """Fixed framework-control projection only. Never read a payload/body."""
    from native_scientific_http import NativeScientificHttpServer
    from admission_gate import AdmissionGate
    need(type(server) is NativeScientificHttpServer and type(server.gate) is AdmissionGate,
         'NORMAL_TRANSPORT_EXACT_ORIGINAL_HTTP_AND_GATE')
    outside_science(server.ledger)
    server.current()
    need(not server.lifecycle_storage_unknown and not server.listener_stopped,
         'NORMAL_TRANSPORT_ORIGINAL_LIVE_KNOWN_LISTENER')
    trajectories = sorted({t for t, _ in server.registered})
    for t in trajectories:
        need(server.trajectory_park_ready(t)['safe_to_park_writers'],
             'NORMAL_TRANSPORT_ORIGINAL_HTTP_SAFE_WITH_NO_DELIVERIES')
    with server.registry_lock:
        requests = tuple(server.requests.values())
        accepted = set(server.accepted_sockets)
        need(not server.retained, 'NORMAL_TRANSPORT_NO_RETAINED_HTTP_UNKNOWN')
    need(accepted == {id(r.connection) for r in requests},
         'NORMAL_TRANSPORT_NO_UNATTRIBUTED_ACCEPTED_CONNECTION')
    rows = []
    for request in requests:
        status = request.status()
        need(status['finished'] is False and status['delivery_unknown'] is False
             and status['failure_metadata_unknown'] is False
             and status['request_id'] is not None,
             'NORMAL_TRANSPORT_ONLY_EXACT_BOUND_UNSENT_HTTP_HANDLES')
        rid, identity = status['request_id'], request.identity
        with server.ledger.mutex:
            need(server.ledger.db.execute('SELECT state FROM requests WHERE id=?', (rid,)).fetchone() is None,
                 'NORMAL_TRANSPORT_UNSENT_HAS_NO_ORIGINAL_MODEL_REQUEST_ROW')
            pause = server.gate.budget_pause(*identity)
            need(pause['paused'] is True and pause['request_id'] == rid
                 and server.gate.waiters.get(identity) == rid,
                 'NORMAL_TRANSPORT_ORIGINAL_BUDGET_WAITER_EXACT_RID')
        states = server.engine.continuations
        with states.lock:
            saved = states.db.execute('SELECT id,generation FROM parked WHERE id=?', (rid,)).fetchone()
        need(saved is not None and tuple(saved) == (rid, None),
             'NORMAL_TRANSPORT_ORIGINAL_UNSENT_CONTROL_RETAINED_NO_BODY_READ')
        rows.append(dict(handle=status['handle'], trajectory=identity[0], role=identity[1],
            request_id=rid, generation=pause['generation'], continuation_generation=None))
    with server.registry_lock:
        need(tuple(server.requests.values()) == requests
             and set(server.accepted_sockets) == accepted and not server.retained,
             'NORMAL_TRANSPORT_HTTP_CONTROL_SNAPSHOT_STILL_SAME')
    return dict(listener_identity_sha256=server.listener_identity_sha256,
                waiters=sorted(rows, key=lambda row: (row['trajectory'], row['role'], row['request_id'])))


def shutdown_original_unsent_gate(gate, servers, expected):
    """Actual API stage; caller still needs real whole-barrier/paid preflight."""
    from admission_gate import AdmissionGate
    need(type(gate) is AdmissionGate and not gate.closed and len(servers) == len(expected),
         'NORMAL_TRANSPORT_ONLY_CURRENT_OPEN_ORIGINAL_GATE')
    outside_science(gate.ledger)
    need(gate.shutdown.__func__ is AdmissionGate.shutdown,
         'NORMAL_TRANSPORT_UNMODIFIED_ORIGINAL_GATE_SHUTDOWN_METHOD')
    actual = [capture_unsent_http(server) for server in servers]
    need(actual == list(expected) and all(server.gate is gate for server in servers),
         'NORMAL_TRANSPORT_FRESH_SAME_GATE_AND_UNSENT_CONTROL_SET')
    declared = {(r['trajectory'], r['role']): r['request_id'] for v in actual for r in v['waiters']}
    need(sum(len(v['waiters']) for v in actual) == len(declared),
         'NORMAL_TRANSPORT_UNIQUE_ORIGINAL_HTTP_WAITER_IDENTITIES')
    with gate.condition:
        need(dict(gate.waiters) == declared,
             'NORMAL_TRANSPORT_NO_NON_HTTP_OR_UNCAPTURED_GATE_WAITER')
    # No lock held across this API, no SENT cancellation or model close.
    gate.shutdown()
    return sum(len(v['waiters']) for v in actual)


def http_handlers_clear(server):
    outside_science(server.ledger)
    server.current()
    need(not server.lifecycle_storage_unknown, 'NORMAL_TRANSPORT_HTTP_LIFECYCLE_UNKNOWN_RETAIN')
    with server.registry_lock:
        return not server.requests and not server.accepted_sockets and not server.retained


def stop_original_listener(server):
    from native_scientific_http import NativeScientificHttpServer
    outside_science(server.ledger)
    need(http_handlers_clear(server) and server.started and not server.listener_stopped
         and server.serving.is_set() and not server.loop_finished.is_set()
         and server.thread is not None and server.thread.is_alive()
         and server.stop_listener.__func__ is NativeScientificHttpServer.stop_listener,
         'NORMAL_TRANSPORT_TRUE_ORIGINAL_SERVING_LOOP_NO_HANDLERS_BEFORE_STOP')
    server.stop_listener()  # original stdlib shutdown/join, outside science locks
    need(server.listener_stopped and server.loop_finished.is_set() and not server.thread.is_alive(),
         'NORMAL_TRANSPORT_ORIGINAL_LISTENER_PHYSICAL_STOP_REQUIRED')


def original_handler_threads_clear(server):
    from socketserver import _Threads, _NoThreads
    threads = server._threads
    if type(threads) is _NoThreads:
        return True  # exact original never-created-handler sentinel
    need(type(threads) is _Threads, 'NORMAL_TRANSPORT_ORIGINAL_HANDLER_THREAD_REGISTRY')
    return not any(t.is_alive() for t in tuple(threads))


class NormalTransportRetirement:
    def __init__(self, barrier):
        from normal_cold_barrier import NormalCheckpointBarrier
        from native_v2_dispositions import NativeV2Dispositions
        need(type(barrier) is NormalCheckpointBarrier and not barrier.requested
             and not barrier.cohort.activation_attempted and barrier.cohort.final is None
             and not hasattr(barrier.core, 'normal_transport_retirement'),
             'NORMAL_TRANSPORT_INSTALL_ONLY_AFTER_FIRST_COLD_BARRIER_BEFORE_ACTIVATION')
        barrier._current()
        core = barrier.core
        need(type(core.v2_dispositions) is NativeV2Dispositions
             and core.v2_dispositions.ledger is core.ledger,
             'NORMAL_TRANSPORT_EXACT_CURRENT_ORIGINAL_MODERN_V2_PROJECTION')
        self.barrier, self.core, self.cohort, self.owner = barrier, core, barrier.cohort, barrier.owner
        self.pid, self.thread = os.getpid(), threading.get_ident()
        self.birth = barrier.birth
        self.gate = core.gate
        self.servers = tuple(core.servers[t] for t in sorted(core.rows))
        need(len(self.servers) == len(set(map(id, self.servers))) == 6,
             'NORMAL_TRANSPORT_SIX_EXACT_ORIGINAL_HTTP_CUSTODIANS')
        self.close_methods = {id(s): s.close_after_drained for s in self.servers}
        self.requested = self.gate_shutdown_done = False
        self.stopped, self.closed = set(), set()
        self.state, self.wait_code, self.failure = 'COLD_INSTALLED_NOT_REQUESTED', None, None
        self.protected_control, self.retained_unsent = None, None
        self.stop_elapsed = {}
        core.normal_transport_retirement = self.owner.normal_transport_retirement = self

    def _current(self):
        self.barrier._current()
        need(os.getpid() == self.pid and threading.get_ident() == self.thread
             and self.barrier.birth == self.birth and self.owner.normal_transport_retirement is self
             and self.core.normal_transport_retirement is self and self.core.gate is self.gate
             and tuple(self.core.servers[t] for t in sorted(self.core.rows)) == self.servers,
             'NORMAL_TRANSPORT_SAME_ORIGINAL_OWNER_THREAD_AND_OBJECTS')
        self.barrier.domain._outside_locks()

    def _preflight(self):
        self._current()
        view = self.barrier.poll()
        need(view['requested'] and view['observed_six_original_frozen_cut_stability'] is True
             and len(view['tracks']) == 6,
             'NORMAL_TRANSPORT_WAIT_TRUE_SIX_FROZEN_ORIGINAL_BARRIER')
        disposition = self.core.v2_dispositions
        need(disposition.ledger is self.core.ledger and disposition.search_count() == 0
             and self.core.ledger.global_unresolved() == 0,
             'NORMAL_TRANSPORT_WAIT_CURRENT_ORIGINAL_V2_PHYSICAL_ZERO')
        with self.core.ledger.mutex:
            need(self.core.ledger.db.execute(
                "SELECT COUNT(*) FROM aux_permits WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0] == 0,
                'NORMAL_TRANSPORT_WAIT_NO_ACTIVE_OR_UNKNOWN_AUX_API_CUSTODY')
        final = self.cohort.final
        need(final is not None and final is self.barrier.final_record[0]
             and final.dispatcher is self.barrier.final_record[2],
             'NORMAL_TRANSPORT_SAME_RETAINED_FINAL_AND_ORIGINAL_DISPATCHER')
        for record in final.dispatcher.children.values():
            child, terminal = record['child'], record['terminal']
            need(child is not None and child.returncode is not None and terminal is not None
                 and terminal.get('wait_observed') is True,
                 'NORMAL_TRANSPORT_WAIT_EVERY_PAID_FINAL_CHILD_REAL_ORIGINAL_WAIT')
        rows = self.barrier.approved.all_rows(self.core.queue)
        need(not any(r['state'] in ('CLAIMED','RUNNING','CHILD_EXITED_HOLD','CUSTODY_UNKNOWN') for r in rows),
             'NORMAL_TRANSPORT_WAIT_CURRENT_ALL_APPROVED_FINAL_CUSTODY_TERMINAL')
        return view

    def _preserve_control(self, views):
        """New append-only framework metadata; old continuation/archive untouched."""
        parent = self.core.home
        s = parent.lstat()
        need(parent.resolve() == parent and not parent.is_symlink() and stat.S_ISDIR(s.st_mode)
             and s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == 0o700,
             'NORMAL_TRANSPORT_ORIGINAL_PRIVATE_OWNER_CONTROL_HOME')
        directory = parent/'normal-transport-retirement-control-v1'
        directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        value = dict(schema='count14-normal-transport-original-unsent-control-v1',
            owner=asdict(self.birth), contract_sha256=self.barrier.source_binding, HTTP=views,
            original_request_row_absent=True, original_continuations_retained=True,
            payloads_read_or_reconstructed=False, original_archives_or_control_or_SID_edited=False,
            normal_SDK_resume_qualified=False, whole_cold_ready=False)
        raw = wire(value)
        path = directory/'ORIGINAL_UNSENT_CONTROL.json'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        with os.fdopen(fd, 'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(dfd)
        finally: os.close(dfd)
        self.retained_unsent = tuple(copy.deepcopy(views))
        self.protected_control = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                                      waiters=sum(len(v['waiters']) for v in views))

    def request(self):
        self._current()
        need(not self.requested, 'NORMAL_TRANSPORT_REQUEST_ONCE_RETAIN_NO_REPLAY')
        self.requested = True
        self.state = 'WAIT_REAL_BARRIER_FINAL_AND_HTTP_PREFLIGHT'
        return self.public()

    def poll(self):
        self._current()
        if not self.requested or self.failure is not None or self.state in (
            'OLD_HTTP_TRANSPORTS_RETIRED_NO_SDK_CLAIM', 'WAIT_ORIGINAL_CLOSE_GUARD_RETAINED_NO_RETRY'):
            return self.public()
        try:
            self._preflight()  # keep SYSTEM/resource/FINAL originals alive until paid clear
            self.wait_code = None
            if not self.gate_shutdown_done:
                views = [capture_unsent_http(s) for s in self.servers]
                if self.protected_control is None:
                    self._preserve_control(views)
                else:
                    need(tuple(views) == self.retained_unsent,
                         'NORMAL_TRANSPORT_PREPARED_UNSENT_CONTROL_CHANGED_RETAIN_NO_REWRITE')
                shutdown_original_unsent_gate(self.gate, self.servers, views)
                self.gate_shutdown_done = True
                self.state = 'WAIT_ORIGINAL_UNSENT_HANDLERS_NATURAL_TERMINAL'
                return self.public()
            for server in self.servers:
                if id(server) not in self.closed and not http_handlers_clear(server):
                    self.wait_code = 'NORMAL_TRANSPORT_WAIT_ORIGINAL_HANDLER_OR_ACCEPTED_SOCKET'
                    return self.public()
            for server in self.servers:
                if id(server) not in self.stopped:
                    start = time.monotonic()
                    stop_original_listener(server)
                    self.stop_elapsed[server.listener_identity_sha256] = time.monotonic()-start
                    self.stopped.add(id(server))
                    self.state = 'STOPPING_ORIGINAL_LISTENERS_ONE_PER_POLL'
                    return self.public()
            for server in self.servers:
                if not original_handler_threads_clear(server):
                    self.wait_code = 'NORMAL_TRANSPORT_WAIT_ORIGINAL_HANDLER_THREADS_EXIT'
                    return self.public()
            # One fixed finite set: all six close APIs run only after the same
            # fresh all-six preflight and ALL handler threads ended. No wait,
            # re-poll of a now-closed server, or duplicate close is introduced.
            for server in self.servers:
                if id(server) not in self.closed:
                    current = server.close_after_drained
                    need(current.__func__ is self.close_methods[id(server)].__func__,
                         'NORMAL_TRANSPORT_SAME_CURRENT_V2_BOUND_CLOSE_GUARDS')
                    try:
                        current()  # raw/effective UNKNOWN guard is NEVER altered
                    except Exception as error:
                        self.wait_code = fixed_code(error, 'NORMAL_TRANSPORT_ORIGINAL_CLOSE_REFUSED')
                        self.failure = exception_public(error)
                        self.state = 'WAIT_ORIGINAL_CLOSE_GUARD_RETAINED_NO_RETRY'
                        return self.public()
                    self.closed.add(id(server))
            self.state = 'OLD_HTTP_TRANSPORTS_RETIRED_NO_SDK_CLAIM'
        except TransportWait as error:
            self.wait_code = error.code
        except Exception as error:
            self.failure = exception_public(error)
            self.state = 'PARTIAL_RETAINED_NO_RETRY'
        return self.public()

    def public(self):
        return dict(schema='count14-normal-old-HTTP-retirement-WIP-public-v1', state=self.state,
            requested=self.requested, original_gate_shutdown=self.gate_shutdown_done,
            original_listeners_stopped=len(self.stopped), original_HTTP_servers_closed=len(self.closed),
            retained_unsent_control=None if self.protected_control is None else dict(self.protected_control),
            wait_code=self.wait_code, failure=copy.deepcopy(self.failure), original_stop_elapsed_seconds=dict(self.stop_elapsed),
            model_replays=0, model_cancel_or_core_engine_queue_FINAL_close_called=False,
            SYSTEM_health_or_resource_stop_called=False, existing_archives_control_SID_modified=False,
            normal_SDK_resume_or_pending_request_reconstruction_qualified=False,
            whole_cold_ready=False, normal_handoff_authority_implemented=False,
            OPS_control_opcode_installed=False, actual_Dev4_or_six_graph_qualified=False)


def fixed_code(error, fallback):
    code = getattr(error, 'code', None)
    return code if type(code) is str and re.fullmatch('[A-Z0-9_]{1,160}', code) else fallback


def exception_public(error):
    locations, tb = [], error.__traceback__
    while tb:
        locations.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                              function=tb.tb_frame.f_code.co_name));tb = tb.tb_next
    return dict(PUBLIC_code=fixed_code(error, 'NORMAL_TRANSPORT_ORIGINAL_API_REFUSED_RETAIN'),
                exception_type=type(error).__name__, locations=locations)
