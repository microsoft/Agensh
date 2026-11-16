"""Fixed peer-bound MCP stdio/UDS transport with independent physical custody.

The trusted owner selects the native executable, env, tool declarations and
parent TOOL operation. Workers select none of these. Native stdout alone is NOT
terminal: an independent inherited fd must confirm the original notice shown
ACK chain completed too. An ambiguous backend/notice/pipe result is retained as
ACTIVE and faults admission; there is no respawn, replay, cancel or signal path.
Payloads only live in transit/memory, never in the metadata ledger.

This is a local integration component, not a production activation launcher.
"""
from dataclasses import dataclass,field
from pathlib import Path
import copy,hmac,os,selectors,socket,socketserver,subprocess,threading,uuid
from common import need,Refused,wire,strict,digest,private_dir,unix_socket_address
from bridge import peer_identity,process_identity,write_all
from native_control_custody import NativeAcceptedControls,require_control_drained
from native_mcp_policy import McpPolicy,FRAME_CAP,ScopeRejected,ArgumentRejected,normalize_protocol_progress

SCHEMA='agensh-native-mcp-uds-v1'

@dataclass
class Pending:
    operation_id:str
    request:dict
    done:threading.Event=field(default_factory=threading.Event)
    response:object=None
    terminal:object=None
    code:object=None

class NativeMcpSession:
    def __init__(self,policy,ledger,*,command,environment,cwd,parent_tool_provider,preexec_domain=None):
        need(isinstance(policy,McpPolicy),'MCP_QUALIFIED_POLICY_REQUIRED')
        need(type(command)is list and command and all(type(x)is str and x and '\x00'not in x for x in command),'MCP_TRUSTED_COMMAND')
        need(Path(command[0]).is_absolute()and callable(parent_tool_provider),'MCP_TRUSTED_HOST_CONFIGURATION')
        need(type(environment)is dict and all(type(k)is str and type(v)is str for k,v in environment.items()),'MCP_TRUSTED_ENVIRONMENT')
        policy.verify_backend(command,environment,cwd)
        if preexec_domain is not None:
            from native_cgroup_launch import NativeCgroupLaunch
            need(type(preexec_domain)is NativeCgroupLaunch,'MCP_TRUSTED_PREEXEC_DOMAIN_OBJECT');preexec_domain.current()
        self.policy,self.ledger=policy,ledger;self.identity=policy.identity;self.parent_tool_provider=parent_tool_provider
        self.lock=threading.RLock();self.pending={};self.broken=False;self.closing=False;self.closed=False;self.child=None
        self.scope=digest({k:v for k,v in vars(self.identity).items()if k not in('capability','generation')})
        self.config_sha=digest({'policy_sha256':policy.sha,'command':command,'environment_sha256':digest(environment),'cwd':str(cwd)})
        if preexec_domain is not None:
            self.config_sha=digest({'original_configuration_sha256':self.config_sha,'preexec_domain_binding_sha256':preexec_domain.binding_sha,'preexec_shim_sha256':preexec_domain.shim_sha})
        self.preexec_launch_receipt=None
        self.worker_initialize=None;self.worker_initialized=False
        self.threads=[];self.retainers=[];self.control=None;self.control_fd=None;self.retained_terminal=None
        with ledger.tx():
            # A stage advance is not a new service scope. Reopening a possibly-live
            # service must not launch a second native
            # process. Current implementation deliberately offers no cold resume.
            account=ledger._identity(self.identity.trajectory,self.identity.role,self.identity.generation)
            need(account['state']in('RUNNING','DRAINING')and not ledger.admission_fault(self.identity.trajectory),'MCP_ACCOUNT_NOT_ADMITTING')
            rows=ledger.db.execute("SELECT metadata FROM events WHERE trajectory=? AND kind='MCP_PROCESS_ALLOCATING'",(self.identity.trajectory,)).fetchall()
            need(all(strict(row[0]).get('scope')!=self.scope for row in rows),'MCP_SCOPE_ALREADY_ALLOCATED_NO_RESPAWN')
            ledger.event(self.identity.trajectory,'MCP_PROCESS_ALLOCATING',{'scope':self.scope,'policy_sha256':policy.sha,'configuration_sha256':self.config_sha})
        ledger.retain_native_service(self.scope,self)
        startup=threading.Event();started=False;writefd=None;prepared=None
        def ready_target(target):
            startup.wait()
            if started:target()
        try:
            readfd,writefd=os.pipe();self.control_fd=readfd
            env={**environment,'AGENSH_MCP_CONTROL_FD':str(writefd)}
            if preexec_domain is not None:prepared=preexec_domain.prepare(command,env)
            launch_command=command if prepared is None else prepared.command
            inherited=(writefd,) if prepared is None else (writefd,*prepared.pass_fds)
            with ledger.mutex:
                need(not ledger.admission_fault(self.identity.trajectory),'MCP_ACCOUNT_NOT_ADMITTING')
                self.child=subprocess.Popen(launch_command,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,pass_fds=inherited,bufsize=0)
            if prepared is not None:prepared.child_started()
            os.close(writefd);writefd=None
            self.control=os.fdopen(readfd,'rb',buffering=0)
            self.process_identity=process_identity(self.child.pid)
            if prepared is not None:self.preexec_launch_receipt=prepared.verify(self.child,self.process_identity)
            with ledger.tx():
                if prepared is not None:ledger.event(self.identity.trajectory,'MCP_PREEXEC_DOMAIN_READY',{'scope':self.scope,**self.preexec_launch_receipt})
                ledger.event(self.identity.trajectory,'MCP_PROCESS_STARTED',{'scope':self.scope,**self.process_identity})
            # No reader may run until ALL custodial threads are ready. A partial
            # Thread.start failure cannot leave competing consumers on one fd.
            for name,target in [('stdout',lambda:self._read(self.child.stdout,False)),('control',lambda:self._read(self.control,True)),('wait',self._wait)]:
                thread=threading.Thread(target=lambda t=target:ready_target(t),name='native-mcp-'+name,daemon=True)
                self.threads.append(thread);thread.start()
            if prepared is not None:prepared.release()
            started=True;startup.set()
        except BaseException:
            if prepared is not None:prepared.close()
            if writefd is not None:os.close(writefd);writefd=None
            # The independent in-memory gate closes before fallible metadata.
            # Retain the exact Popen object even when proc identity or STARTED
            # persistence failed; never return an unowned live native child.
            ledger.latch_fault(self.identity.trajectory,'MCP_START_CUSTODY_UNKNOWN')
            startup.set()
            for thread in self.threads:
                if thread.ident is not None:thread.join()
            if self.child is not None:
                thread=threading.Thread(target=self._retain_failed_start,name='native-mcp-start-custodian',daemon=False)
                self.retainers.append(thread)
                try:thread.start()
                except BaseException:
                    self.retainers.remove(thread)
                    # If the host cannot allocate a custodian thread, the caller
                    # itself retains/drains; do not drop or signal the child.
                    self._retain_failed_start()
            elif self.control_fd is not None:
                os.close(self.control_fd);self.control_fd=None
            try:self._broken('MCP_START_CUSTODY_UNKNOWN')
            except Exception:pass
            raise Refused('MCP_START_CUSTODY_UNKNOWN')from None
        finally:
            if prepared is not None:prepared.close()
            if writefd is not None:os.close(writefd)

    def _retain_failed_start(self):
        # Discard bounded chunks without decoding/logging native payloads. Both
        # stdout AND independent control fd must drain to EOF before waitpid.
        # No stdin close, kill, cancel, replay or respawn is used to manufacture
        # terminality. This may intentionally retain an idle service indefinitely.
        with selectors.DefaultSelector()as selector:
            selector.register(self.child.stdout.fileno(),selectors.EVENT_READ)
            selector.register(self.control_fd,selectors.EVENT_READ)
            while selector.get_map():
                for key,_ in selector.select():
                    try:raw=os.read(key.fd,65536)
                    except InterruptedError:continue
                    if not raw:selector.unregister(key.fd)
        code=self.child.wait()
        identity=getattr(self,'process_identity',{'pid':self.child.pid})
        self.retained_terminal={**identity,'exit_code':code if code>=0 else None,'signal':-code if code<0 else None}
        self.child.stdout.close()
        if self.control is not None:self.control.close()
        else:os.close(self.control_fd)
        self.child.stdin.close()
        try:self._event('MCP_RETAINED_START_PROCESS_TERMINAL',self.retained_terminal)
        except Exception:pass
        # Retained startup/fault is not reconciliation of possible remote side
        # effects, so no operation or native-service custody is released here.

    def _event(self,kind,meta):
        with self.ledger.tx():self.ledger.event(self.identity.trajectory,kind,{'scope':self.scope,**meta})

    def _broken(self,code):
        if getattr(self.ledger,'native_unmanaged_cli',False):
            from native_unmanaged_cli import broken
            return broken(self,code)
        with self.lock:
            self.broken=True
            self.fault_code=getattr(self,'fault_code',code)
            # This shared in-memory latch closes ALL SEARCH roles including
            # their final pre-SENT boundary, even if the SQLite FAULT rolls back.
            # owner.open already existed before any dispatch; an unclean/faulted
            # owner close/reopen cannot silently clear this admission fence.
            self.ledger.latch_fault(self.identity.trajectory,self.fault_code)
            try:
                if not getattr(self,'fault_persisted',False):
                    with self.ledger.tx():
                        self.ledger.db.execute("UPDATE accounts SET state='FAULT' WHERE trajectory=?",(self.identity.trajectory,))
                        self.ledger.event(self.identity.trajectory,'MCP_CUSTODY_UNKNOWN',{'scope':self.scope,'code':self.fault_code,'active_operations':len(self.pending)})
                    self.fault_persisted=True
            finally:
                # Wake accepted callers even when metadata persistence fails.
                # Re-entry may retry ONLY that metadata transaction, never work.
                for pending in self.pending.values():pending.code=pending.code or self.fault_code;pending.done.set()

    def _wait(self):
        code=self.child.wait()
        try:self._event('MCP_PROCESS_TERMINAL',{'exit_code':code if code>=0 else None,'signal':-code if code<0 else None,**self.process_identity})
        except Exception:
            self._broken('MCP_PROCESS_TERMINAL_METADATA_UNKNOWN');return
        with self.lock:
            # Even waitpid is not proof that an HTTP write/notice lease was not
            # accepted server-side. Outstanding operations stay ACTIVE forever
            # until an explicit trusted reconciliation (not implemented here).
            if not self.closing or self.pending:self._broken('MCP_NATIVE_PROCESS_EXIT_UNKNOWN')

    def _read(self,stream,control):
        try:
            while True:
                raw=stream.readline(FRAME_CAP+1)
                if not raw:
                    with self.lock:
                        if not self.closing or self.pending:self._broken('MCP_NATIVE_PIPE_EOF_UNKNOWN')
                    return
                need(len(raw)<=FRAME_CAP and raw.endswith(b'\n'),'MCP_NATIVE_FRAME_BOUND')
                message=strict(raw)
                with self.lock:
                    unmanaged=getattr(self.ledger,'native_unmanaged_cli',False)
                    if unmanaged and control:
                        # Only the native text prefix proof is needed for the
                        # unchanged output scope guard. Notice/rpc/terminal flags
                        # and dispatch closure are NOT admission/completion gates.
                        if not isinstance(message,dict) or message.get('id') not in self.pending:continue
                        pending=self.pending[message['id']]
                        if 'native_text'not in message:continue
                        need(message.get('method')==pending.request['method'],'MCP_NATIVE_TEXT_SCOPE_METHOD')
                        pending.terminal={'native_text':message['native_text']}
                        self._complete(message['id'],pending);continue
                    need(type(message)is dict and type(message.get('id'))is str and message['id']in self.pending,'MCP_NATIVE_UNMATCHED_ID')
                    pending=self.pending[message['id']]
                    if control:
                        need(set(message)in({'schema','id','method','notice_unknown','rpc_error'},{'schema','id','method','notice_unknown','rpc_error','native_text'})and message['schema']=='agensh-native-mcp-terminal-v1'and message['method']==pending.request['method']and type(message['notice_unknown'])is bool and type(message['rpc_error'])is bool,'MCP_NATIVE_CONTROL_FIELDS')
                        need(pending.terminal is None,'MCP_NATIVE_DUPLICATE_TERMINAL');pending.terminal=message
                    else:
                        need(pending.response is None,'MCP_NATIVE_DUPLICATE_RESPONSE');pending.response=self.policy.response(pending.request,message)
                    self._complete(message['id'],pending)
        except Refused as e:self._broken(e.code)
        except Exception:self._broken('MCP_NATIVE_PIPE_UNKNOWN')

    def _complete(self,rpc_id,pending):
        if getattr(self.ledger,'native_unmanaged_cli',False):
            from native_unmanaged_cli import complete
            return complete(self,rpc_id,pending)
        if pending.response is None or pending.terminal is None:return
        term=pending.terminal
        response_error='error'in pending.response or bool(isinstance(pending.response.get('result'),dict)and pending.response['result'].get('isError'))
        if term['notice_unknown']or term['rpc_error']or response_error:
            self._broken('MCP_NATIVE_NOTICE_OR_BACKEND_UNKNOWN');return
        # Both independent channels must agree. Never release from stdout alone.
        authorization=self.policy.authorization_response(pending.response,term)
        with self.ledger.tx():
            self.policy.physical_complete(pending.request,authorization)
            self.ledger.event(self.identity.trajectory,'MCP_OPERATION_PHYSICAL_TERMINAL',{'scope':self.scope,'operation_id':pending.operation_id,'method':pending.request['method'],'response_sha256':digest(pending.response)})
            row=self.ledger.db.execute('SELECT state,kind FROM operations WHERE id=?',(pending.operation_id,)).fetchone()
            need(row is not None and row['state']=='ACTIVE'and row['kind']in('CHAT_READ','CHAT_WRITE','GIT_READ','GIT_WRITE'),'MCP_OPERATION_LEDGER_IDENTITY')
            self.ledger.db.execute("UPDATE operations SET state='COMPLETE' WHERE id=?",(pending.operation_id,))
            self.ledger.event(self.identity.trajectory,'OPERATION_COMPLETE',{'operation_id':pending.operation_id})
        del self.pending[rpc_id];pending.done.set()

    def _worker_lifecycle_event(self,kind,metadata):
        # A typed storage refusal is just as uncertain as an I/O exception.
        # Isolate this try from request validation: do not accidentally downgrade
        # invalid worker protocol/control fields to a storage error.
        try:self._event(kind,metadata)
        except Exception:
            try:self._broken('MCP_WORKER_LIFECYCLE_METADATA_UNKNOWN')
            finally:raise Refused('MCP_WORKER_LIFECYCLE_METADATA_UNKNOWN')from None

    def bind_worker_initialize(self,request,response):
        """Retain the native verified one-shot Gitea initialize result privately.

        No backend initialize replay, restart, tools/call cache or error masking.
        A worker requesting a newer version receives the original negotiated
        server version unchanged, not an invented version/capability promise.
        """
        need(self.identity.purpose=='gitea' and self.worker_initialize is None,'MCP_WORKER_INITIALIZE_BIND_ONCE')
        need(request.get('method')=='initialize' and type(response.get('result'))is dict and 'error'not in response,'MCP_WORKER_INITIALIZE_VERIFIED_REPLY')
        self.policy.request(request);self.policy.response(request,response)
        with self.lock:
            need(not self.broken and not self.pending and self.policy.worker_ready(),'MCP_WORKER_INITIALIZE_NATIVE_PRIME_NOT_READY')
            self._worker_lifecycle_event('MCP_WORKER_INITIALIZE_BOUND',{'response_sha256':digest(response),'protocol_version':response['result'].get('protocolVersion')})
            self.worker_initialize=copy.deepcopy(response)

    def worker_call(self,message):
        if self.worker_initialize is None or message.get('method')not in('initialize','notifications/initialized'):return self.call(message)
        self.policy.request(message)
        with self.lock:
            need(not self.broken and not self.closing and not self.ledger.admission_fault(self.identity.trajectory),'MCP_SERVICE_NOT_ADMITTING')
            if message['method']=='initialize':
                self._worker_lifecycle_event('MCP_WORKER_INITIALIZE_FROM_NATIVE_PRIME',{'request_sha256':digest(message),'native_process_scope':self.scope})
                self.worker_initialized=True
                return {**copy.deepcopy(self.worker_initialize),'id':message['id']}
            need(self.worker_initialized,'MCP_WORKER_INITIALIZED_WITHOUT_INITIALIZE')
            self._worker_lifecycle_event('MCP_WORKER_INITIALIZED_FRONTEND',{'native_process_scope':self.scope});return None

    def call(self,message):
        if getattr(self.ledger,'native_unmanaged_cli',False):
            from native_unmanaged_cli import call
            return call(self,message)
        message=normalize_protocol_progress(message)
        # Only the exact original model index understands the private native
        # invocation ticket. Consume it before ORIGINAL policy/SDK processing;
        # never forward it to a backend or broaden any business/network guard.
        from native_model_tool_parent import NativeModelToolParents
        original_parent=type(self.parent_tool_provider)is NativeModelToolParents
        cli_ticket=None
        if original_parent:
            message,cli_ticket=self.parent_tool_provider.prepare_mcp_message(self.identity,message)
        try:kind=self.policy.request(message)
        except (ScopeRejected,ArgumentRejected) as error:
            # Pure metadata authorization, no native byte or backend effect.
            # Keep the original stdio/session alive and return a fixed logical
            # tool error, rather than confuse it with uncertain native custody.
            with self.lock:
                need(not self.broken and not self.closing and not self.ledger.admission_fault(self.identity.trajectory),'MCP_SERVICE_NOT_ADMITTING')
                event='MCP_ARGUMENT_REJECTED_BEFORE_DISPATCH'if isinstance(error,ArgumentRejected)else'MCP_SCOPE_REJECTED_BEFORE_DISPATCH'
                response={'jsonrpc':'2.0','id':message['id'],'result':{'isError':True,'content':[{'type':'text','text':error.code}]}}
                # Rejection is not an accepted native dispatch. With the original
                # CLI attached, bind the host decision to its exact still-running
                # ticket/model TOOL before returning the unchanged logical error.
                bound=None
                if original_parent and self.parent_tool_provider.cli_receipts is not None:
                    parent=self.parent_tool_provider.mcp_parent(self.identity,message,cli_ticket=cli_ticket)
                    bound={'schema':'agensh-original-mcp-predispatch-rejection-v1',
                           'scope':self.scope,'role':self.identity.role,'generation':self.identity.generation,
                           'operation_id':parent,'cli_ticket_sha256':digest(cli_ticket),
                           'configuration_sha256':self.config_sha,
                           'native_process_identity_sha256':digest(self.process_identity),
                           'rejection_kind':event,'code':error.code,
                           'request_sha256':digest(message),'response_sha256':digest(response),
                           'native_bytes_sent':False}
                try:
                    if bound is None:
                        # Keep the original legacy metadata/failure seam.
                        self._event(event,{'code':error.code,'request_sha256':digest(message)})
                    else:
                        # Generic refusal and original-ticket binding commit
                        # atomically; neither alone is a callback receipt.
                        with self.ledger.tx():
                            self.ledger.event(self.identity.trajectory,event,
                                              {'scope':self.scope,'code':error.code,'request_sha256':digest(message)})
                            previous=[strict(r[0]) for r in self.ledger.db.execute(
                                "SELECT metadata FROM events WHERE trajectory=?AND kind='NATIVE_MCP_ORIGINAL_TOOL_PREDISPATCH_REJECTED'",
                                (self.identity.trajectory,))]
                            need(not any(x.get('operation_id')==parent for x in previous),
                                 'MCP_ORIGINAL_REJECTION_ONCE_NO_RETRY')
                            self.ledger.event(self.identity.trajectory,'NATIVE_MCP_ORIGINAL_TOOL_PREDISPATCH_REJECTED',bound)
                except Exception:
                    self._broken('MCP_SCOPE_REJECTION_METADATA_UNKNOWN');raise Refused('MCP_SCOPE_REJECTION_METADATA_UNKNOWN')from None
            return response
        with self.lock:
            need(not self.broken and not self.closing and not self.ledger.admission_fault(self.identity.trajectory),'MCP_SERVICE_NOT_ADMITTING')
            if kind is None:
                try:write_all(self.child.stdin,wire(message)+b'\n')
                except Exception:self._broken('MCP_INITIALIZED_WRITE_UNKNOWN');raise Refused('MCP_INITIALIZED_WRITE_UNKNOWN')from None
                return None
            op='mcp-'+uuid.uuid4().hex;rid=uuid.uuid4().hex
            mcp_parent=getattr(self.parent_tool_provider,'mcp_parent',None)
            parent=(mcp_parent(self.identity,message,cli_ticket=cli_ticket)if original_parent
                    else mcp_parent(self.identity,message)if callable(mcp_parent)else self.parent_tool_provider(self.identity))
            self.ledger.operation_start(self.identity.trajectory,self.identity.role,self.identity.generation,op,kind,parent_tool_operation=parent)
            request={**message,'id':rid};pending=Pending(op,request);self.pending[rid]=pending
            # Commit before any byte goes to native stdin. Never persist private
            # args, worker RPC ids, service replies or capabilities.
            try:
                self._event('MCP_OPERATION_DISPATCHING',{'operation_id':op,'method':request['method'],'request_sha256':digest(request)})
                write_all(self.child.stdin,wire(request)+b'\n')
            except Exception:self._broken('MCP_NATIVE_SEND_UNKNOWN')
        pending.done.wait()
        need(pending.code is None,pending.code or'MCP_OPERATION_UNKNOWN')
        return {**pending.response,'id':message['id']}

    def active_count(self):
        with self.lock:return len(self.pending)

    def close_when_drained(self,timeout=10):
        """Graceful EOF only after accepted work finishes; no cancellation."""
        with self.lock:
            need(not self.pending and not self.broken,'MCP_CUSTODY_NOT_DRAINED')
            if self.closed:return
            self.closing=True;self.child.stdin.close()
        try:self.child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:raise Refused('MCP_DRAINED_PROCESS_STILL_LIVE_NO_SIGNAL')from None
        for thread in self.threads:thread.join(timeout)
        need(all(not t.is_alive()for t in self.threads),'MCP_READER_STILL_LIVE')
        need(not self.broken,'MCP_DRAINED_CLOSE_CUSTODY_UNKNOWN')
        self.child.stdout.close();self.control.close();self.closed=True
        try:self._event('MCP_PROCESS_DRAINED_CLOSED',{})
        except Exception:
            self._broken('MCP_DRAINED_CLOSE_METADATA_UNKNOWN');raise
        self.ledger.release_native_service(self.scope)

class McpServer:
    def __init__(self,path,session,*,late_delivery=False):
        from native_delivery import delivery_dir
        self.path=Path(path);(delivery_dir if late_delivery else private_dir)(self.path.parent);need(not self.path.exists(),'MCP_SOCKET_ALREADY_EXISTS')
        need(session.policy.worker_ready(),'MCP_SCOPE_NOT_PRIMED')
        self.session=session;self.thread=None;owner=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                try:
                    peer=peer_identity(self.request);raw=self.rfile.readline(FRAME_CAP+1)
                    need(len(raw)<=FRAME_CAP and raw.endswith(b'\n'),'MCP_WORKER_FRAME_BOUND')
                    result=owner.dispatch(peer,strict(raw));response={'ok':True,'result':result}
                except Refused as e:response={'ok':False,'code':e.code}
                except Exception:response={'ok':False,'code':'MCP_CONTROL_ERROR'}
                try:self.wfile.write(wire(response)+b'\n');self.wfile.flush()
                except OSError:
                    # The accepted call already ran to terminal or retained its
                    # custody. A lost client never closes native stdin/replays.
                    if not getattr(owner.session.ledger,'native_unmanaged_cli',False):owner.session._event('MCP_CLIENT_DELIVERY_LOST',{})
        class Server(NativeAcceptedControls,socketserver.UnixStreamServer):pass
        with unix_socket_address(self.path)as address:self.server=Server(address,Handler,control_failure=lambda code:session.ledger.latch_fault(session.identity.trajectory,code),unmanaged_cli=getattr(session.ledger,'native_unmanaged_cli',False))
        self.server.server_address=str(self.path);os.chmod(self.path,0o600)
        if session.identity.uid!=os.geteuid():os.chown(self.path,session.identity.uid,-1)
        self.inode=self.path.stat().st_ino

    def dispatch(self,peer,value):
        identity=self.session.identity
        need(peer['uid']==identity.uid and peer['pid_namespace_inode']==identity.pid_namespace_inode,'MCP_PEER_IDENTITY')
        need(type(value)is dict and set(value)=={'schema','capability','message'}and value['schema']==SCHEMA,'MCP_WORKER_ENVELOPE')
        need(type(value['capability'])is str and hmac.compare_digest(value['capability'],identity.capability),'MCP_PEER_CAPABILITY')
        return self.session.worker_call(value['message'])

    def start(self):
        need(self.thread is None,'MCP_SERVER_ALREADY_STARTED');self.thread=threading.Thread(target=self.server.serve_forever,name='native-mcp-uds',daemon=True);self.thread.start()

    def close_listener(self):
        # Stop accepting, then join original accepted framing/business/delivery.
        # No cancellation or native-session EOF; zero pending alone is not drain.
        if self.thread:self.server.shutdown();self.thread.join(10)
        self.server.server_close();require_control_drained(self,'MCP_ACCEPTED_CONTROL_RETAIN_CUSTODY');need(self.path.is_socket()and self.path.stat().st_ino==self.inode,'MCP_SOCKET_IDENTITY_CHANGED');self.path.unlink()

class McpClient:
    def __init__(self,path,capability):
        self.path=Path(path);need(self.path.is_absolute()and self.path.resolve()==self.path,'MCP_CLIENT_SOCKET');self.capability=capability
    def call(self,message):
        raw=wire({'schema':SCHEMA,'capability':self.capability,'message':message})+b'\n';need(len(raw)<=FRAME_CAP,'MCP_WORKER_FRAME_BOUND')
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)as client:
                with unix_socket_address(self.path)as address:client.connect(address)
                client.sendall(raw)
                with client.makefile('rb')as stream:reply=stream.readline(FRAME_CAP+1)
            need(len(reply)<=FRAME_CAP and reply.endswith(b'\n'),'MCP_WORKER_REPLY_BOUND');result=strict(reply)
            need(type(result)is dict and result.get('ok')is True,result.get('code','MCP_WORKER_CONTROL_UNKNOWN')if type(result)is dict else'MCP_WORKER_CONTROL_UNKNOWN')
            return result['result']
        except Refused:raise
        except Exception:raise Refused('MCP_WORKER_TRANSPORT_UNKNOWN_NO_RETRY')from None
