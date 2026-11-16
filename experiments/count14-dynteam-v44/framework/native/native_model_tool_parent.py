"""Exact settled model call -> native MCP parent, never a fabricated TOOL.

This port does NOT assert ACP toolCallId==Responses call_id, infer a Git shell
ancestor, or claim whole-writer physical termination. Those native ports remain
required. Only the existing settled Ledger TOOL is eligible as a parent.
"""
import copy
import hashlib
import json
import math
import struct
import tempfile
import threading
from contextlib import contextmanager
from common import need, Refused, digest, strict, wire, ident, integer, sha

def native_json_arguments_sha256(value):
    """Content match after native JS JSON numeric roundtrip, not raw JSON text.

    The original JS CLI/MCP shim has binary64 Numbers; represent finite numbers
    as normalized IEEE754 bits, preserving every actually distinct JS value.
    Both model JSON and actual MCP JSON use this SAME typed canonical form.
    Strings/bools/null/arrays/objects stay disjoint; no schema/role guard changes.
    Nonfinite/overflow model numbers cannot authorize any native request.
    """
    def canonical(v):
        if v is None:return ['null']
        if type(v)is bool:return ['boolean',v]
        if type(v)in(int,float):
            try:number=float(v)
            except (OverflowError,ValueError):raise Refused('NATIVE_PARENT_ARGUMENT_NONFINITE')from None
            need(math.isfinite(number),'NATIVE_PARENT_ARGUMENT_NONFINITE')
            if number==0:number=0.0 # JSON.stringify(-0) is0.
            return ['number',struct.pack('!d',number).hex()]
        if type(v)is str:return ['string',v]
        if type(v)is list:return ['array',[canonical(x)for x in v]]
        need(type(v)is dict and all(type(k)is str for k in v),'NATIVE_PARENT_ARGUMENT_JSON_TYPE')
        return ['object',[[key,canonical(v[key])]for key in sorted(v)]]
    try:return digest(canonical(value))
    except (UnicodeError,RecursionError):raise Refused('NATIVE_PARENT_ARGUMENT_ENCODING')from None

class CommittedToolStream:
    """Preserve original SSE event bytes/order; hold tools until Ledger commit.

    Text before the first tool still streams. From the first function item on,
    spool privately rather than accumulating role-wide tool argument copies.
    The existing original transport reply bound remains; no new capacity cap.
    A failed/unaccounted stream never releases tool data to native execution.
    """
    def __init__(self, emit, private_home, verified_commit):
        self.emit = emit
        self.verify = verified_commit
        self.home = private_home
        self.spool = None
        self.closed = False
    def __call__(self, event):
        need(not self.closed, 'TOOL_STREAM_ALREADY_CLOSED')
        kind = event.get('type')
        if kind == 'response.failed':
            if self.spool is not None:
                self.spool.close(); self.spool = None
            self.emit(event)
            return
        if self.spool is None and kind == 'response.output_item.added' and event.get('item', {}).get('type') == 'function_call':
            self.spool = tempfile.TemporaryFile(dir=self.home)
        if self.spool is None:
            self.emit(event)
            return
        if kind in ('response.completed', 'response.incomplete'):
            self.verify(event)
            self.spool.seek(0)
            while True:
                head = self.spool.read(8)
                if not head:
                    break
                need(len(head) == 8, 'TOOL_STREAM_SPOOL_FRAME')
                size = struct.unpack('!Q', head)[0]
                raw = self.spool.read(size)
                need(len(raw) == size, 'TOOL_STREAM_SPOOL_TRUNCATED')
                self.emit(strict(raw))
            self.spool.close(); self.spool = None
            self.emit(event)
        else:
            raw = wire(event)  # Capture now: original mapper mutates item later.
            self.spool.write(struct.pack('!Q', len(raw)) + raw)
    def close(self):
        self.closed = True
        if self.spool is not None:
            self.spool.close(); self.spool = None

class NativeModelToolParents:
    """Host-only index in the SAME private Ledger. Does not create requests/tools.

    Registered names are the model-visible `<native MCP server>-<tool>` names
    used by the original entrypoint's original exclusion mapping. No heuristic
    prefix stripping/call-ID equality/first-active selection is used.
    """
    def __init__(self, ledger):
        self.ledger = ledger;self._prime=threading.local();self.cli_receipts=None
        with ledger.tx():
            ledger.db.execute('''CREATE TABLE IF NOT EXISTS native_model_tool_parents(
                trajectory TEXT NOT NULL, role TEXT NOT NULL, generation INTEGER NOT NULL,
                request_id TEXT NOT NULL, call_id TEXT NOT NULL, operation_id TEXT NOT NULL UNIQUE,
                function_name TEXT NOT NULL, arguments_sha256 TEXT,
                PRIMARY KEY(trajectory,role,call_id))''')
            for action in ('UPDATE','DELETE'):
                ledger.db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_native_model_parents_{action.lower()} BEFORE {action} ON native_model_tool_parents BEGIN SELECT RAISE(ABORT,'append only native model tool parents'); END")
            ledger.db.execute('CREATE TABLE IF NOT EXISTS native_model_tool_wire(operation_id TEXT PRIMARY KEY,arguments_raw_sha256 TEXT NOT NULL)')
            for action in ('UPDATE','DELETE'):
                ledger.db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_native_model_wire_{action.lower()} BEFORE {action} ON native_model_tool_wire BEGIN SELECT RAISE(ABORT,'append only native model tool wire'); END")
    def bind_cli_receipts(self, receipts):
        from native_cli_tool_receipt import NativeCliToolReceipts
        need(type(receipts)is NativeCliToolReceipts and receipts.parents is self
             and receipts.ledger is self.ledger and self.cli_receipts is None,
             'NATIVE_PARENT_ORIGINAL_CLI_RECEIPTS_BIND_ONCE')
        with self.ledger.mutex:
            need(self.ledger.db.execute('SELECT COUNT(*) FROM native_model_tool_parents').fetchone()[0]==0,
                 'NATIVE_PARENT_CLI_RECEIPTS_BEFORE_FIRST_MODEL')
            self.cli_receipts=receipts

    @contextmanager
    def identity_prime(self, session):
        """Host-only one-shot native get_me; never a model business permit.

        The ORIGINAL prime runs before listeners/model admission. Its exact
        native session/current-thread object is retained privately; a worker
        cannot request this exemption through MCP JSON or borrow another role.
        """
        from native_mcp_bridge import NativeMcpSession
        from native_gitea_scope import GiteaScope
        from native_mattermost_scope import MattermostScope
        need(type(session)is NativeMcpSession and session.ledger is self.ledger
             and session.parent_tool_provider is self,'NATIVE_PRIME_ORIGINAL_SESSION')
        i=session.identity;guard=session.policy.scope_guard
        need((i.purpose=='gitea'and type(guard)is GiteaScope)
             or (i.purpose=='mattermost'and type(guard)is MattermostScope),
             'NATIVE_PRIME_ORIGINAL_SCOPE_GUARD')
        with self.ledger.mutex:
            self.ledger._identity(i.trajectory,i.role,i.generation)
            need(not hasattr(self._prime,'value') and i.generation==1
                 and self.ledger.account(i.trajectory)['state']=='RUNNING'
                 and not self.ledger.admission_fault(i.trajectory)
                 and not guard.ready(i)
                 and self.ledger.native_services.get(session.scope)is session,
                 'NATIVE_PRIME_FIRST_START_ORIGINAL_CUSTODY')
            need(self.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=?',(i.trajectory,)).fetchone()[0]==0,
                 'NATIVE_PRIME_BEFORE_ANY_MODEL')
            for event in self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=?AND kind='NATIVE_IDENTITY_PRIME_AUTHORIZED'",(i.trajectory,)):
                need(strict(event[0]).get('scope')!=session.scope,'NATIVE_PRIME_ONCE_NO_RETRY')
            try:
                with self.ledger.tx():self.ledger.event(i.trajectory,'NATIVE_IDENTITY_PRIME_AUTHORIZED',
                    {'scope':session.scope,'role':i.role,'purpose':i.purpose,'generation':1,'tool':'get_me'})
            except Exception:
                self.ledger.latch_fault(i.trajectory,'NATIVE_PRIME_AUTHORIZATION_STORAGE_UNKNOWN');raise
            permit={'session':session,'consumed':False};self._prime.value=permit
        try:
            yield
            need(permit['consumed']and guard.ready(i),'NATIVE_PRIME_NATIVE_IDENTITY_NOT_COMPLETED')
            with self.ledger.tx():self.ledger.event(i.trajectory,'NATIVE_IDENTITY_PRIME_COMPLETE',
                {'scope':session.scope,'role':i.role,'purpose':i.purpose,'generation':1,'worker_listener_released':False})
        except BaseException:
            self.ledger.latch_fault(i.trajectory,'NATIVE_PRIME_FAILED_RETAIN_NO_RETRY');raise
        finally:del self._prime.value
    def __call__(self, binding):
        # The legacy binding-only callback has no exact MCP request. In
        # particular do not accidentally install this as a Git parent guesser.
        raise Refused('NATIVE_MODEL_PARENT_REQUEST_CONTEXT_REQUIRED')
    def git_parent(self,binding,*,cli_ticket):
        """Explicit original callback ticket only; legacy binding guess stays refused.

        This active-callback branch does NOT yet authorize future Git from a
        retained background writer after callback return. That needs the exact
        retained-lineage/admission port, not a relaxed ACTIVE parent check.
        """
        from native_git_http import NativeGitHttpBinding
        from native_cli_tool_receipt import NativeCliToolReceipts
        need(type(binding)is NativeGitHttpBinding and type(self.cli_receipts)is NativeCliToolReceipts
             and self.cli_receipts.parents is self and self.cli_receipts.ledger is self.ledger,
             'NATIVE_GIT_PARENT_ORIGINAL_BINDING_AND_CLI_SERVICE')
        return self.cli_receipts.git_parent(binding,cli_ticket)
    def register_committed_response(self, rid, identity, response):
        t, role = identity
        calls = [item for item in response.get('output', []) if item.get('type') == 'function_call']
        with self.ledger.tx():
            r = self.ledger.db.execute('SELECT * FROM requests WHERE id=?', (rid,)).fetchone()
            need(r is not None and r['state'] == 'SETTLED' and (r['trajectory'], r['role']) == identity,
                 'NATIVE_MODEL_PARENT_SETTLED_REQUEST_REQUIRED')
            need((r['input'], r['output']) == (response['usage']['input_tokens'], response['usage']['output_tokens']),
                 'NATIVE_MODEL_PARENT_USAGE_IDENTITY')
            for item in calls:
                call = item['call_id']; name = item['name']
                need(type(call) is str and call and type(name) is str and name, 'NATIVE_MODEL_PARENT_CALL_FIELDS')
                op = 'tool-' + digest({'rid': rid, 'call_id': call})
                operation = self.ledger.db.execute('SELECT * FROM operations WHERE id=?', (op,)).fetchone()
                need(operation is not None and operation['kind'] == 'TOOL' and operation['state'] == 'ACTIVE'
                     and (operation['trajectory'], operation['role'], operation['generation'], operation['parent'])
                     == (t, role, r['generation'], rid), 'NATIVE_MODEL_PARENT_REAL_TOOL_REQUIRED')
                # Malformed model arguments retain their actual TOOL/cost; they
                # cannot authorize a native valid-JSON request by guessing. Do
                # not turn a normal model argument error into a fake operation.
                try:
                    args = strict(item['arguments'])
                    args_sha = native_json_arguments_sha256(args) if type(args) is dict else None
                except Refused:
                    args_sha = None
                self.ledger.db.execute('INSERT INTO native_model_tool_parents VALUES(?,?,?,?,?,?,?,?)',
                    (t, role, r['generation'], rid, call, op, name, args_sha))
                self.ledger.db.execute('INSERT INTO native_model_tool_wire VALUES(?,?)',
                    (op,hashlib.sha256(item['arguments'].encode('utf-8')).hexdigest()))
            if calls:
                self.ledger.event(t, 'NATIVE_MODEL_TOOL_PARENTS_INDEXED',
                                  {'request_id': rid, 'role': role, 'generation': r['generation'], 'tools': len(calls)})
    def prepare_mcp_message(self, binding, message):
        """Consume only the private native invocation capability, not tool data.

        Exact native integer progressToken is consumed independently first.
        Policy still sees its ORIGINAL exact business request shape. Other metadata,
        cross-scope names/args and JSON-RPC extension keys remain refused.
        Host-only identity prime and initial protocol negotiation are unchanged.
        """
        from native_mcp_policy import normalize_protocol_progress
        message=normalize_protocol_progress(message)
        need(type(message)is dict,'MCP_JSONRPC_REQUEST')
        if self.cli_receipts is None or message.get('method')!='tools/call':return message,None
        if getattr(self._prime,'value',None)is not None:return message,None
        params=message.get('params')
        need(type(params)is dict and type(params.get('_meta'))is dict
             and set(params['_meta'])=={'count14/original-cli-tool'},
             'NATIVE_PARENT_PRIVATE_CLI_TICKET_REQUIRED')
        ticket=sha(params['_meta']['count14/original-cli-tool'])
        return {**message,'params':{k:v for k,v in params.items()if k!='_meta'}},ticket
    def mcp_parent(self, binding, message, *, cli_ticket=None):
        t, role, generation, purpose = binding.trajectory, binding.role, binding.generation, binding.purpose
        need(purpose in ('gitea', 'mattermost', 'board'), 'NATIVE_MODEL_PARENT_NATIVE_PURPOSE')
        with self.ledger.mutex:
            self.ledger._identity(t, role, generation)
            need(not self.ledger.admission_fault(t), 'NATIVE_MODEL_PARENT_SHARED_FAULT')
            method = message.get('method')
            if method in ('initialize', 'tools/list'):
                # Actual protocol negotiation, NOT a model business tool. A
                # draining trajectory cannot gain a new unparented operation.
                need(self.ledger.account(t)['state'] == 'RUNNING', 'NATIVE_MODEL_PARENT_HANDSHAKE_CLOSED')
                return None
            need(method == 'tools/call' and type(message.get('params')) is dict, 'NATIVE_MODEL_PARENT_TOOLS_CALL')
            params = message['params']; name = params.get('name'); args = params.get('arguments', {})
            ident(name); need(type(args) is dict, 'NATIVE_MODEL_PARENT_ARGUMENT_OBJECT')
            prime=getattr(self._prime,'value',None)
            if prime is not None:
                session=prime['session']
                need(session.identity is binding and session.ledger is self.ledger
                     and session.parent_tool_provider is self and not prime['consumed']
                     and name=='get_me'and args=={} and set(params)=={'name','arguments'}
                     and generation==1 and self.ledger.account(t)['state']=='RUNNING'
                     and self.ledger.native_services.get(session.scope)is session,
                     'NATIVE_PRIME_EXACT_HOST_GET_ME_ONLY')
                with self.ledger.tx():self.ledger.event(t,'NATIVE_IDENTITY_PRIME_DISPATCHED',
                    {'scope':session.scope,'role':role,'purpose':purpose,'generation':1,'tool':'get_me'})
                prime['consumed']=True;return None
            qualified = purpose + '-' + name
            if self.cli_receipts is not None:
                from native_cli_tool_receipt import NativeCliToolReceipts
                need(type(self.cli_receipts)is NativeCliToolReceipts and self.cli_receipts.parents is self
                     and self.cli_receipts.ledger is self.ledger,'NATIVE_PARENT_ORIGINAL_CLI_SERVICE_CHANGED')
                need(cli_ticket is not None,'NATIVE_PARENT_PRIVATE_CLI_TICKET_REQUIRED')
                return self.cli_receipts.mcp_parent(t,role,generation,qualified,native_json_arguments_sha256(args),cli_ticket)
            rows = self.ledger.db.execute('''SELECT p.operation_id FROM native_model_tool_parents p
                JOIN requests r ON r.id=p.request_id JOIN operations o ON o.id=p.operation_id
                WHERE p.trajectory=? AND p.role=? AND p.generation=? AND p.function_name=? AND p.arguments_sha256=?
                AND r.state='SETTLED' AND r.trajectory=p.trajectory AND r.role=p.role AND r.generation=p.generation
                AND o.kind='TOOL' AND o.state='ACTIVE' AND o.parent=p.request_id
                AND o.trajectory=p.trajectory AND o.role=p.role AND o.generation=p.generation''',
                (t, role, generation, qualified, native_json_arguments_sha256(args))).fetchall()
            need(len(rows) == 1, 'NATIVE_MODEL_PARENT_NO_UNIQUE_EXACT_CALL')
            return rows[0]['operation_id']
