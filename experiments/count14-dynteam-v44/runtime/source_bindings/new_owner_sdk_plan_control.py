"""NEW receiving-owner strict plan/ACK/once control, no old guard rewrites.

Installation is not issuance. Missing original runtime methods, physical/kernel
custody or actual receiving CLI always WAIT; INERT metadata alone cannot pass.
Only the existing owner loop calls poll_once. No SDK process or SQL is started.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MethodType
import copy
import hashlib
import importlib
import os
import socket
import struct
import threading
import time

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from common import digest, wire, publish, strict
from native_peer_registry import process_birth
from native_session_control import NativeSessionControl, checked
from native_sdk_startup_epochs import NativeSdkStartupEpochs, Epoch
from native_bridge_owner import same_child_alive
from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
import new_owner_sdk_guest_control as R
import normal_inert_cut as T

HOST_SHA256 = 'dadf6ce97da5a7f57d239ac7f4bbbdd397308745c36fa9575d48c524c6ecfb85'
_SEAL = object()
_CONTROLS = {}
PATHS = ('/native-sdk-new-owner-plan', '/native-sdk-restore-ack',
         '/native-sdk-collaboration-recovery')


def host_api():
    module = importlib.import_module('new_owner_host_control')
    path = Path(module.__file__)
    expected = Path(__file__).resolve().parents[1]/'formal100m-new-owner-host-control-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/new_owner_host_control.py'
    M.need(HOST_SHA256 is not None and path == expected and path.resolve() == path
           and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == HOST_SHA256,
           'NEW_OWNER_PLAN_WAIT_FIXED_NEW_HOST_GRAPH_PIN')
    return module


@dataclass(frozen=True, repr=False)
class NewOwnerLoadPlan:
    control: object
    key: tuple
    _descriptor_raw: bytes
    receiving_epoch: Epoch
    receiving_cli: dict
    source_epoch: Epoch
    source_count: int
    _seal: object

    @property
    def descriptor(self):
        M.need(self._seal is _SEAL, 'NEW_OWNER_PLAN_ONLY_FIXED_ISSUED_DESCRIPTOR')
        return strict(self._descriptor_raw) # Fresh copy; callers cannot mutate the retained plan.


class NewOwnerGuestPlanControl:
    def __init__(self, graph):
        G = host_api()
        M.need(type(graph) is G.NewOwnerHostControlGraph
               and G.registered_stage_host_graph(graph.stage) is graph
               and graph.registration is R.registered_stage_sdk_controls(graph.stage)
               and type(graph.control) is NativeSessionControl and not graph.control.started
               and id(graph) not in _CONTROLS,
               'NEW_OWNER_PLAN_NEW_REGISTERED_UNSTARTED_ORIGINAL_CONTROL_ONLY')
        self.graph, self.stage, self.core = graph, graph.stage, graph.core
        self.owner = process_birth(os.getpid()); self.thread = threading.get_ident()
        self.lock = threading.Lock(); self.queue = []; self.plans = {}; self.sequence = 0
        self.failure = None
        self._install_handler(); _CONTROLS[id(graph)] = self
        # The existing same-owner metadata step drives both CONTROL inboxes.
        # Preserve its original bound function; no dispatcher/thread/class edit.
        previous = graph.poll_metadata_once
        M.need(previous.__func__ is G.NewOwnerHostControlGraph.poll_metadata_once,
               'NEW_OWNER_PLAN_ONLY_ORIGINAL_NEW_GRAPH_METADATA_STEP_ONCE')
        self.original_metadata_poll = previous
        def metadata_poll(own, *, read_budget):
            M.need(own is graph, 'NEW_OWNER_PLAN_SAME_GRAPH_OWNER_METADATA_STEP')
            result = previous(read_budget=read_budget)
            self.poll_once()
            return result
        graph.poll_metadata_once = MethodType(metadata_poll, graph)

    def _current(self):
        G = host_api(); graph = self.graph
        M.need(_CONTROLS.get(id(graph)) is self and G.registered_stage_host_graph(self.stage) is graph
               and R.registered_stage_sdk_controls(self.stage) is graph.registration
               and graph.core is self.core is self.stage.core
               and self.owner == self.stage.new_owner_birth == process_birth(os.getpid())
               and self.thread == threading.get_ident()
               and not self.core.ledger.mutex._is_owned() and not self.core.queue.mutex._is_owned()
               and self.core.gate.closed and not self.core.gate.waiters
               and set(self.core.gate.startup_held) == set(self.core.rows),
               'NEW_OWNER_PLAN_EXACT_SAME_HELD_OWNER_LOOP_GRAPH')

    def _legal(self, key):
        """Use actual original runtime custody; never call around quarantine."""
        self._current(); graph = self.graph; reg = graph.registration; epochs = reg.epochs
        cap = T.verify_inert_ticket(reg.source_ticket, owner=reg.source_owner, read_budget=ReadBudget())
        M.need(type(cap) is T.VerifiedNormalInertCut and cap.OWN is False
               and cap.source_control_sha256 == reg.source_control_sha256
               and cap.component('native_SDK_epoch_controls') == reg.source_section,
               'NEW_OWNER_PLAN_FRESH_ORIGINAL_SOURCE_LINEAGE_STILL_EQUAL')
        custody = graph.kernel_custody
        M.need(type(custody) is NativeKernelToolCustody and custody.core is self.core
               and getattr(self.core, 'native_kernel_tool_custody', None) is custody
               and getattr(graph.publisher, 'native_kernel_tool_custody', None) is custody
               and getattr(custody, 'sdk_startup_epochs', None) is epochs and epochs.custody is custody,
               'NEW_OWNER_PLAN_WAIT_ACTUAL_SAME_CORE_KERNEL_CUSTODY')
        M.need(all(getattr(epochs, n).__func__ is getattr(NativeSdkStartupEpochs, n)
                   for n in ('_physical', '_capture', '_game', '_project_epoch', 'project')),
               'NEW_OWNER_PLAN_WAIT_ORIGINAL_RUNTIME_NOT_METADATA_QUARANTINE')
        epoch = epochs.current.get(key); cli = graph.bridge_owner.clis.get(key)
        source = reg.source_transfer.current.get(key)
        M.need(type(epoch) is Epoch and type(source) is Epoch and epoch.owner_birth == self.owner
               and source.owner_birth == reg.old_owner_birth and type(cli) is dict
               and not epoch.archived and not cli['archived'] and cli['end_lease'] is None
               and cli['birth'] == epoch.child and cli['token'] == epoch.token
               and same_child_alive(epoch.child),
               'NEW_OWNER_PLAN_WAIT_ACTUAL_RECEIVING_CLI_EPOCH_NOT_SOURCE_PYTHON_IDENTITY')
        count_rows = [v for v in reg.source_section['counts']['by_registered_epoch_role'] if tuple(v['key']) == key]
        M.need(len(count_rows) == 1 and epochs._count(key) == count_rows[0]['original_request_rows']
               and epochs._session(key) == reg.source_transfer.current_original_session_pairs[key],
               'NEW_OWNER_PLAN_ORIGINAL_SOURCE_COUNT_SID_AND_ANCHORS_NOT_REBASELINED')
        if epoch.child != source.child:
            M.need(not same_child_alive(source.child)
                   and all(not same_child_alive(b) for c in source.components for b in c.sdk),
                   'NEW_OWNER_PLAN_OLD_CLI_AND_ALL_OLD_SDK_BIRTHS_MUST_BE_ABSENT')
        epochs._physical(key)
        M.need(epochs._capture(key, epoch.child, previous=source.components) == epoch.components
               and custody(*key) is True,
               'NEW_OWNER_PLAN_WAIT_TRUE_ORIGINAL_MODEL_HTTP_KERNEL_AND_ORDERED_TOOL_ZERO')
        return epoch, cli, source, count_rows[0]['original_request_rows']

    def issue_plan(self, key, *, native_turn, read_budget):
        M.need(type(read_budget) is ReadBudget, 'NEW_OWNER_PLAN_FINITE_BUDGET')
        read_budget.check(); epoch, cli, source, count = self._legal(key)
        reg = self.graph.registration
        cap = T.verify_inert_ticket(reg.source_ticket, owner=reg.source_owner, read_budget=read_budget)
        M.need(type(cap) is T.VerifiedNormalInertCut and cap.OWN is False,
               'NEW_OWNER_PLAN_TYPED_PRODUCTION_SOURCE_PROOF_NOT_GRANT')
        rows = [r for r in reg.source_transfer.clis if r.key == key]
        M.need(len(rows) == 1 and not rows[0].archived, 'NEW_OWNER_PLAN_EXACT_SOURCE_CLI_LINEAGE')
        row = rows[0]; pair = reg.epochs._session(key)
        M.need(pair is not None and type(native_turn) is str
               and hashlib.sha256(__import__('json').dumps(
                   ['70e2ca54c078597e3314755064d2ef1a83344c8e', *key, native_turn],
                   ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() == row.token[3],
               'NEW_OWNER_PLAN_ONLY_ORIGINAL_RUNTIME_TURN_METADATA')
        snapshot = cap._body['source_controls']['cuts'][key[0]]['snapshot_reference']['sha256']
        M.sha(snapshot)
        custody_binding = dict(source_control_sha256=reg.source_control_sha256,
            source_epoch_sha256=digest(asdict(source)), receiving_epoch_sha256=digest(asdict(epoch)),
            receiving_owner_birth_sha256=digest(asdict(self.owner)), receiving_cli_birth_sha256=digest(asdict(epoch.child)),
            request_count=count, models_held=True)
        body = dict(trajectory=key[0], role=key[1], snapshot_sha256=snapshot,
                    session_sha256=hashlib.sha256(pair[1].encode()).hexdigest(), **custody_binding)
        pin = digest(body); M.need(pin not in self.plans, 'NEW_OWNER_PLAN_NO_SECOND_ISSUANCE_OR_REPLAY')
        descriptor = dict(schema='count14-formal-cold-sdk-load-control-v1', plan_sha256=pin,
            snapshot_sha256=snapshot, trajectory=key[0], role=key[1], native_session_uuid=pair[1],
            session_sha256=body['session_sha256'], native_turn=native_turn,
            logical_birth_sha256=row.raw_birth, native_turn_sha256=row.token[3],
            control_socket='/run/count14-dynteam/native-control.sock', no_prompt=True, no_fallback=True,
            new_owner_control_sha256=digest(custody_binding), new_owner_control=custody_binding)
        plan = NewOwnerLoadPlan(self, key, wire(descriptor), epoch, cli, source, count, _SEAL)
        self.plans[pin] = dict(plan=plan, state='ISSUANCE_INTENT_RETAINED', preflight=False,
                               strict_ack=False, once=None, complete=False)
        self._receipt('PLAN_ISSUED_HELD', plan_sha256=pin, **body)
        self.plans[pin]['state'] = 'ISSUED_WAIT_GUEST_PREFLIGHT'
        return plan

    def stage_control_descriptor(self, plan):
        """Existing scoped runtime exports only; no caller-selected path."""
        self._current()
        M.need(type(plan) is NewOwnerLoadPlan and plan._seal is _SEAL and plan.control is self
               and self.plans.get(plan.descriptor['plan_sha256'], {}).get('plan') is plan
               and os.geteuid() == 0,
               'NEW_OWNER_PLAN_ONLY_TRUSTED_RUNTIME_ISSUED_DESCRIPTOR_NO_ELEVATION')
        self._legal(plan.key)
        exports = getattr(self.core, 'cold_native_exports', None)
        M.need(type(exports) is dict, 'NEW_OWNER_PLAN_WAIT_ACTUAL_SCOPED_NATIVE_CONTROL_EXPORTS')
        role = exports['trajectories'][plan.key[0]]['role_exports'][plan.key[1]]
        raw = wire(plan.descriptor); pin = hashlib.sha256(raw).hexdigest()
        for key in ('agent_control_directory', 'router_control_directory'):
            path = Path(role[key])/'cold-sdk-restore.json'
            M.need(path.is_absolute() and path.parent.resolve() == path.parent and not path.is_symlink(),
                   'NEW_OWNER_PLAN_ORIGINAL_EXACT_SCOPED_CONTROL_DIRECTORY')
            publish(path, raw, mode=0o444)
        return dict(COUNT14_COLD_SDK_RESTORE_FILE='/run/count14-dynteam/cold-sdk-restore.json',
                    COUNT14_COLD_SDK_RESTORE_SHA256=pin)

    def _receipt(self, kind, **metadata):
        root = self.graph.control.path.parent/'sdk-new-owner-control'
        root.mkdir(mode=0o700, exist_ok=True)
        M.need(root.resolve() == root and not root.is_symlink(), 'NEW_OWNER_PLAN_FIXED_NEW_CONTROL_HOME')
        self.sequence += 1
        body = dict(metadata)
        body.update(schema='count14-new-owner-sdk-control-receipt-v1', kind=kind,
            receiving_owner_birth_sha256=digest(asdict(self.owner)),
            safe_to_TERM=False, paid_activation_authorized=False, whole_runnable_ready=False)
        publish(root/(str(self.sequence).zfill(8)+'-'+kind+'_PUBLIC.json'), wire(body), mode=0o400)

    def _install_handler(self):
        return _install_plan_handler(self.graph.control, self)

    def poll_once(self):
        self._current()
        with self.lock: tickets, self.queue = self.queue, []
        for ticket in tickets:
            try:
                M.need(time.monotonic() < ticket['expires'], 'NEW_OWNER_PLAN_EXPIRED_NO_ACCEPT')
                ticket['result'] = self._handle(ticket['path'], ticket['value'], ticket['peer'])
                ticket['accepted'] = True
            except Exception as error:
                self.failure = dict(PUBLIC_code='NEW_OWNER_PLAN_WAIT_NO_PROMPT', exception_type=type(error).__name__)
            finally: ticket['event'].set()
        return len(tickets)

    def _handle(self, path, value, peer):
        M.need(type(value) is dict, 'NEW_OWNER_PLAN_EXACT_CONTROL_OBJECT')
        p = self.plans.get(value.get('plan_sha256'))
        M.need(p is not None, 'NEW_OWNER_PLAN_NOT_ISSUED_INERT_DESCRIPTOR_IS_NOT_AUTHORITY')
        plan = p['plan']; d = plan.descriptor
        epoch, cli, source, count = self._legal(plan.key)
        M.need(epoch is plan.receiving_epoch and cli is plan.receiving_cli and source is plan.source_epoch
               and count == plan.source_count, 'NEW_OWNER_PLAN_SAME_RETAINED_NEW_CLI_EPOCH_IDENTITY')
        if path == PATHS[0]:
            fields = {'schema','plan_sha256','snapshot_sha256','session_sha256','trajectory','role','new_owner_control_sha256'}
            M.need(set(value) == fields and value['schema'] == 'count14-new-owner-sdk-plan-check-v1'
                   and all(value[k] == d[k] for k in fields-{'schema'})
                   and self.graph.peers.validate(dict(schema='count14-dynteam-native-session-ready-v1',
                       source_commit='70e2ca54c078597e3314755064d2ef1a83344c8e',
                       trajectory_id=plan.key[0], role_slot=plan.key[1]), peer)
                   and not p['preflight'], 'NEW_OWNER_PLAN_EXACT_LIVE_ROUTER_PREFLIGHT_ONCE')
            p['preflight'] = True
            self._receipt('GUEST_PREFLIGHT', plan_sha256=d['plan_sha256'])
            return dict(new_owner_control_sha256=d['new_owner_control_sha256'], models_held=True)
        row = checked(value['session'])
        M.need(p['preflight'] and value['snapshot_sha256'] == d['snapshot_sha256']
               and (row['trajectory_id'], row['role_slot']) == plan.key
               and row['native_session_uuid'] == d['native_session_uuid']
               and row['logical_birth_sha256'] == d['logical_birth_sha256']
               and row['native_turn_sha256'] == d['native_turn_sha256']
               and self.graph.peers.validate(row, peer), 'NEW_OWNER_PLAN_ORIGINAL_ACK_SAME_PEER_SID_TURN')
        if path == PATHS[1]:
            M.need(set(value) == {'schema','plan_sha256','snapshot_sha256','session_sha256','session','loaded_original','prompt_sent'}
                   and value['schema'] == 'count14-formal-cold-sdk-loaded-ack-v1'
                   and value['session_sha256'] == d['session_sha256']
                   and value['loaded_original'] is True and value['prompt_sent'] is False
                   and not p['strict_ack'], 'NEW_OWNER_PLAN_FIXED_ORIGINAL_STRICT_ACK_ONCE')
            inbox = self.graph.publisher.inbox
            key = hashlib.sha256(__import__('json').dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            with inbox.lock:
                durable = inbox.tickets.get(key)
                M.need(durable is not None and durable.envelope == row and durable.peer == tuple(peer)
                       and durable.accepted is True and durable.complete.is_set(),
                       'NEW_OWNER_PLAN_WAIT_ORIGINAL_PUBLISHER_DURABLE_NATIVE_SESSION_ACK')
            self._receipt('STRICT_NORMAL_LOAD_ACK', plan_sha256=d['plan_sha256'], session_sha256=d['session_sha256'])
            p['strict_ack'] = True
            return {}
        return self._once(p, value)

    def _once(self, p, value):
        base = {'schema','plan_sha256','snapshot_sha256','session','stage','before'}
        M.need(p['strict_ack'] and value['schema'] == 'count14-formal-cold-collaboration-recovery-v1'
               and value['stage'] in ('INTENT','COMMITTED')
               and set(value) == (base if value['stage'] == 'INTENT' else base|{'after','recovered','recovery_token'}),
               'NEW_OWNER_PLAN_ORIGINAL_ONCE_AFTER_TRUE_STRICT_ACK')
        before = value['before']
        M.need(type(before) is dict and set(before) == {'sending','retrying'}
               and all(type(n) is int and 0 <= n <= 1000000 for n in before.values()),
               'NEW_OWNER_PLAN_FINITE_COLLABORATION_COUNTS_NOT_EVENT_BODIES')
        if value['stage'] == 'INTENT':
            M.need(p['once'] is None, 'NEW_OWNER_PLAN_RETAINED_INTENT_UNKNOWN_NO_SECOND_RECOVERY')
            token = digest(dict(plan=value['plan_sha256'], before=before, source_count=p['plan'].source_count))
            p['once'] = dict(before=copy.deepcopy(before), token=token, state='INTENT_RETAINED')
            self._receipt('COLLABORATION_INTENT', plan_sha256=value['plan_sha256'], before=before, recovery_token=token)
            return dict(recovery_token=token)
        intent = p['once']
        M.need(intent is not None and not p['complete'] and before == intent['before']
               and value['recovery_token'] == intent['token'] and type(value['recovered']) is int
               and value['recovered'] == before['sending']
               and value['after'] == dict(sending=0, retrying=before['retrying']),
               'NEW_OWNER_PLAN_ORIGINAL_RECOVERY_RESULT_ONCE_COUNTS')
        p['complete'] = True  # Retain before durable write; failure never retries.
        self._receipt('COLLABORATION_COMMITTED', plan_sha256=value['plan_sha256'], before=before,
                      after=value['after'], recovered=value['recovered'], recovery_token=intent['token'])
        intent['state'] = 'COMMITTED'
        return dict(recovery_token=intent['token'])


def _install_plan_handler(native_control, control):
    M.need(type(native_control) is NativeSessionControl
           and type(control) in (NewOwnerGuestPlanControl, OWNUnissuedPlanEndpoint),
           'NEW_OWNER_PLAN_FIXED_PRODUCTION_OR_EXPLICIT_OWN_INGRESS_ONLY')
    original = native_control.server.RequestHandlerClass
    class NewOwnerHandler(original):
        def do_POST(own):
            if own.path not in PATHS: return super().do_POST()
            try:
                lengths = own.headers.get_all('Content-Length', [])
                M.need(not own.headers.get('Transfer-Encoding') and len(lengths) == 1
                       and lengths[0].isdigit() and 0 < int(lengths[0]) <= 4096,
                       'NEW_OWNER_PLAN_BOUNDED_ORIGINAL_PROTOCOL')
                value = strict(own.rfile.read(int(lengths[0])))
                peer = struct.unpack('3i', own.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                ticket = dict(path=own.path, value=value, peer=peer, event=threading.Event(),
                              accepted=False, result={}, expires=time.monotonic()+2)
                with control.lock:
                    M.need(len(control.queue) < 128, 'NEW_OWNER_PLAN_FINITE_CONTROL_QUEUE')
                    control.queue.append(ticket)
                okay = ticket['event'].wait(2) and ticket['accepted']
                own.answer(200 if okay else 503, dict(accepted=bool(okay),
                    plan_sha256=value.get('plan_sha256'), **ticket['result']))
            except Exception:
                own.answer(503, dict(accepted=False, PUBLIC_code='NEW_OWNER_PLAN_WAIT_NO_PROMPT'))
    native_control.server.RequestHandlerClass = NewOwnerHandler


class OWNUnissuedPlanEndpoint:
    """Explicit real-transport rejection port. Cannot register or issue a plan.

    This is not a fabricated production graph/capability or a load test. Its
    only operation records actual kernel peer credentials and refuses a request.
    """
    def __init__(self, native_control, *, home, peers, read_budget):
        from native_peer_registry import NativePeerRegistry
        root = Path(home)
        M.need(type(read_budget) is ReadBudget and type(native_control) is NativeSessionControl
               and not native_control.started and native_control.path.parent == root
               and root.is_absolute() and root.resolve() == root and root.name.startswith('OWN-')
               and root.stat().st_uid == os.geteuid() and root.stat().st_mode & 0o777 == 0o700
               and type(peers) is NativePeerRegistry,
               'NEW_OWNER_PLAN_EXPLICIT_PRIVATE_OWN_TRANSPORT_REJECTION_ONLY')
        read_budget.check()
        self.control, self.peers = native_control, peers
        self.lock = threading.Lock(); self.queue = []; self.observed_peers = []; self.rejected = 0
        _install_plan_handler(native_control, self)

    def poll_once(self):
        with self.lock: tickets, self.queue = self.queue, []
        for ticket in tickets:
            try:
                value = ticket['value']; peer = ticket['peer']
                M.need(self.peers.validate(dict(schema='count14-dynteam-native-session-ready-v1',
                    source_commit='70e2ca54c078597e3314755064d2ef1a83344c8e',
                    trajectory_id=value['trajectory'], role_slot=value['role']), peer),
                    'NEW_OWNER_PLAN_OWN_ACTUAL_REGISTERED_KERNEL_PEER')
                self.observed_peers.append(peer); self.rejected += 1
                # No production graph, plan, ACK or recovery token is minted.
            finally: ticket['event'].set()
        return len(tickets)
