"""Fixed OWN framework lifecycle fields only; no messages/locals/model data."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import threading
BASE = '70e2ca54c078597e3314755064d2ef1a83344c8e'
FIELDS = {'schema', 'source_commit', 'trajectory_id', 'role_slot', 'logical_birth_sha256', 'native_turn_sha256', 'event', 'child_namespace_pid', 'child_start_ticks', 'child_running', 'archive_durable', 'end_kind'}
EVENTS = {'BRIDGE_READY', 'CLI_BIRTH', 'END_REQUEST', 'CHILD_EXIT', 'BEFORE_CLEANUP', 'ARCHIVED_END'}
KINDS = {'NONE', 'RETIRE', 'TERMINATED', 'SHUTDOWN', 'DISCONNECT', 'TESTER_RELEASE', 'STARTUP_RECOVERY', 'OTHER'}
_COUNT14_CONTROL_SCHEMA = 'count14-native-cli-control-counts-v1'
_COUNT14_CONTROL_FIELDS = {'schema', 'sequence', 'pending_prompts', 'pending_tools', 'control_complete', 'observer_fault'}

def _count14_checked_tool_control(value):
    if not (type(value) is dict and set(value) == _COUNT14_CONTROL_FIELDS and (value['schema'] == _COUNT14_CONTROL_SCHEMA) and (type(value['sequence']) is int) and (value['sequence'] >= 0) and all((type(value[k]) is int and 0 <= value[k] <= 65536 for k in ('pending_prompts', 'pending_tools'))) and (type(value['control_complete']) is bool) and (type(value['observer_fault']) is bool)):
        raise ValueError('DYNTEAM_EXACT_NATIVE_CONTROL_COUNTER_FIELDS')
    return value

def checked_lifecycle(row):
    sha = lambda x: type(x) is str and len(x) == 64 and all((c in '0123456789abcdef' for c in x))
    role = row.get('role_slot') if type(row) is dict else None
    roles = {f'worker-{i:02d}' for i in range(32)} | {'checker-00', 'tester-00', 'racing-background-00'} | {f'racing-player-{i:02d}' for i in range(7)}
    if not (type(row) is dict and set(row) in (FIELDS, FIELDS | {'tool_control'}) and (row['schema'] == 'count14-native-bridge-lifecycle-v1') and (row['source_commit'] == BASE) and (type(row['trajectory_id']) is str) and (0 < len(row['trajectory_id']) <= 512) and (role in roles) and all((sha(row[k]) for k in ('logical_birth_sha256', 'native_turn_sha256'))) and (row['event'] in EVENTS) and (row['end_kind'] in KINDS) and (type(row['child_namespace_pid']) is int) and (row['child_namespace_pid'] >= 0) and (type(row['child_start_ticks']) is int) and (row['child_start_ticks'] >= 0) and (type(row['child_running']) is bool) and (type(row['archive_durable']) is bool) and ((row['child_namespace_pid'] == 0) == (row['child_start_ticks'] == 0))):
        raise ValueError('DYNTEAM_EXACT_NATIVE_BRIDGE_LIFECYCLE_FIELDS')
    if row['event']=='BRIDGE_READY' and not (
            row['child_namespace_pid']==row['child_start_ticks']==0 and
            row['child_running'] is False and row['archive_durable'] is False and
            row['end_kind']=='NONE' and row.get('tool_control') is None):
        raise ValueError('DYNTEAM_BRIDGE_READY_METADATA_ONLY_NO_CLI_OR_ARCHIVE_CLAIM')
    if 'tool_control' in row and row['tool_control'] is not None:
        _count14_checked_tool_control(row['tool_control'])
    return row

@dataclass
class LifecycleTicket:
    row: dict
    peer: tuple
    complete: threading.Event
    result: bool | None = None

class NativeBridgeInbox:
    def __init__(self, *, timeout=30):
        from native_control_inbox import OwnerControlQueue
        self._queue=OwnerControlQueue(checked=checked_lifecycle,timeout=timeout)
        self.timeout,self.lock,self.pending=self._queue.timeout,self._queue.lock,self._queue.pending

    def receive(self,row,peer):
        return self._queue.receive(row,peer)

    def poll_once(self,handler):
        return self._queue.poll_once(handler)['processed']

    def public(self):
        return self._queue.public()
