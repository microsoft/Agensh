"""Original owner-loop native CLI lifecycle composition; control metadata only.

Exact peer -> direct original child PID/start/ns -> original physical model/
tool projection -> anonymous durable membership -> original role gate. No
model, process signal, source/session read, fee rewrite or dispatcher here.
"""
from pathlib import Path
import copy
import time

from common import need, digest
from native_peer_registry import ProcessBirth, process_birth
from native_bridge_protocol import checked_lifecycle


def direct_native_child(peer_pid, namespace_pid, start_ticks, *, expected_uid):
    need(all(type(v) is int and v > 0 for v in (peer_pid, namespace_pid, start_ticks)) and
         type(expected_uid) is int and expected_uid >= 0,
         'DYNTEAM_EXACT_NATIVE_CHILD_TYPED_IDENTIFIERS')
    parent = process_birth(peer_pid)
    task_root = Path('/proc', str(peer_pid), 'task')

    def bounded(path, limit):
        with path.open('rb') as stream:
            raw = stream.read(limit + 1)
        need(len(raw) <= limit, 'DYNTEAM_REGISTERED_BRIDGE_FIXED_METADATA_BOUND')
        return raw

    def status(path, wanted):
        values = {}
        for line in bounded(path, 16384).splitlines():
            key, sep, text = line.partition(b':')
            if sep and key in wanted:
                need(key not in values, 'DYNTEAM_NATIVE_CHILD_STATUS_DUPLICATE_FIELD')
                values[key] = tuple(map(int, text.split()))
        need(set(values) == wanted, 'DYNTEAM_NATIVE_CHILD_STATUS_COMPLETE_FIELDS')
        return values

    def snapshot():
        tids = []
        for entry in task_root.iterdir():
            need(entry.name.isascii() and entry.name.isdigit() and int(entry.name) > 0 and
                 len(tids) < 128, 'DYNTEAM_REGISTERED_BRIDGE_THREADS_BOUND')
            tids.append(int(entry.name))
        need(peer_pid in tids and len(set(tids)) == len(tids),
             'DYNTEAM_REGISTERED_BRIDGE_LEADER_AND_UNIQUE_THREADS')
        threads, children = [], set()
        rows_seen = 0
        for tid in sorted(tids):
            task = task_root / str(tid)
            raw = bounded(task / 'stat', 16384)
            close = raw.rfind(b')')
            fields = raw[close + 2:].split()
            need(close >= 0 and len(fields) >= 20 and fields[0] not in (b'Z', b'X', b'x'),
                 'DYNTEAM_REGISTERED_BRIDGE_THREAD_LIVE_METADATA')
            tgid = status(task / 'status', {b'Tgid'})
            need(tgid[b'Tgid'] == (peer_pid,), 'DYNTEAM_REGISTERED_BRIDGE_THREAD_EXACT_TGID')
            born = int(fields[19])
            need(born > 0, 'DYNTEAM_REGISTERED_BRIDGE_THREAD_START')
            threads.append((tid, born))
            rows = bounded(task / 'children', 8192).split()
            need(all(v.isdigit() and int(v) > 0 for v in rows),
                 'DYNTEAM_REGISTERED_BRIDGE_CHILD_PID_FIELDS')
            rows_seen += len(rows)
            need(rows_seen <= 128, 'DYNTEAM_REGISTERED_BRIDGE_CHILDREN_BOUND')
            children.update(map(int, rows))
        need(process_birth(peer_pid) == parent,
             'DYNTEAM_REGISTERED_BRIDGE_FULL_BIRTH_STABLE')
        return tuple(threads), tuple(sorted(children))

    threads, children = snapshot()
    selected = []
    selected_status = None
    for pid in children:
        path = Path('/proc', str(pid), 'status')
        values = status(path, {b'NSpid', b'PPid', b'Tgid'})
        if values[b'NSpid'][-1:] != (namespace_pid,):
            continue
        birth = process_birth(pid)
        # Preserve original PPid/start/UID requirements, and explicitly reject
        # thread IDs, nested/foreign namespaces and any PID/birth race.
        need(values[b'PPid'] == (peer_pid,) and values[b'Tgid'] == (pid,) and
             birth.start_ticks == start_ticks and birth.uid == expected_uid,
             'DYNTEAM_EXACT_NATIVE_CHILD_PARENT_START_UID')
        need((birth.pid_namespace, birth.network_namespace, birth.mount_namespace) ==
             (parent.pid_namespace, parent.network_namespace, parent.mount_namespace),
             'DYNTEAM_EXACT_NATIVE_CHILD_SAME_REGISTERED_NAMESPACES')
        selected.append(birth)
        selected_status = values
    need(len(selected) == 1, 'DYNTEAM_ONE_ORIGINAL_NATIVE_CHILD_REQUIRED')
    child = selected[0]
    need(snapshot() == (threads, children),
         'DYNTEAM_REGISTERED_BRIDGE_THREADS_AND_CHILDREN_STABLE')
    need(status(Path('/proc', str(child.pid), 'status'), {b'NSpid', b'PPid', b'Tgid'}) == selected_status and
         process_birth(child.pid) == child and process_birth(peer_pid) == parent,
         'DYNTEAM_EXACT_NATIVE_CHILD_AND_PEER_FULL_BIRTH_STABLE')
    return child


def same_child_alive(birth):
    try:
        return process_birth(birth.pid) == birth
    except FileNotFoundError:
        return False


class NativeBridgeLifecycleOwner:
    def __init__(self, core, *, child_uid, original_physical_projection, archive_guard):
        need(type(child_uid) is int and child_uid >= 0 and
             (child_uid > 0 or core.qualification_only) and
             callable(original_physical_projection) and callable(archive_guard),
             'DYNTEAM_NATIVE_BRIDGE_TRUSTED_ORIGINAL_BINDINGS')
        self.core, self.uid = core, child_uid
        self.physical, self.archive = original_physical_projection, archive_guard
        self.clis = {}
        self.logical = {}
        self.finished = set()
        self.end_transitions = {}
        self.clear_observations = {}
        self.prepark_wait_cache = {}

    def _clear(self, key):
        proof = self.physical(*key)
        need(type(proof) is dict and set(proof) == {'models_clear','tools_clear'} and
             all(type(v) is bool for v in proof.values()), 'DYNTEAM_ORIGINAL_NATIVE_PHYSICAL_BOOLEAN_PROJECTION')
        self.clear_observations[key] = dict(proof,observed_monotonic_ns=time.monotonic_ns())
        return proof['models_clear'] and proof['tools_clear']

    def _note_end_wait(self, trajectory, code):
        old = self.prepark_wait_cache.get(trajectory, {})
        counts = dict(old.get('reason_counts', {}))
        counts[code] = counts.get(code, 0) + 1
        rows = [v for k, v in self.end_transitions.items() if k[0] == trajectory]
        self.prepark_wait_cache[trajectory] = dict(
            reason_code=code, reason_counts=counts, pending_native_END_transitions=len(rows),
            held=self.core.roles.native_end_status(trajectory),
            last_clear_projections=[dict(role_slot=k[1], **v)
                for k,v in sorted(self.clear_observations.items()) if k[0] == trajectory],
            longest_transition_ns=max((time.monotonic_ns()-v['since_ns'] for v in rows), default=0))

    def prepark_pending(self, trajectory):
        """Same owner metadata only; no physical probe or model request.

        Keep the END -> archive -> required replacement birth/session interval
        closed as one prepark transition. A new END AFTER cut has no side effect.
        """
        epochs = getattr(self.core, 'native_sdk_startup_epochs', None)
        for key, transition in list(self.end_transitions.items()):
            if key[0] != trajectory or transition['state'] != 'ARCHIVED_WAIT_REPLACEMENT':
                continue
            cli = self.clis.get(key)
            epoch = None if epochs is None else epochs.current.get(key)
            # session_bound is written only AFTER the original affinity commit.
            bound = (epochs is not None and any(k[0] == key and
                     value.child == cli['birth'] and value.token == cli['token']
                     for k, value in epochs.session_bound.items())) if cli is not None else False
            if (cli is not None and epoch is not None and bound and
                    cli['birth'] != transition['birth'] and cli['token'] != transition['token'] and
                    not cli['archived'] and not epoch.archived and
                    epoch.child == cli['birth'] and epoch.token == cli['token'] and
                    epochs.birth_committed(*key, cli['birth'], cli['token']) and
                    transition['token'] in self.finished):
                del self.end_transitions[key]
        pending = any(key[0] == trajectory for key in self.end_transitions)
        self._note_end_wait(trajectory, 'WAIT_NATIVE_END_TRANSITION' if pending else 'NATIVE_END_PREPARK_READY')
        return pending

    def prepark_public(self, trajectory):
        # Export cache only: no new census/SQL/process access from PUBLIC.
        return copy.deepcopy(self.prepark_wait_cache.get(trajectory))

    def handle(self, row, peer):
        checked_lifecycle(row)
        need(self.core.peers.validate(row,peer), 'DYNTEAM_EXACT_REGISTERED_BRIDGE_PEER')
        key = (row['trajectory_id'],row['role_slot'])
        t, role = key
        if row['event']=='BRIDGE_READY':
            # peer_validator already authenticated the exact preregistered
            # init/CID/code/UID/namespace and registered this bridge ancestry.
            # Never convert this metadata ACK into a CLI/SDK/lifecycle proof.
            from native_container_retirement import ContainerBinding
            binding=self.core.native_containers.records.get((t,role,'agent'))
            return bool(type(binding)is ContainerBinding and binding.peer_birth.pid==peer[0]
                        and row['child_namespace_pid']==0
                        and not row['child_running'] and not row['archive_durable']
                        and row['end_kind']=='NONE' and row.get('tool_control')is None)
        raw_birth = row['logical_birth_sha256']
        journal = self.core.journals[t]
        anonymous = journal.projection._identity(role, raw_birth)
        token = (key,row['child_namespace_pid'],row['child_start_ticks'],row['native_turn_sha256'])
        event = row['event']
        if event == 'CLI_BIRTH':
            child = direct_native_child(peer[0], row['child_namespace_pid'], row['child_start_ticks'], expected_uid=self.uid)
            old = self.clis.get(key)
            if old is not None and old['token'] == token:
                epochs=getattr(getattr(self.core,'native_kernel_tool_custody',None),'sdk_startup_epochs',None)
                return same_child_alive(old['birth']) and (epochs is None or epochs.birth_committed(t,role,child,token))
            custody=getattr(self.core,'native_kernel_tool_custody',None)
            if custody is not None:
                from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
                need(type(custody) is NativeKernelToolCustody and custody.core is self.core,
                     'DYNTEAM_EXACT_KERNEL_TOOL_CUSTODY_SAME_OWNER')
                custody.observe_cli_birth(t,role,child,row=row)
            need(old is None or old['archived'] and not same_child_alive(old['birth']),
                 'DYNTEAM_PREVIOUS_NATIVE_CHILD_OR_ARCHIVE_RETAINED')
            if not self._clear(key):
                return False
            covering=self.core.pending_native_launches.get(key)
            if covering is not None:
                need(type(covering) is dict and self.core.membership_fences[t].owns(covering.get('lease'),role),
                     'DYNTEAM_NATIVE_LAUNCH_MUST_OWN_EXACT_MEMBERSHIP_LEASE')
            own_lease=None if covering is not None else self.core.membership_fences[t].acquire(role,'BIRTH')
            if covering is None and own_lease is None:return False
            anchor,_ = self.core.original_projection(t,role)
            if key not in self.logical:
                journal.record_lifecycle('BIRTH',role,raw_birth,anchor)
                self.core.roles.open_birth(t,role,anonymous,durable_metadata=True,previous_physical_clear=True)
                self.logical[key] = raw_birth
            else:
                need(self.logical[key] == raw_birth,'DYNTEAM_OLD_LOGICAL_AGENT_NOT_RETIRED')
                self.core.roles.reopen_same_logical_birth(t,role,anonymous, previous_cli_exited=True,
                    previous_physical_clear=True,new_cli_metadata_durable=True)
            self.clis[key] = dict(token=token,birth=child,raw_birth=raw_birth,archived=False,end_lease=None)
            if covering is not None:
                covering['birth_observed']=True
                covering['native_cli_token_sha256']=digest(token)
            else:
                self.core.membership_fences[t].finish(own_lease,
                    original_control_receipt_sha256=digest(['NATIVE_CLI_BIRTH_DURABLE',token]))
            epochs=getattr(custody,'sdk_startup_epochs',None)
            if epochs is not None:epochs.commit_birth(t,role,child,token)
            return True
        if event == 'BEFORE_CLEANUP' and row['child_namespace_pid'] == 0:
            # Startup archival is allowed only on a truly fresh role. Paid
            # session recovery needs original SDK restoration, never auto-clear.
            with self.core.ledger.mutex:
                paid = self.core.ledger.db.execute("SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=? "
                    "AND state IN('SENT','SETTLED','UNKNOWN')",key).fetchone()[0]
            return paid == 0 and self._clear(key) and row['archive_durable'] and self.archive(row, None) is True
        cli = self.clis.get(key)
        need(cli is not None and cli['token'] == token and cli['raw_birth'] == raw_birth,
             'DYNTEAM_NATIVE_LIFECYCLE_EXACT_CURRENT_CLI')
        custody=getattr(self.core,'native_kernel_tool_custody',None)
        if custody is not None and row.get('tool_control') is not None:
            from smoke_racing_tools_cold_control_builder import consume_control_snapshot
            consume_control_snapshot(custody,t,role,cli['birth'],row['tool_control'])
        if event == 'END_REQUEST':
            # Resolve a completed previous tester cycle even while RUNNING;
            # checkpoint.step is not the only caller of this metadata barrier.
            self.prepark_pending(t)
            if token in self.finished:
                # Exact already-archived retry: never acquire a lease which
                # ARCHIVED_END's original idempotent fast path cannot finish.
                return cli['archived'] and cli['end_lease'] is None
            transition=self.end_transitions.get(key)
            if transition is not None and transition['token'] != token:
                epochs=getattr(self.core,'native_sdk_startup_epochs',None)
                epoch=None if epochs is None else epochs.current.get(key)
                # A replacement may itself finish before its first SID binds.
                # Roll the SAME barrier only after its original birth commit;
                # never invent a SID, control snapshot, or physical clearance.
                need(transition['state']=='ARCHIVED_WAIT_REPLACEMENT' and
                     transition['token'] in self.finished and
                     transition['birth'] != cli['birth'] and not cli['archived'] and
                     epoch is not None and not epoch.archived and
                     epoch.child==cli['birth'] and epoch.token==token and
                     epochs.birth_committed(t,role,cli['birth'],token),
                     'DYNTEAM_NATIVE_END_EXACT_COMMITTED_REPLACEMENT_TRANSITION')
            # Cut/role-busy refusal MUST precede any role hold or NO_SEND.
            if cli['end_lease'] is None:
                lease=self.core.membership_fences[t].acquire(role,'NATIVE_END')
                if lease is None:
                    self._note_end_wait(t, 'NATIVE_END_WAIT_MEMBERSHIP')
                    return False
                cli['end_lease']=lease
            if transition is None:
                self.end_transitions[key]=dict(token=token,birth=cli['birth'],
                    state='END_PENDING',since_ns=time.monotonic_ns(),replacement_rolls=0)
            elif transition['token'] != token:
                transition.update(token=token,birth=cli['birth'],state='END_PENDING',
                    replacement_rolls=transition.get('replacement_rolls',0)+1)
            else:
                need(transition['token']==token,'DYNTEAM_NATIVE_END_SAME_CURRENT_TRANSITION')
            self.core.roles.hold_native_end(t,role,anonymous,digest(token))
            if not self._clear(key):
                self._note_end_wait(t, 'NATIVE_END_WAIT_PHYSICAL_CLEAR')
                return False
            self.end_transitions[key]['state']='END_ACKED'
            self._note_end_wait(t, 'NATIVE_END_ACKED_WAIT_ARCHIVE')
            return True
        if event == 'CHILD_EXIT':
            return not same_child_alive(cli['birth']) and self._clear(key)
        if event == 'BEFORE_CLEANUP':
            return (not same_child_alive(cli['birth']) and self._clear(key) and
                    row['archive_durable'] and self.archive(row, cli['birth']) is True)
        if event == 'ARCHIVED_END':
            if token in self.finished:
                epochs=getattr(custody,'sdk_startup_epochs',None)
                if epochs is not None:epochs.note_archived(t,role,row)
                return True
            if same_child_alive(cli['birth']) or not self._clear(key) or not row['archive_durable'] or self.archive(row,cli['birth']) is not True:
                return False
            # Scientific retirement ends the logical agent. Administrative
            # shutdown/disconnect only suspends its runtime; do not fabricate
            # a new scientific birth/budget on normal same-account reconnect.
            if row['end_kind'] in ('RETIRE','TERMINATED'):
                anchor,_ = self.core.original_projection(t,role)
                journal.record_lifecycle('END',role,raw_birth,anchor,physical_terminal=True)
                if (t,role) in self.core.sessions:
                    self.core.sessions.tracks[t].end(role,anonymous,physical_terminal=True)
                self.core.roles.finish_end(t,role,anonymous,physical_models_clear=True,physical_tools_clear=True,
                    native_process_exited=True,durable_metadata=True)
                del self.logical[key]
            cli['archived'] = True
            need(cli['end_lease'] is not None,'DYNTEAM_NATIVE_END_MUST_HAVE_ORIGINAL_MEMBERSHIP_LEASE')
            self.core.membership_fences[t].finish(cli['end_lease'],
                original_control_receipt_sha256=digest(['NATIVE_CLI_ARCHIVED_END_DURABLE',token]))
            cli['end_lease']=None
            self.finished.add(token)
            epochs=getattr(custody,'sdk_startup_epochs',None)
            if epochs is not None:epochs.note_archived(t,role,row)
            transition=self.end_transitions.get(key)
            need(transition is not None and transition['token']==token,
                 'DYNTEAM_ARCHIVED_END_EXACT_PREPARK_TRANSITION')
            if row['end_kind'] in ('TESTER_RELEASE','DISCONNECT'):
                transition['state']='ARCHIVED_WAIT_REPLACEMENT'
            else:
                self.core.roles.complete_native_end(t,role,digest(token))
                del self.end_transitions[key]
            self._note_end_wait(t, 'NATIVE_END_ARCHIVED')
            return True
        raise ValueError('DYNTEAM_NATIVE_LIFECYCLE_EVENT_UNEXPECTED')
