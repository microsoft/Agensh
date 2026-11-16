"""Original scientific relay HTTP custody, never a second model controller.

Budget-only SSE comments are transport liveness, NOT a CLI timeout exemption. A response write loss
faults admission but DOES NOT throw through the upstream SSE iterator, cancel
SENT work, release its physical reservation or replay it. A genuinely dead
socket during UNSENT admission is observed without reading client payloads;
ordinary TCP half-close remains allowed. Actual CLI park qualification is OPS's.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import MappingProxyType
from pathlib import Path
import hmac, ipaddress, os, re, select, threading, uuid
from common import need, Refused, digest, integer, hash_file
from protocol import Rejected, wire, need as http_need, base_response, StreamMapper
from feasibility_relay import MAX_BODY, strict_json
from scientific_relay import ScientificRelay
from admission_gate import AdmissionGate
from bridge import process_identity

HEARTBEAT_SECONDS=15.0
DELIVERY_WRITE_SECONDS=15.0
PARK_COMMENT=b': count14-budget-park\n\n'

class NativeHttpRequest:
    """Host-created exact HTTP connection -> ORIGINAL generated Responses rid.

    It never supplies model usage, tool terminal proof or scientific identity.
    All network IO remains in the original HTTP handler thread. Only immutable
    metadata is exposed; bearer/body/result/error text is never logged.
    """
    def __init__(self, server, connection, identity, payload_sha256):
        self.server=server;self.engine=server.engine;self.ledger=server.engine.budget
        self.connection=connection;self.fd=connection.fileno();self.identity=identity
        self.payload_sha=payload_sha256;self.handle='http-'+uuid.uuid4().hex
        self.lock=threading.RLock();self.rid=None;self.request_sha=None
        self.delivery_unknown=False;self.failure_metadata_unknown=False
        self.finished=False;self.bytes_written=0;self.outcome=None
        self.stream_events_attempted={};self.stream_events_written={}
        self.stream_start=None;self.stream_comment=None;self.stream_opened=False
        self.heartbeat_stop=threading.Event();self.heartbeat_thread=None;self.heartbeat_count=0
    def _registered(self):
        # Only a genuine host-held request can fault its original trajectory.
        # An invented handle must not select/fault another registered role.
        with self.server.registry_lock:
            need(self.server.requests.get(self.handle) is self,
                 'SCIENTIFIC_HTTP_ORIGINAL_REQUEST_HANDLE')
        try:
            self.server.current()
            need(self.connection.fileno()==self.fd and self.fd>=0,
                 'SCIENTIFIC_HTTP_ORIGINAL_SOCKET')
        except BaseException:
            self.failure_metadata_unknown=True
            self.ledger.latch_fault(self.identity[0],'SCIENTIFIC_HTTP_REQUEST_BINDING_UNKNOWN')
            self.server.gate.notify()
            raise
    def configure_stream(self,handler,start,comment):
        self._registered()
        need(type(handler)is NativeScientificHandler and handler.server is self.server
             and handler.connection is self.connection and callable(start)and callable(comment),
             'SCIENTIFIC_HTTP_ORIGINAL_STREAM_WRITER')
        with self.lock:
            need(self.rid is None and self.stream_start is None,'SCIENTIFIC_HTTP_STREAM_CONFIGURE_ONCE')
            self.stream_start=start;self.stream_comment=comment
    def _start_budget_transport(self):
        if self.stream_start is None:return
        # Same handler thread, only AFTER original protocol validation and
        # durable original rid binding. No fake response/model event is sent.
        if not self.stream_start():return
        self.stream_opened=True
        def heartbeat():
            try:
                while not self.heartbeat_stop.wait(HEARTBEAT_SECONDS):
                    self._registered()
                    with self.lock:active=not self.finished and not self.delivery_unknown
                    if not active:return
                    if not self.stream_comment():return
                    with self.lock:self.heartbeat_count+=1
            except BaseException:
                self.failure_metadata_unknown=True
                self.ledger.latch_fault(self.identity[0],'SCIENTIFIC_HTTP_KEEPALIVE_CUSTODY_UNKNOWN')
                self.delivery_failed('SCIENTIFIC_HTTP_KEEPALIVE_CUSTODY_UNKNOWN')
        self.heartbeat_thread=threading.Thread(target=heartbeat,name='native-http-budget-comment',daemon=False)
        try:self.heartbeat_thread.start()
        except BaseException:
            self.failure_metadata_unknown=True
            self.ledger.latch_fault(self.identity[0],'SCIENTIFIC_HTTP_KEEPALIVE_START_UNKNOWN');raise
    def _stop_budget_transport(self):
        self.heartbeat_stop.set();thread=self.heartbeat_thread
        # Never join while holding ledger.mutex: the same original heartbeat
        # may be making its brief budget-pause observation under that mutex.
        if thread is not None and thread.ident is not None:thread.join()
    def bind(self,rid,identity,request_sha):
        # Called by original ScientificUsage.begin, before original reserve/send.
        self._registered()
        with self.ledger.mutex,self.lock:
            need(not self.finished and self.rid is None and identity==self.identity,
                 'SCIENTIFIC_HTTP_BIND_EXACT_ONCE')
            self.rid=rid;self.request_sha=request_sha
            try:
                with self.ledger.tx():
                    self.ledger.event(identity[0],'SCIENTIFIC_HTTP_REQUEST_BOUND',
                        {'handle':self.handle,'role':identity[1],'request_id':rid,
                         'http_payload_sha256':self.payload_sha,
                         'normalized_request_sha256':request_sha})
            except BaseException:
                self.failure_metadata_unknown=True
                self.ledger.latch_fault(identity[0],'SCIENTIFIC_HTTP_BIND_STORAGE_FAILURE')
                raise Refused('SCIENTIFIC_HTTP_BIND_STORAGE_FAILURE_NO_SEND')from None
        self._start_budget_transport()
    def _native_end_no_send(self):
        # Only exact current END intents and NEVER-RESERVED original requests.
        # Preserve PrivateStates.parked and every financial row unchanged.
        control=getattr(self.server.gate,'_dynteam_role_control',None)
        if control is None or self.rid is None:return False
        with self.ledger.mutex:
            if self.identity not in getattr(control,'native_end_holds',{}):return False
            if self.ledger.db.execute('SELECT state FROM requests WHERE id=?',(self.rid,)).fetchone() is not None:
                return False
            with self.lock:self.normal_end_no_send=True
            return True
    def delivery_failed(self,code='SCIENTIFIC_HTTP_DELIVERY_UNKNOWN'):
        # Do NOT raise: throwing out of emit closes original transport iteration
        # and could cancel an already-SENT upstream operation. Keep consuming to
        # its original physical terminal and preserve original accounting.
        with self.ledger.mutex,self.lock:
            if self.delivery_unknown:return
            self.delivery_unknown=True
            if self.rid is None:return  # malformed/rejected before model binding
            peer=code in ('SCIENTIFIC_HTTP_DELIVERY_UNKNOWN','SCIENTIFIC_HTTP_PEER_UNAVAILABLE_NO_SEND')
            expected_end=False
            if not peer:self.ledger.latch_fault(self.identity[0],code)
            try:
                expected_end=peer and self._native_end_no_send()
                with self.ledger.tx():
                    if peer and not expected_end:self.server.record_peer_outcome(self.identity,self.rid,failed=True)
                    self.ledger.event(self.identity[0],
                        'SCIENTIFIC_HTTP_ROLE_END_NO_SEND' if expected_end else 'SCIENTIFIC_HTTP_DELIVERY_UNKNOWN',
                        {'handle':self.handle,'role':self.identity[1],
                         'request_id':self.rid,'code':code,
                         'body_bytes_written':self.bytes_written,
                         'expected_native_END_no_send':expected_end,
                         'upstream_cancelled_replayed_or_reclassified':False})
            except BaseException:
                self.failure_metadata_unknown=True
                self.ledger.latch_fault(self.identity[0],'SCIENTIFIC_HTTP_PEER_METADATA_UNKNOWN')
        self.server.gate.notify()
    def guard(self):
        self._registered()
        need(not self._native_end_no_send(),'ROLE_END_HOLD_NO_SEND')
        # POLLRDHUP/EOF alone only means the client half-closed its write side.
        # That is legal HTTP; do not read/consume a payload byte or cancel it.
        # POLLERR/HUP/NVAL instead means a hard transport loss. No wall-clock
        # deadline, model request or CLI/ACP restart is introduced.
        with self.lock:
            unknown=self.delivery_unknown;finished=self.finished
        need(not finished,'SCIENTIFIC_HTTP_FINISHED_REQUEST_NO_SEND')
        if not unknown:
            poller=select.poll();poller.register(self.fd,select.POLLERR|select.POLLHUP|select.POLLNVAL)
            if any(events&(select.POLLERR|select.POLLHUP|select.POLLNVAL)
                   for _,events in poller.poll(0)):
                self.delivery_failed('SCIENTIFIC_HTTP_PEER_UNAVAILABLE_NO_SEND')
        with self.lock:need(not self.delivery_unknown,'SCIENTIFIC_HTTP_PEER_UNAVAILABLE_NO_SEND')
    def confirm_before_send(self):
        # Called outside ledger.mutex: writer -> delivery_failed takes it.
        # A legal TCP half-close still receives this genuine SSE comment.
        self.guard()
        with self.lock:comment=self.stream_comment
        if comment is not None and not comment():
            self.delivery_failed('SCIENTIFIC_HTTP_PEER_UNAVAILABLE_NO_SEND')
        self.guard()
    def note_stream_event(self,kind,written):
        allowed={'response.created','response.in_progress','response.output_item.added',
                 'response.content_part.added','response.output_text.delta','response.output_text.done',
                 'response.content_part.done','response.function_call_arguments.delta',
                 'response.function_call_arguments.done','response.output_item.done',
                 'response.completed','response.incomplete','response.failed'}
        key=kind if kind in allowed else 'OTHER'
        with self.lock:
            self.stream_events_attempted[key]=self.stream_events_attempted.get(key,0)+1
            if written:self.stream_events_written[key]=self.stream_events_written.get(key,0)+1
    def wrote(self,size):
        with self.lock:self.bytes_written+=size
    def finish(self,outcome):
        self._stop_budget_transport()
        # Handler completion is NOT an upstream terminal proof or CLI OBSERVED.
        # A SENT/UNKNOWN row stays unresolved and prevents clean retirement.
        with self.ledger.mutex,self.lock:
            need(not self.finished,'SCIENTIFIC_HTTP_FINISH_ONCE')
            self.finished=True
            self.outcome=('ROLE_END_NO_SEND' if getattr(self,'normal_end_no_send',False) else
                          'DELIVERY_UNKNOWN' if self.delivery_unknown else outcome)
            if self.rid is not None:
                row=self.ledger.db.execute('SELECT state FROM requests WHERE id=?',(self.rid,)).fetchone()
                state=None if row is None else row[0]
                try:
                    with self.ledger.tx():
                        if not self.delivery_unknown and outcome=='RESPONSE_BYTES_WRITTEN'and state=='SETTLED':
                            self.server.record_peer_outcome(self.identity,self.rid,failed=False)
                        self.ledger.event(self.identity[0],'SCIENTIFIC_HTTP_HANDLER_FINISHED',
                            {'handle':self.handle,'role':self.identity[1],
                             'request_id':self.rid,'original_request_state':state,
                             'outcome':self.outcome,'body_bytes_written':self.bytes_written,
                             'client_observed_not_proven':True,
                             'budget_park_comments_written':self.heartbeat_count,
                             'stream_headers_opened':self.stream_opened,
                             'anonymous_stream_events_attempted':dict(self.stream_events_attempted),
                             'anonymous_stream_events_written':dict(self.stream_events_written),
                             'anonymous_response_metadata_unavailable':bool(getattr(self.engine.ledger,'anonymous_response_metadata_unavailable',False))})
                except BaseException:
                    self.failure_metadata_unknown=True
                    self.ledger.latch_fault(self.identity[0],'SCIENTIFIC_HTTP_FINISH_STORAGE_FAILURE')
        self.server.gate.notify()
    def status(self):
        with self.lock:
            return {'handle':self.handle,'trajectory':self.identity[0],'role':self.identity[1],
                    'request_id':self.rid,'delivery_unknown':self.delivery_unknown,
                    'failure_metadata_unknown':self.failure_metadata_unknown,
                    'finished':self.finished,'outcome':self.outcome,
                    'normal_native_END_no_send':getattr(self,'normal_end_no_send',False),
                    'body_bytes_written':self.bytes_written,
                    'budget_park_comments_written':self.heartbeat_count,
                    'stream_headers_opened':self.stream_opened,
                    'heartbeat_thread_live':self.heartbeat_thread is not None and self.heartbeat_thread.is_alive()}

class NativeScientificHandler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def identity(self):
        values=self.headers.get_all('Authorization',[])
        if len(values)!=1:raise Rejected('AUTHENTICATION_REQUIRED',401)
        # HTTP headers decode Latin1. compare_digest(str) rejects non-ASCII;
        # bytes comparison prevents an unauthenticated Unicode header from
        # escaping as an internal exception and faulting unrelated trajectories.
        raw=values[0].encode('latin1')
        for token,identity in self.server.identities.items():
            if hmac.compare_digest(raw,b'Bearer '+token.encode('ascii')):
                return identity
        raise Rejected('AUTHENTICATION_REQUIRED',401)
    def _write(self,raw,custody=None):
        if custody is not None and custody.delivery_unknown:return False
        try:
            n=self.wfile.write(raw);self.wfile.flush()
            if n!=len(raw):raise OSError('OWN_FIXED_HTTP_SHORT_WRITE')
            if custody is not None:custody.wrote(n)
            return True
        except OSError:
            if custody is not None:custody.delivery_failed()
            self.close_connection=True;return False
    def send_json(self,value,status=200,custody=None):
        raw=wire(value);self.close_connection=True
        try:
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Connection','close');self.end_headers()
        except OSError:
            if custody is not None:custody.delivery_failed()
            return False
        return self._write(raw,custody)
    def do_GET(self):
        identity=None
        try:
            if self.path=='/healthz':
                self.send_json({'status':'ok','purpose':'agensh_scientific_transport',
                                'scientific_activation_qualified_here':False});return
            identity=self.identity()
            if self.path=='/admin/usage':
                self.send_json([r for r in self.server.engine.ledger.totals()
                                if (r['trajectory'],r['agent'])==identity]);return
            prefix='/v1/responses/'
            if self.path.startswith(prefix):
                self.send_json(self.server.engine.lookup(self.path[len(prefix):],identity)['response']);return
            raise Rejected('ROUTE_NOT_FOUND',404)
        except Rejected as exc:self._reject(exc,identity=identity)
        except Exception:self.close_connection=True
    def _reject(self,exc,custody=None,identity=None):
        # Existing protocol codes only, never an exception message/payload.
        code=exc.code if type(exc.code)is str and re.fullmatch('[A-Z0-9_]{1,160}',exc.code)else'SCIENTIFIC_HTTP_REQUEST_REJECTED'
        self.server.note_rejection(identity if custody is None else custody.identity,code,exc.status,custody)
        return self.send_json({'error':{'type':'invalid_request_error','code':code,'message':code}},exc.status,custody)
    def do_POST(self):
        started=False;terminal=False;custody=None;outcome='HANDLER_UNKNOWN';identity=None
        stream_lock=threading.RLock();emit=None;request=None
        def stream_error(exc):
            nonlocal terminal
            if custody is None or not started or terminal or custody.delivery_unknown:return
            # Original schema/sequence, original generated rid, FAILED only.
            # This is not a model physical terminal/usage or a ledger mutation.
            failed=base_response(request,custody.rid)
            mapper=StreamMapper(failed,emit)
            failed.update(status='failed',error={'type':'server_error','code':exc.code,'message':exc.code})
            mapper.event('response.failed',response=failed)
        try:
            identity=self.identity();http_need(self.path=='/v1/responses','ROUTE_NOT_FOUND')
            http_need(not self.headers.get('Transfer-Encoding'),'CHUNKED_REQUEST_UNSUPPORTED')
            http_need(self.headers.get_content_type()=='application/json','JSON_CONTENT_TYPE_REQUIRED')
            lengths=self.headers.get_all('Content-Length',[])
            http_need(len(lengths)==1 and lengths[0].isdigit(),'CONTENT_LENGTH_REQUIRED')
            length=int(lengths[0]);http_need(0<length<=MAX_BODY,'REQUEST_BODY_BOUND')
            raw=self.rfile.read(length);http_need(len(raw)==length,'REQUEST_BODY_INCOMPLETE')
            request=strict_json(raw);http_need(type(request)is dict,'JSON_OBJECT_REQUIRED')
            metadata=request.get('metadata',{});http_need(type(metadata)is dict,'METADATA_OBJECT')
            for key,value in zip(('trajectory_id','agent_id'),identity):
                http_need(metadata.get(key,value)==value,'METADATA_IDENTITY_MISMATCH')
            custody=self.server.new_request(self.connection,identity,digest(request))
            if request.get('stream')is True:
                def start_stream():
                    nonlocal started
                    with stream_lock:
                        if custody.delivery_unknown:return False
                        if started:return True
                        try:
                            # Only outbound delivery is bounded; body parsing
                            # is complete. Never timeout/cancel original upstream.
                            self.connection.settimeout(DELIVERY_WRITE_SECONDS)
                            self.send_response(200);self.send_header('Content-Type','text/event-stream')
                            self.send_header('Cache-Control','no-cache')
                            self.send_header('Connection','close');self.end_headers()
                            self.close_connection=True;started=True;return True
                        except OSError:
                            custody.delivery_failed();return False
                def comment():
                    with stream_lock:
                        if not started or custody.delivery_unknown:return False
                        return self._write(PARK_COMMENT,custody)
                def emit(event):
                    nonlocal terminal
                    with stream_lock:
                        if custody.delivery_unknown:return
                        if not start_stream():return
                        written=self._write(b'event: '+event['type'].encode()+b'\ndata: '+wire(event)+b'\n\n',custody)
                        custody.note_stream_event(event['type'],written)
                        if event['type']in ('response.completed','response.incomplete','response.failed'):terminal=True
                custody.configure_stream(self,start_stream,comment)
            response=self.server.engine.run(request,identity,emit=emit,http_custody=custody)
            if not started and not custody.delivery_unknown:self.send_json(response,custody=custody)
            outcome='RESPONSE_BYTES_WRITTEN'
        except Rejected as exc:
            outcome='PROTOCOL_REJECTED'
            if not started:self._reject(exc,custody,identity)
            else:
                self.server.note_rejection(identity,exc.code,exc.status,custody);stream_error(exc)
        except Refused as exc:
            outcome='PROTOCOL_REJECTED'
            if not started:self._reject(Rejected(exc.code,409),custody,identity)
            else:
                self.server.note_rejection(identity,exc.code,409,custody);stream_error(exc)
        except Exception:
            outcome='HANDLER_UNKNOWN'
            if custody is not None:custody.delivery_failed('SCIENTIFIC_HTTP_HANDLER_UNKNOWN')
            self.close_connection=True
        finally:
            if custody is not None:
                if outcome=='HANDLER_UNKNOWN':custody.delivery_failed('SCIENTIFIC_HTTP_HANDLER_UNKNOWN')
                self.server.finish_request_custody(custody,outcome)

class NativeScientificHttpServer(ThreadingHTTPServer):
    daemon_threads=False
    def __init__(self,address,engine,identities):
        need(type(engine)is ScientificRelay and type(engine.ledger.admission_gate)is AdmissionGate,
             'SCIENTIFIC_HTTP_ORIGINAL_RELAY_GATE')
        self.engine=engine;self.gate=engine.ledger.admission_gate;self.ledger=engine.budget
        need(self.gate.ledger is self.ledger and self.gate.global_cap==engine.ledger.global_cap,
             'SCIENTIFIC_HTTP_ORIGINAL_SHARED_LEDGER_CAP')
        need(type(identities)is dict and 0<len(identities)<=96,'SCIENTIFIC_HTTP_REGISTERED_IDENTITIES')
        mapping={}
        with self.ledger.mutex:
            for token,identity in identities.items():
                need(type(token)is str and re.fullmatch('[A-Za-z0-9_-]{32,512}',token)
                     and type(identity)is tuple and len(identity)==2,
                     'SCIENTIFIC_HTTP_EXACT_PRIVATE_IDENTITY')
                t,role=identity;f=self.ledger.frontier(t);self.ledger._identity(t,role,f['generation'])
                mapping[token]=identity
        need(len(set(mapping.values()))==len(mapping),'SCIENTIFIC_HTTP_ONE_BEARER_PER_ROLE')
        need(type(address)is tuple and len(address)==2 and type(address[0])is str,
             'SCIENTIFIC_HTTP_FIXED_LISTENER')
        try:ip=ipaddress.ip_address(address[0])
        except ValueError:raise Refused('SCIENTIFIC_HTTP_LITERAL_PRIVATE_LISTENER')from None
        need(ip.version==4 and not ip.is_unspecified and (ip.is_loopback or ip.is_private),
             'SCIENTIFIC_HTTP_LITERAL_PRIVATE_LISTENER')
        integer(address[1],'SCIENTIFIC_HTTP_PORT');need(address[1]<=65535,'SCIENTIFIC_HTTP_PORT')
        self.identities=MappingProxyType(mapping);self.registered=frozenset(mapping.values())
        self.owner=process_identity(os.getpid());self.registry_lock=threading.RLock()
        self.requests={};self.retained={};self.accepted_sockets={}
        self.completed=0;self.delivery_unknown_count=0;self.rejections={}
        self.thread=None;self.listener_stopped=False;self.closed=False
        self.started=False;self.lifecycle_storage_unknown=False
        self.retire_attempted=False;self.network_closed=False
        self.serving=threading.Event();self.loop_finished=threading.Event()
        self.scope='native-http-'+uuid.uuid4().hex
        with engine.lock:
            need(getattr(engine,'native_http_custodian',None)is None,
                 'SCIENTIFIC_HTTP_ONE_ORIGINAL_SERVER')
            super().__init__(address,NativeScientificHandler)
            try:
                self.ledger.retain_native_service(self.scope,self)
                engine.native_http_custodian=self
            except BaseException:
                self.server_close();raise
        self.listener_identity={'owner':self.owner,'owner_uid':os.geteuid(),
            'netns_inode':os.stat('/proc/self/ns/net').st_ino,
            'socket_inode':os.fstat(self.socket.fileno()).st_ino,
            'address':list(self.server_address),
            'role_roster_sha256':digest(sorted([list(v)for v in self.registered])),
            'implementation_sha256':hash_file(Path(__file__))['sha256']}
        self.listener_identity_sha256=digest(self.listener_identity)
    def current(self):
        need(not self.closed and process_identity(os.getpid())==self.owner,
             'SCIENTIFIC_HTTP_ORIGINAL_LIVE_OWNER')
        need(self.engine.budget is self.ledger and self.engine.ledger.admission_gate is self.gate
             and self.engine.ledger.global_cap==self.gate.global_cap
             and getattr(self.engine,'native_http_custodian',None)is self,
             'SCIENTIFIC_HTTP_ORIGINAL_RUNTIME_BINDING')
        need(digest(self.listener_identity)==self.listener_identity_sha256,
             'SCIENTIFIC_HTTP_FROZEN_LISTENER_IDENTITY')
        if not self.network_closed:
            need(os.stat('/proc/self/ns/net').st_ino==self.listener_identity['netns_inode']
                 and os.fstat(self.socket.fileno()).st_ino==self.listener_identity['socket_inode']
                 and list(self.server_address)==self.listener_identity['address'],
                 'SCIENTIFIC_HTTP_ORIGINAL_LISTENER_SOCKET')
    def _record_lifecycle(self,kind):
        try:
            with self.ledger.tx():
                for t in {t for t,_ in self.registered}:
                    self.ledger.event(t,kind,{'scope':self.scope,
                        'listener_identity_sha256':digest(self.listener_identity),
                        'client_observed_not_proven':True})
        except BaseException:
            self.lifecycle_storage_unknown=True
            for t in {t for t,_ in self.registered}:self.ledger.latch_fault(t,'SCIENTIFIC_HTTP_LIFECYCLE_STORAGE_UNKNOWN')
            raise Refused('SCIENTIFIC_HTTP_LIFECYCLE_STORAGE_UNKNOWN_NO_RETRY')from None
    def record_peer_outcome(self,identity,rid,*,failed):
        # Caller holds original ledger mutex/transaction; one outcome per
        # failed connection (delivery_failed's original idempotence guard).
        need(self.ledger.mutex._is_owned()and self.ledger.db.in_transaction,
             'SCIENTIFIC_HTTP_PEER_ORIGINAL_WRITER_TRANSACTION')
        t,role=identity
        previous=self.ledger.db.execute(
            "SELECT metadata FROM events WHERE trajectory=? AND kind='SCIENTIFIC_HTTP_PEER_OUTCOME' ORDER BY seq DESC LIMIT 1",(t,)).fetchone()
        old=0 if previous is None else __import__('json').loads(previous[0])['consecutive_peer_failures']
        need(type(old)is int and old>=0,'SCIENTIFIC_HTTP_PEER_COUNTER_METADATA')
        streak=old+1 if failed else 0
        self.ledger.event(t,'SCIENTIFIC_HTTP_PEER_OUTCOME',
            dict(role=role,request_id=rid,failed=failed,consecutive_peer_failures=streak,
                 threshold=3,cancel_sent=False,replay=False))
        if failed and streak>=3:
            self.ledger.latch_fault(t,'HTTP_PEER_CONSECUTIVE_3_STOP')
            self.ledger.event(t,'SCIENTIFIC_HTTP_PEER_CONSECUTIVE_3_STOP',
                dict(role=role,request_id=rid,consecutive_peer_failures=streak,threshold=3))
    def note_rejection(self,identity,code,status,custody=None):
        code=code if type(code)is str and re.fullmatch('[A-Z0-9_]{1,160}',code)else'SCIENTIFIC_HTTP_REQUEST_REJECTED'
        status=status if type(status)is int and 400<=status<=599 else 502
        with self.registry_lock:self.rejections[(code,status)]=self.rejections.get((code,status),0)+1
        if identity is None:return  # unknown bearer never chooses a trajectory
        try:
            with self.ledger.tx():
                self.ledger.event(identity[0],'SCIENTIFIC_HTTP_PROTOCOL_REJECTED',
                    {'role':identity[1],'code':code,'status':status,
                     'request_id':None if custody is None else custody.rid,
                     'stage':'PRE_BIND'if custody is None or custody.rid is None else'POST_BIND'})
        except BaseException:
            self.ledger.latch_fault(identity[0],'SCIENTIFIC_HTTP_REJECTION_METADATA_UNKNOWN')
            if custody is not None:custody.failure_metadata_unknown=True
    def new_request(self,connection,identity,payload_sha):
        self.current();need(identity in self.registered,'SCIENTIFIC_HTTP_REGISTERED_REQUEST_ROLE')
        req=NativeHttpRequest(self,connection,identity,payload_sha)
        with self.registry_lock:
            need(not self.listener_stopped,'SCIENTIFIC_HTTP_ADMISSION_STOPPED')
            self.requests[req.handle]=req
        return req
    def finish_request_custody(self,custody,outcome):
        completed=False
        try:custody.finish(outcome);completed=True
        finally:
            with self.registry_lock:
                self.completed+=1;self.delivery_unknown_count+=int(custody.delivery_unknown)
                if not completed or custody.failure_metadata_unknown:self.retained[custody.handle]=custody
                self.requests.pop(custody.handle,None)
    def process_request(self,request,client_address):
        # Track accepted sockets BEFORE handler thread start/body parsing, so a
        # slow or not-yet-scheduled HTTP parser cannot look like a drained server.
        with self.registry_lock:self.accepted_sockets[id(request)]=request
        return super().process_request(request,client_address)
    def finish_request(self,request,client_address):
        try:return super().finish_request(request,client_address)
        finally:
            with self.registry_lock:self.accepted_sockets.pop(id(request),None)
    def service_actions(self):
        # Called by the ORIGINAL stdlib loop after its first select iteration.
        # This is not a CLI/model readiness or native-service backup receipt.
        self.serving.set()
        return super().service_actions()
    def start(self):
        self.current()
        with self.registry_lock:
            need(self.thread is None and not self.listener_stopped,'SCIENTIFIC_HTTP_START_ONCE')
            def serve():
                try:self.serve_forever(poll_interval=.1)
                except BaseException:
                    for t in {t for t,_ in self.registered}:self.ledger.latch_fault(t,'SCIENTIFIC_HTTP_LISTENER_UNKNOWN')
                finally:self.loop_finished.set()
            self.thread=threading.Thread(target=serve,name='native-scientific-http',daemon=False)
            try:self.thread.start()
            except BaseException:
                for t in {t for t,_ in self.registered}:self.ledger.latch_fault(t,'SCIENTIFIC_HTTP_START_FAILED_RETAIN')
                raise
        while not self.serving.wait(.02):
            need(not self.loop_finished.is_set(),'SCIENTIFIC_HTTP_START_FAILED_RETAIN')
        self._record_lifecycle('NATIVE_SCIENTIFIC_HTTP_STARTED')
        self.started=True
    def stop_listener(self):
        self.current()
        with self.registry_lock:
            if self.listener_stopped:return
            self.listener_stopped=True;thread=self.thread
        if thread is not None:
            if self.serving.is_set():self.shutdown()
            if thread.ident is not None:thread.join()
        # Existing handler/transport stacks remain live; no gate/CLI shutdown,
        # cancel, child signal, iterator close or native terminal is issued.
    def status(self):
        with self.registry_lock:
            requests=list(self.requests.values());retained=list(self.retained.values())
            accepted=len(self.accepted_sockets);completed=self.completed;lost=self.delivery_unknown_count
            rejections=[{'code':c,'status':s,'count':n}for(c,s),n in sorted(self.rejections.items())]
        return {'active_http_handlers':[r.status()for r in requests],
                'retained_http_metadata':[r.status()for r in retained],
                'accepted_http_connections':accepted,
                'completed_http_handlers':completed,'delivery_unknown_handlers':lost,
                'listener_stopped':self.listener_stopped,'closed':self.closed,
                'started':self.started,'lifecycle_storage_unknown':self.lifecycle_storage_unknown,
                'network_closed':self.network_closed,'retirement_attempted':self.retire_attempted,
                'protocol_rejections':rejections,
                'models_sent_by_http_component':0,'heartbeats_or_cli_timeout_override':True,
                'cli_timeout_override':False,'budget_park_sse_comments':True,
                'all_stream_waits_keepalive':True,'peer_consecutive_stop_threshold':3,
                'heartbeat_interval_seconds':HEARTBEAT_SECONDS,'delivery_write_timeout_seconds':DELIVERY_WRITE_SECONDS}
    def trajectory_park_ready(self,trajectory):
        """Drain real model delivery before freezing its receiving CLI.

        An original unadmitted budget waiter stays live across the same cut;
        SETTLED alone does not prove its final SSE bytes have been delivered.
        Parsing/unknown accepted sockets conservatively defer writer freeze.
        No client OBSERVED/native-tool/cold-restore proof is invented here.
        """
        self.current()
        need(trajectory in {t for t,_ in self.registered},'SCIENTIFIC_HTTP_REGISTERED_PARK_TRAJECTORY')
        with self.registry_lock:
            requests=list(self.requests.values());retained=list(self.retained.values())
            accepted=set(self.accepted_sockets)
        known={id(r.connection)for r in requests}
        unattributed=len(accepted-known);deliveries=0;waiters=0
        with self.ledger.mutex:
            fault=self.ledger.admission_fault(trajectory)is not None
            for r in requests:
                if r.identity[0]!=trajectory:continue
                status=r.status()
                if status['finished']:continue
                state=None if r.rid is None else self.ledger.db.execute('SELECT state FROM requests WHERE id=?',(r.rid,)).fetchone()
                pause=self.gate.budget_pause(*r.identity)
                if r.rid is not None and state is None and pause['paused']and pause['request_id']==r.rid:waiters+=1
                else:deliveries+=1
        retained_count=sum(r.identity[0]==trajectory for r in retained)
        return {'safe_to_park_writers':not(fault or unattributed or deliveries or retained_count),
                'unattributed_accepted_connections':unattributed,'active_model_deliveries':deliveries,
                'original_budget_waiters':waiters,'retained_http_metadata':retained_count}
    def close_after_drained(self):
        self.current();need(self.listener_stopped,'SCIENTIFIC_HTTP_STOP_LISTENER_FIRST')
        with self.registry_lock:
            need(not self.requests and not self.accepted_sockets,'SCIENTIFIC_HTTP_ACCEPTED_HANDLERS_RETAIN_CUSTODY')
            need(not self.retained,'SCIENTIFIC_HTTP_METADATA_CUSTODY_UNKNOWN_RETAIN')
        with self.ledger.mutex:
            for t in {t for t,_ in self.registered}:
                n=self.ledger.db.execute("SELECT COUNT(*) FROM requests WHERE trajectory=? AND state IN ('RESERVED','SENT','UNKNOWN')",(t,)).fetchone()[0]
                need(n==0,'SCIENTIFIC_HTTP_NATIVE_REQUESTS_RETAIN_CUSTODY')
        need(not self.retire_attempted,'SCIENTIFIC_HTTP_RETIREMENT_NO_RETRY')
        need(not self.lifecycle_storage_unknown,'SCIENTIFIC_HTTP_LIFECYCLE_UNKNOWN_RETAIN')
        self.retire_attempted=True
        self.server_close();self.network_closed=True
        self._record_lifecycle('NATIVE_SCIENTIFIC_HTTP_DRAINED_CLOSED')
        self.ledger.release_native_service(self.scope);self.closed=True
    def handle_error(self,request,client_address):
        # Stdlib's default prints raw traceback/messages. A framework handler
        # fault has no raw diagnostic permission here; hold all registered roles.
        for t in {t for t,_ in self.registered}:self.ledger.latch_fault(t,'SCIENTIFIC_HTTP_HANDLER_UNKNOWN')
        self.gate.notify()
