"""Bounded framework-only control for the ORIGINAL native spawn process."""
from collections import deque
from dataclasses import dataclass
import threading

BASE='70e2ca54c078597e3314755064d2ef1a83344c8e'
FIELDS={'schema','source_commit','trajectory_id','role_slot','event','worker_slot','spawn_ordinal',
        'operation_id','reuse','succeeded','container_ids'}


def checked_spawn(row):
    if not(type(row) is dict and set(row)==FIELDS and row['schema']=='count14-native-spawn-control-v2' and
        row['source_commit']==BASE and type(row['trajectory_id']) is str and 0<len(row['trajectory_id'])<=512 and
        row['role_slot']=='worker-00' and row['event'] in ('READ','BEGIN','FINISH','RETIRE_BEGIN','RETIRE_POLL') and
        type(row['worker_slot']) is int and 0<=row['worker_slot']<=32 and
        type(row['spawn_ordinal']) is int and row['spawn_ordinal']>=0 and
        type(row['operation_id']) is str and len(row['operation_id'])==32 and
        all(c in '0123456789abcdef' for c in row['operation_id']) and
        type(row['reuse']) is bool and type(row['succeeded']) is bool and
        type(row['container_ids']) is list and len(row['container_ids'])<=2 and
        all(type(cid) is str and len(cid)==64 and all(c in '0123456789abcdef' for c in cid) for cid in row['container_ids']) and
        (row['event']=='RETIRE_BEGIN' and len(set(row['container_ids']))==2 or
         row['event']!='RETIRE_BEGIN' and row['container_ids']==[]) and
        (row['event']!='READ' or row['worker_slot']==row['spawn_ordinal']==0 and row['operation_id']=='0'*32) and
        (row['event']=='READ' or row['worker_slot']>=1 and row['spawn_ordinal']>=1)):
        raise ValueError('DYNTEAM_EXACT_NATIVE_SPAWN_CONTROL_FIELDS')
    return row


@dataclass
class Ticket:
    row:dict
    peer:tuple
    complete:threading.Event
    result:dict|None=None


def _checked_spawn_control_result(value):
    if value is None:return None
    if not(type(value) is dict and set(value)=={'status','active_seconds','operation_id'} and
           value['status'] in ('RUNNING','HOLD','FINAL','ALLOW','RETAINED','DONE') and
           type(value['active_seconds']) is int and value['active_seconds']>=0 and
           type(value['operation_id']) is str and len(value['operation_id'])==32):
        raise ValueError('DYNTEAM_NATIVE_SPAWN_RESULT_REQUIRED')
    return dict(value)


class NativeSpawnInbox:
    def __init__(self, *, timeout=30):
        from native_control_inbox import OwnerControlQueue
        self._queue=OwnerControlQueue(checked=checked_spawn,timeout=timeout,maximum=64,
                                     result_normalizer=_checked_spawn_control_result)
        self.timeout,self.lock,self.pending=self._queue.timeout,self._queue.lock,self._queue.pending

    def receive(self,row,peer):return self._queue.receive(row,peer)
    def poll_once(self,handler):return self._queue.poll_once(handler)['processed']
    def public(self):return self._queue.public()
