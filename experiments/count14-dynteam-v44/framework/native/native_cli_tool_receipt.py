"""Exact host-registered CLI peer -> ORIGINAL committed TOOL callback receipts.

This never completes a TOOL, declares a shell/daemon dead or authorizes a model.
Native MCP physical terminal remains independent. No worker-supplied PID, ACP
status, first-active call guess, result text, exception message or tool replay.
"""
from pathlib import Path
import hashlib, os, re, secrets, socketserver, stat, threading, uuid
from common import need, Refused, digest, sha, wire, strict, private_dir, hash_file, stamp
from bridge import process_identity, peer_identity
from native_model_tool_parent import NativeModelToolParents
from native_control_custody import NativeAcceptedControls
SCHEMA='agensh-original-cli-tool-receipt-v1'
MAX_FRAME=16384

def cli_peer(pid):
    """Trusted launch registration only, not a worker JSON claim of readiness."""
    identity=process_identity(pid);p=Path('/proc')/str(pid)
    def attributes():
        st=p.stat()
        return {'uid':st.st_uid,'gid':st.st_gid,
                'pid_namespace_inode':os.stat(p/'ns/pid').st_ino,
                'net_namespace_inode':os.stat(p/'ns/net').st_ino}
    before=attributes()
    # /proc/PID/exe is an intentional kernel magic link, not an ordinary
    # untrusted pathname. resolve() would reinterpret its mount-namespace path
    # in the host and can read a wrong same-name binary (or fail ENOENT).
    # Open that exact live process image directly; never create a host alias.
    fd=os.open(p/'exe',os.O_RDONLY|os.O_CLOEXEC)
    try:
        start=os.fstat(fd);need(stat.S_ISREG(start.st_mode),'CLI_PEER_EXE_REGULAR_FILE')
        hasher=hashlib.sha256();size=0
        for block in iter(lambda:os.read(fd,1024*1024),b''):
            size+=len(block);hasher.update(block)
        need(stamp(start)==stamp(os.fstat(fd))and size==start.st_size,
             'CLI_PEER_EXE_CHANGED_DURING_READ')
        # Same PID/start/boot alone does not detect execve. Reopen the original
        # magic link and check the actual current image's fd identity too.
        current=os.open(p/'exe',os.O_RDONLY|os.O_CLOEXEC)
        try:need(stamp(start)==stamp(os.fstat(current)),'CLI_PEER_EXE_CURRENT_IMAGE_CHANGED')
        finally:os.close(current)
        need(process_identity(pid)==identity and attributes()==before,
             'CLI_PEER_PROCESS_OR_NAMESPACE_CHANGED')
        need(stamp(start)==stamp(os.fstat(fd)),'CLI_PEER_EXE_CHANGED_AFTER_VERIFY')
        return {**identity,**before,'executable_sha256':hasher.hexdigest()}
    finally:os.close(fd)

class NativeCliToolReceipts:
    def __init__(self, parents):
        need(type(parents)is NativeModelToolParents,'CLI_RECEIPT_ORIGINAL_MODEL_INDEX')
        self.parents=parents;self.ledger=parents.ledger;self.lock=threading.RLock()
        self.condition=threading.Condition(self.lock);self.peers={};self.closed=False;self.shell_contexts={}
        with self.ledger.tx():
            self.ledger.db.execute('''CREATE TABLE IF NOT EXISTS native_cli_tool_starts(
                ticket TEXT PRIMARY KEY,trajectory TEXT NOT NULL,role TEXT NOT NULL,generation INTEGER NOT NULL,
                operation_id TEXT NOT NULL UNIQUE,request_id TEXT NOT NULL,call_id TEXT NOT NULL,
                native_call_id TEXT NOT NULL,function_name TEXT NOT NULL,arguments_sha256 TEXT,
                mode TEXT NOT NULL,parent_ticket TEXT,peer_sha256 TEXT NOT NULL)''')
            self.ledger.db.execute('''CREATE TABLE IF NOT EXISTS native_cli_tool_returns(
                ticket TEXT PRIMARY KEY,outcome TEXT NOT NULL,exception_type TEXT,receipt_sha256 TEXT NOT NULL)''')
            for table in ('native_cli_tool_starts','native_cli_tool_returns'):
                for action in ('UPDATE','DELETE'):
                    self.ledger.db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append only'); END")
        parents.bind_cli_receipts(self)
    def register_peer(self, identity, pid, *, expected_peer_sha256):
        """Owner calls before that role's first model, after actual CLI launch.

        Source/image/read-only overlay provenance is the cold launcher's separate
        mandatory proof; a matching PID alone does not prove original app bytes.
        This method does NOT infer readiness/version/provenance from the peer.
        """
        need(type(identity)is tuple and len(identity)==2,'CLI_RECEIPT_HOST_ROLE_IDENTITY')
        with self.condition,self.ledger.mutex:
            need(not self.closed and identity not in self.peers,'CLI_RECEIPT_PEER_BIND_ONCE')
            t,role=identity;f=self.ledger.frontier(t);self.ledger._identity(t,role,f['generation'])
            need(f['generation']==1 and self.ledger.account(t)['state']=='RUNNING'
                 and self.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=?AND role=?',identity).fetchone()[0]==0,
                 'CLI_RECEIPT_FIRSTSTART_BEFORE_MODEL')
            peer=cli_peer(pid);need(digest(peer)==sha(expected_peer_sha256),'CLI_RECEIPT_EXACT_LAUNCH_PEER_PIN')
            need(all(p['pid']!=peer['pid']for p in self.peers.values()),'CLI_RECEIPT_ONE_NATIVE_PEER_PER_ROLE')
            self.peers[identity]=peer
            try:
                with self.ledger.tx():self.ledger.event(t,'NATIVE_CLI_TOOL_PEER_REGISTERED',{'role':role,'peer_sha256':expected_peer_sha256})
            except BaseException:
                self.ledger.latch_fault(t,'CLI_RECEIPT_PEER_STORAGE_UNKNOWN');raise
            return expected_peer_sha256
    def _peer(self, identity, observed):
        # Unauthorized sibling processes cannot fault/select another trajectory.
        need(identity in self.peers,'CLI_RECEIPT_REGISTERED_ORIGINAL_PEER_REQUIRED')
        p=self.peers[identity]
        need(type(observed)is dict and all(observed.get(k)==p[k]for k in ('pid','uid','gid','pid_namespace_inode')),
             'CLI_RECEIPT_EXACT_ORIGINAL_PEER_ONLY')
        try:need(cli_peer(p['pid'])==p,'CLI_RECEIPT_ORIGINAL_PEER_CHANGED')
        except BaseException:
            self.ledger.latch_fault(identity[0],'CLI_RECEIPT_PEER_CUSTODY_UNKNOWN');raise
        return p
    def handle(self, identity, observed, value):
        self._peer(identity,observed)
        try:
            need(type(value)is dict and value.get('schema')==SCHEMA,'CLI_RECEIPT_SCHEMA')
            with self.condition:
                need(not self.closed,'CLI_RECEIPT_SERVICE_CLOSED')
                if value.get('phase') in ('SHELL_ALLOCATE','SHELL_PREPARE'):
                    need(identity in self.shell_contexts,'SHELL_CONTEXT_ORIGINAL_HOST_BINDING_REQUIRED')
                    from native_shell_context import NativeShellContexts
                    context=self.shell_contexts[identity]
                    need(type(context)is NativeShellContexts and context.receipts is self,'SHELL_CONTEXT_ORIGINAL_HOST_OBJECT')
                    return context.handle(identity,value)
                if value.get('phase')=='BEGIN':return self._begin(identity,observed,value)
                need(value.get('phase')=='RETURN','CLI_RECEIPT_PHASE')
                return self._return(identity,value)
        except BaseException:
            self.ledger.latch_fault(identity[0],'CLI_RECEIPT_NATIVE_EXECUTION_CUSTODY_UNKNOWN')
            self.condition.acquire();self.condition.notify_all();self.condition.release();raise
    def _begin(self,identity,observed,value):
        fields={'schema','phase','original_call_id','native_plan_call_id','function_name','native_function_name',
                'arguments_raw_sha256','arguments_sha256','mode','parent_ticket'}
        need(set(value)==fields,'CLI_RECEIPT_BEGIN_FIELDS')
        for k in ('original_call_id','native_plan_call_id','function_name','native_function_name'):
            need(type(value[k])is str and 0<len(value[k].encode())<=512,'CLI_RECEIPT_BOUNDED_ORIGINAL_ID_NAME')
        need(value['mode']in('CALLBACK','NATIVE_PLAN_NO_EXECUTION'),'CLI_RECEIPT_EXECUTION_MODE')
        sha(value['arguments_raw_sha256'])
        if value['mode']=='CALLBACK':sha(value['arguments_sha256'])
        else:need(value['arguments_sha256']is None,'CLI_RECEIPT_NOEXEC_ARGUMENTS')
        if value['parent_ticket']is not None:sha(value['parent_ticket'])
        t,role=identity
        # Exact host-minted invocation tickets are propagated by the original
        # native MCP client's metadata seam. Never serialize identical nested
        # callbacks behind their own live ancestors or pick a first/leaf match.
        self._peer(identity,observed)
        with self.ledger.mutex:
            need(not self.ledger.admission_fault(t),'CLI_RECEIPT_SHARED_FAULT')
            f=self.ledger.frontier(t);self.ledger._identity(t,role,f['generation'])
            need(f['state']in('RUNNING','DRAINING'),'CLI_RECEIPT_ORIGINAL_ACCEPTED_TOOL_STAGE')
            row=self.ledger.db.execute('''SELECT p.*,o.state,o.kind,o.parent,w.arguments_raw_sha256
                FROM native_model_tool_parents p JOIN operations o ON o.id=p.operation_id
                JOIN requests r ON r.id=p.request_id JOIN native_model_tool_wire w ON w.operation_id=p.operation_id
                WHERE p.trajectory=?AND p.role=?AND p.call_id=?AND r.state='SETTLED'
                AND r.trajectory=p.trajectory AND r.role=p.role AND r.generation=p.generation
                AND o.trajectory=p.trajectory AND o.role=p.role AND o.generation=p.generation''',
                (*identity,value['original_call_id'])).fetchone()
            need(row is not None and row['kind']=='TOOL'and row['state']=='ACTIVE'
                 and row['parent']==row['request_id']and row['generation']==f['generation'],
                 'CLI_RECEIPT_EXACT_SETTLED_ORIGINAL_TOOL_REQUIRED')
            need(row['function_name']==value['function_name']==value['native_function_name']
                 and row['arguments_raw_sha256']==value['arguments_raw_sha256'],
                 'CLI_RECEIPT_ORIGINAL_NAME_AND_RAW_ARGUMENTS')
            if value['mode']=='CALLBACK':need(row['arguments_sha256']==value['arguments_sha256'], 'CLI_RECEIPT_ORIGINAL_CALLBACK_ARGUMENTS')
            need(self.ledger.db.execute('SELECT 1 FROM native_cli_tool_starts WHERE operation_id=?',(row['operation_id'],)).fetchone()is None,
                 'CLI_RECEIPT_EXECUTION_ONCE_NO_RETRY')
            if value['parent_ticket']is not None:
                parent=self.ledger.db.execute('''SELECT s.* FROM native_cli_tool_starts s
                    LEFT JOIN native_cli_tool_returns e ON e.ticket=s.ticket WHERE s.ticket=?AND e.ticket IS NULL''',(value['parent_ticket'],)).fetchone()
                need(parent is not None and parent['mode']=='CALLBACK'
                     and (parent['trajectory'],parent['role'],parent['generation'])==(t,role,f['generation']),
                     'CLI_RECEIPT_EXACT_LIVE_NESTED_CALLBACK_PARENT')
            ticket=secrets.token_hex(32);peer_sha=digest(self.peers[identity]);values=(ticket,t,role,row['generation'],row['operation_id'],row['request_id'],row['call_id'],value['native_plan_call_id'],row['function_name'],value['arguments_sha256'],value['mode'],value['parent_ticket'],peer_sha)
            try:
                with self.ledger.tx():
                    self.ledger.db.execute('INSERT INTO native_cli_tool_starts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',values)
                    self.ledger.event(t,'NATIVE_CLI_ORIGINAL_TOOL_CALLBACK_STARTED',{'role':role,'operation_id':row['operation_id'],'request_id':row['request_id'],'call_id':row['call_id'],'native_plan_call_id':value['native_plan_call_id'],'mode':value['mode'],'peer_sha256':peer_sha})
            except BaseException:
                self.ledger.latch_fault(t,'CLI_RECEIPT_BEGIN_STORAGE_UNKNOWN');raise
            return {'ok':True,'ticket':ticket}
    def _return(self,identity,value):
        need(set(value)=={'schema','phase','ticket','outcome','exception_type'},'CLI_RECEIPT_RETURN_FIELDS');sha(value['ticket'])
        need(value['outcome']in('RETURN','THROW','NATIVE_PLAN_NO_EXECUTION'),'CLI_RECEIPT_RETURN_OUTCOME')
        if value['outcome']=='THROW':need(type(value['exception_type'])is str and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,159}',value['exception_type']), 'CLI_RECEIPT_EXCEPTION_TYPE_ONLY')
        else:need(value['exception_type']is None,'CLI_RECEIPT_NO_EXCEPTION_MESSAGE')
        with self.ledger.mutex:
            need(not self.ledger.admission_fault(identity[0]),'CLI_RECEIPT_SHARED_FAULT')
            row=self.ledger.db.execute('SELECT * FROM native_cli_tool_starts WHERE ticket=?',(value['ticket'],)).fetchone()
            need(row is not None and (row['trajectory'],row['role'])==identity,'CLI_RECEIPT_EXACT_ORIGINAL_RETURN_TICKET')
            need(self.ledger.db.execute('SELECT 1 FROM native_cli_tool_returns WHERE ticket=?',(value['ticket'],)).fetchone()is None,'CLI_RECEIPT_RETURN_ONCE_NO_RETRY')
            need((row['mode']=='NATIVE_PLAN_NO_EXECUTION')==(value['outcome']=='NATIVE_PLAN_NO_EXECUTION'), 'CLI_RECEIPT_ORIGINAL_MODE_RETURN')
            proof={'trajectory':row['trajectory'],'role':row['role'],'generation':row['generation'],
                   'operation_id':row['operation_id'],'request_id':row['request_id'],'call_id':row['call_id'],
                   'native_plan_call_id':row['native_call_id'],'mode':row['mode'],'peer_sha256':row['peer_sha256'],
                   'outcome':value['outcome'],'exception_type':value['exception_type']}
            receipt=digest(proof)
            try:
                with self.ledger.tx():
                    self.ledger.db.execute('INSERT INTO native_cli_tool_returns VALUES(?,?,?,?)',(value['ticket'],value['outcome'],value['exception_type'],receipt))
                    self.ledger.event(identity[0],'NATIVE_CLI_ORIGINAL_TOOL_CALLBACK_RETURNED',{**proof,'receipt_sha256':receipt,'physical_terminal_not_claimed':True})
            except BaseException:
                self.ledger.latch_fault(identity[0],'CLI_RECEIPT_RETURN_STORAGE_UNKNOWN');raise
        self.condition.notify_all();return {'ok':True,'receipt_sha256':receipt}
    def mcp_parent(self,t,role,generation,name,args_sha,ticket):
        with self.ledger.mutex:
            self._peer((t,role),self.peers.get((t,role),{}))
            sha(ticket)
            rows=self.ledger.db.execute('''SELECT p.operation_id FROM native_model_tool_parents p
                JOIN native_cli_tool_starts s ON s.operation_id=p.operation_id
                LEFT JOIN native_cli_tool_returns e ON e.ticket=s.ticket
                JOIN operations o ON o.id=p.operation_id JOIN requests r ON r.id=p.request_id
                WHERE p.trajectory=?AND p.role=?AND p.generation=?AND p.function_name=?AND p.arguments_sha256=?
                AND s.ticket=?AND s.mode='CALLBACK'AND e.ticket IS NULL AND o.kind='TOOL'AND o.state='ACTIVE'
                AND o.parent=p.request_id AND r.state='SETTLED' ''',(t,role,generation,name,args_sha,ticket)).fetchall()
            need(len(rows)==1,'CLI_RECEIPT_MCP_EXACT_EXECUTING_ORIGINAL_REQUIRED');return rows[0][0]
    def git_parent(self,binding,ticket):
        """Exact host-issued live original callback, never first/last/leaf TOOL."""
        from native_git_http import NativeGitHttpBinding
        need(type(binding)is NativeGitHttpBinding,'CLI_RECEIPT_GIT_ORIGINAL_HOST_BINDING')
        t,role,generation=binding.trajectory,binding.role,binding.generation
        with self.ledger.mutex:
            self._peer((t,role),self.peers.get((t,role),{}));sha(ticket)
            self.ledger._identity(t,role,generation)
            need(not self.ledger.admission_fault(t),'CLI_RECEIPT_GIT_SHARED_FAULT')
            rows=self.ledger.db.execute("""SELECT p.operation_id FROM native_model_tool_parents p
                JOIN native_cli_tool_starts s ON s.operation_id=p.operation_id
                LEFT JOIN native_cli_tool_returns e ON e.ticket=s.ticket
                JOIN operations o ON o.id=p.operation_id JOIN requests r ON r.id=p.request_id
                WHERE p.trajectory=?AND p.role=?AND p.generation=?AND s.ticket=?
                AND s.trajectory=p.trajectory AND s.role=p.role AND s.generation=p.generation
                AND s.request_id=p.request_id AND s.call_id=p.call_id AND s.mode='CALLBACK'
                AND s.peer_sha256=?AND e.ticket IS NULL AND o.kind='TOOL'AND o.state='ACTIVE'
                AND o.trajectory=p.trajectory AND o.role=p.role AND o.generation=p.generation
                AND o.parent=p.request_id AND r.trajectory=p.trajectory AND r.role=p.role
                AND r.generation=p.generation AND r.state='SETTLED'""",
                (t,role,generation,ticket,digest(self.peers[(t,role)]))).fetchall()
            need(len(rows)==1,'CLI_RECEIPT_GIT_EXACT_EXECUTING_ORIGINAL_REQUIRED')
            return rows[0][0]
    def callback_receipt(self,identity,call_id,operation_id):
        with self.ledger.mutex:
            self._peer(identity,self.peers.get(identity,{}))
            row=self.ledger.db.execute('''SELECT s.*,r.outcome,r.exception_type,r.receipt_sha256
                FROM native_cli_tool_starts s JOIN native_cli_tool_returns r ON r.ticket=s.ticket
                WHERE s.trajectory=?AND s.role=?AND s.call_id=?AND s.operation_id=?''',(*identity,call_id,operation_id)).fetchone()
            need(row is not None,'CLI_RECEIPT_ORIGINAL_CALLBACK_RETURN_REQUIRED')
            return {k:row[k]for k in ('trajectory','role','generation','operation_id','request_id','call_id','native_call_id','mode','peer_sha256','outcome','exception_type','receipt_sha256')}
    def unresolved(self):
        with self.ledger.mutex:return self.ledger.db.execute('SELECT COUNT(*)FROM native_cli_tool_starts s LEFT JOIN native_cli_tool_returns r ON r.ticket=s.ticket WHERE r.ticket IS NULL').fetchone()[0]

class NativeCliToolServer(NativeAcceptedControls,socketserver.UnixStreamServer):
    daemon_threads=False
    allow_reuse_address=False
    def __init__(self,path,receipts,identity):
        need(type(receipts)is NativeCliToolReceipts,'CLI_RECEIPT_ORIGINAL_HOST_SERVICE')
        self.receipts=receipts;self.identity=identity;self.path=Path(path)
        need(self.path.is_absolute()and self.path.resolve()==self.path and not self.path.exists()and len(os.fsencode(self.path))<108,'CLI_RECEIPT_NEW_FIXED_SOCKET')
        parent=self.path.parent.stat();need(stat.S_ISDIR(parent.st_mode)and parent.st_uid in(0,os.geteuid())and not parent.st_mode&0o022,'CLI_RECEIPT_HOST_SOCKET_PARENT')
        self.thread=None;self.stopped=False;self.closed=False
        class Handler(socketserver.StreamRequestHandler):
            def handle(handler):
                trusted=False
                try:
                    peer=peer_identity(handler.request)
                    receipts._peer(identity,peer);trusted=True;handler.request.settimeout(15)
                    raw=handler.rfile.readline(MAX_FRAME+1)
                    need(len(raw)<=MAX_FRAME and raw.endswith(b'\n')and handler.rfile.read(1)==b'','CLI_RECEIPT_SINGLE_BOUNDED_FRAME')
                    value=strict(raw);result=receipts.handle(identity,peer,value)
                    handler.wfile.write(wire(result)+b'\n');handler.wfile.flush()
                except BaseException:
                    if trusted:receipts.ledger.latch_fault(identity[0],'CLI_RECEIPT_CONTROL_DELIVERY_UNKNOWN')
                    try:handler.wfile.write(wire({'ok':False,'code':'CLI_RECEIPT_REFUSED'})+b'\n');handler.wfile.flush()
                    except OSError:pass
        super().__init__(str(self.path),Handler,control_failure=lambda _:receipts.ledger.latch_fault(identity[0],'CLI_RECEIPT_HANDLER_UNKNOWN'));self.path.chmod(0o666)
        self.controls=self._controls;self.active_controls=self._accepted_controls
        self.inode=self.path.stat().st_ino;self.scope='cli-tools-'+uuid.uuid4().hex
        receipts.ledger.retain_native_service(self.scope,self)
        try:
            with receipts.ledger.tx():receipts.ledger.event(identity[0],'NATIVE_CLI_TOOL_CONTROL_REGISTERED',
                {'scope':self.scope,'role':identity[1],'socket_inode':self.inode})
        except BaseException:
            receipts.ledger.latch_fault(identity[0],'CLI_RECEIPT_LISTENER_STORAGE_UNKNOWN');raise
    def start(self):
        need(self.thread is None and not self.stopped,'CLI_RECEIPT_LISTENER_START_ONCE')
        self.thread=threading.Thread(target=self.serve_forever,name='native-cli-tool-receipts',daemon=False);self.thread.start()
    def stop_listener(self):
        if self.stopped:return
        self.stopped=True
        if self.thread is not None:self.shutdown();self.thread.join()
    def close_drained(self):
        need(self.stopped and not self.closed,'CLI_RECEIPT_STOPPED_LISTENER_REQUIRED')
        # Join the original accepted handlers BEFORE the final unresolved/fault
        # check: one may still be parsing an authorized BEGIN during shutdown.
        self.server_close()
        self.control_snapshot(require_drained=True,code='CLI_RECEIPT_ACCEPTED_CONNECTIONS_RETAIN_CUSTODY')
        need(self.receipts.unresolved()==0,'CLI_RECEIPT_ACCEPTED_CALLBACKS_RETAIN_CUSTODY')
        need(not self.receipts.ledger.admission_fault(self.identity[0]),'CLI_RECEIPT_FAULT_RETAIN_CUSTODY')
        need(self.path.stat().st_ino==self.inode,'CLI_RECEIPT_SOCKET_REPLACED')
        try:
            with self.receipts.ledger.tx():self.receipts.ledger.event(self.identity[0],'NATIVE_CLI_TOOL_CONTROL_DRAINED_CLOSED',{'scope':self.scope,'role':self.identity[1]})
        except BaseException:
            self.receipts.ledger.latch_fault(self.identity[0],'CLI_RECEIPT_CLOSE_STORAGE_UNKNOWN');raise
        self.path.unlink();self.receipts.ledger.release_native_service(self.scope);self.closed=True
    def handle_error(self,*args):
        self._control_unknown()
