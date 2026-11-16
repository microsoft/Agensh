"""Fixed ACP control-field observer, no body/argument/result exposure.

Install BEFORE forwarding the first byte to an original native CLI child.
Feed the same complete ordered protocol lines from the existing bridge's two
observe_* sites. No stream/socket/dispatcher replacement, model/accounting or
command parsing. A malformed control stream remains permanently fail-closed.
"""
import json
import threading

SCHEMA='count14-native-cli-control-counts-v1'
FIELDS={'schema','sequence','pending_prompts','pending_tools','control_complete','observer_fault'}


def checked_control(value):
    if not (type(value) is dict and set(value)==FIELDS and value['schema']==SCHEMA and
            type(value['sequence']) is int and value['sequence']>=0 and
            all(type(value[k]) is int and 0<=value[k]<=65536 for k in ('pending_prompts','pending_tools')) and
            type(value['control_complete']) is bool and type(value['observer_fault']) is bool):
        raise ValueError('DYNTEAM_EXACT_NATIVE_CONTROL_COUNTER_FIELDS')
    return value


class NativeToolControlObserver:
    def __init__(self):
        self.lock=threading.Lock();self.prompts=set();self.tools=set()
        self.sequence=0;self.fault=False

    @staticmethod
    def _id(value):
        return (type(value) is int and 0<=value<2**63 or
                type(value) is str and 0<len(value)<=256)

    def _line(self,line,direction):
        try:
            if type(line) not in (str,bytes) or len(line)>16*1024*1024:
                raise ValueError('DYNTEAM_ACP_CONTROL_LINE_BOUND')
            value=json.loads(line)
            if type(value) is not dict:raise ValueError('DYNTEAM_ACP_CONTROL_OBJECT')
            method=value.get('method')
            if direction=='input':
                if method=='session/prompt':
                    request_id=value.get('id')
                    if not self._id(request_id) or request_id in self.prompts:
                        raise ValueError('DYNTEAM_ACP_CONTROL_EXACT_PROMPT_ID')
                    self.prompts.add(request_id)
                return
            if method is None:
                request_id=value.get('id')
                if self._id(request_id):self.prompts.discard(request_id)
                return
            if method!='session/update':return
            params=value.get('params')
            if type(params) is not dict:raise ValueError('DYNTEAM_ACP_CONTROL_UPDATE_PARAMS')
            update=params.get('update')
            if type(update) is not dict:raise ValueError('DYNTEAM_ACP_CONTROL_UPDATE_OBJECT')
            kind=update.get('sessionUpdate')
            if kind not in ('tool_call','tool_call_update'):return
            session_id=params.get('sessionId')
            if type(session_id) is not str or not self._id(session_id):
                raise ValueError('DYNTEAM_ACP_CONTROL_EXACT_SESSION_ID')
            tool_id=update.get('toolCallId');status=update.get('status')
            if type(tool_id) is not str or not self._id(tool_id):
                raise ValueError('DYNTEAM_ACP_CONTROL_EXACT_TOOL_ID')
            key=(session_id,tool_id)
            if status in ('completed','failed'):
                self.tools.discard(key)
            elif status in ('pending','in_progress') or (kind=='tool_call' and status is None):
                self.tools.add(key)
            elif status is None and kind=='tool_call_update':
                # Native ACP permits content-only updates, never a completion.
                pass
            else:raise ValueError('DYNTEAM_ACP_CONTROL_UNKNOWN_TOOL_STATUS')
            if max(len(self.prompts),len(self.tools))>65536:
                raise ValueError('DYNTEAM_ACP_CONTROL_COUNTER_BOUND')
        except Exception:
            self.fault=True # fixed Boolean only; no exception/message stored

    def observe(self,lines,direction):
        if direction not in ('input','output') or type(lines) not in (list,tuple):
            raise ValueError('DYNTEAM_ACP_CONTROL_FIXED_STREAM_DIRECTION')
        with self.lock:
            for line in lines:
                if line in (b'',''):continue
                self.sequence+=1;self._line(line,direction)

    def snapshot(self):
        with self.lock:
            return dict(schema=SCHEMA,sequence=self.sequence,pending_prompts=len(self.prompts),
                pending_tools=len(self.tools),control_complete=not self.fault,observer_fault=self.fault)
