#!/usr/bin/env python3
"""Independent feasibility relay. Stdlib only; no count14 imports or changes.

One upstream send per accepted request, no redirects/proxy inheritance/retries.
SQLite retains hashes + usage only. Continuation text exists only in bounded
memory; restart loses that state and unknown IDs are refused (never replayed).
"""
import argparse
import copy
import fcntl
import hashlib
import hmac
import http.server
import json
import os
from pathlib import Path
import sqlite3
import stat
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from protocol import (Rejected,need,wire,uid,prepare,nonstream,StreamMapper,
                      base_response,assistant_history,mapped_usage)

MAX_BODY=8*1024*1024
MAX_REPLY=16*1024*1024

def digest(value):return hashlib.sha256(wire(value)).hexdigest()

def private_file(path):
    p=Path(path);s=p.lstat()
    need(stat.S_ISREG(s.st_mode)and not stat.S_ISLNK(s.st_mode)and s.st_uid==os.geteuid()and
        s.st_nlink==1 and s.st_mode&0o077==0,'PRIVATE_FILE_REQUIRED')
    return p.read_bytes()

def strict_json(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'DUPLICATE_JSON_KEY');out[k]=v
        return out
    try:return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Rejected('NONFINITE_JSON')))
    except (ValueError,UnicodeError):raise Rejected('INVALID_JSON')from None

class UsageLedger:
    def __init__(self,path):
        self.path=Path(path);self.lock=threading.RLock()
        parent=self.path.parent;parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        s=parent.lstat();need(stat.S_ISDIR(s.st_mode)and not stat.S_ISLNK(s.st_mode)and s.st_uid==os.geteuid()and s.st_mode&0o077==0,'PRIVATE_LEDGER_DIRECTORY')
        if not self.path.exists():
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(fd)
        else:private_file(self.path)
        self.lockfd=os.open(str(self.path)+'.owner.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(self.lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lockfd);raise Rejected('RELAY_LEDGER_ALREADY_OWNED')from None
        self.db=sqlite3.connect(self.path,check_same_thread=False,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,at_ns INTEGER NOT NULL,rid TEXT NOT NULL,trajectory TEXT NOT NULL,agent TEXT NOT NULL,kind TEXT NOT NULL,request_sha TEXT NOT NULL,response_sha TEXT,input_tokens INTEGER,output_tokens INTEGER,total_tokens INTEGER,code TEXT)')
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS exactly_one_begin ON events(rid) WHERE kind='SENT'")
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS exactly_one_terminal ON events(rid) WHERE kind<>'SENT'")
    def record(self,rid,identity,kind,request_sha,*,response=None,usage=None,code=None):
        with self.lock:
            self.db.execute('INSERT INTO events(at_ns,rid,trajectory,agent,kind,request_sha,response_sha,input_tokens,output_tokens,total_tokens,code) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (time.time_ns(),rid,*identity,kind,request_sha,digest(response)if response is not None else None,
                 usage['input_tokens']if usage is not None else None,usage['output_tokens']if usage is not None else None,
                 usage['total_tokens']if usage is not None else None,code))
    def begin(self,rid,identity,request_sha,limit):
        with self.lock:
            if limit is not None:
                need(self.db.execute("SELECT COUNT(*) FROM events WHERE kind='SENT'").fetchone()[0]<limit,'REAL_REQUEST_LIMIT_REACHED')
            self.record(rid,identity,'SENT',request_sha)
    def totals(self):
        with self.lock:
            # Explicit unresolved count, not invented zero-cost terminal usage.
            rows=self.db.execute("SELECT trajectory,agent,SUM(kind='SENT')AS requests,SUM(kind IN ('COMPLETED','ACCOUNTED_ERROR'))AS accounted,SUM(COALESCE(input_tokens,0)),SUM(COALESCE(output_tokens,0)) FROM events GROUP BY trajectory,agent").fetchall()
            return [dict(trajectory=r[0],agent=r[1],requests=r[2],accounted_requests=r[3],unknown_or_inflight=r[2]-r[3],input_tokens=r[4],output_tokens=r[5],category='agensh_feasibility')for r in rows]
    def close(self):
        self.db.close();os.close(self.lockfd)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class ChatTransport:
    def __init__(self,base,token,*,auth_style='bearer',timeout=120):
        u=urllib.parse.urlsplit(base)
        need(u.scheme in ('http','https')and u.hostname and not u.username and not u.password and not u.query and not u.fragment,'UPSTREAM_BASE_URL')
        need(u.path.rstrip('/').endswith('/v1'),'UPSTREAM_BASE_MUST_END_V1')
        need(auth_style in ('bearer','api-key'),'AUTH_STYLE')
        self.url=base.rstrip('/')+'/chat/completions';self.token=token;self.auth_style=auth_style;self.timeout=timeout
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def __call__(self,body):
        headers={'Content-Type':'application/json','Accept':'text/event-stream'if body['stream']else'application/json'}
        headers['Authorization'if self.auth_style=='bearer'else'api-key']=('Bearer 'if self.auth_style=='bearer'else'')+self.token
        request=urllib.request.Request(self.url,data=wire(body),headers=headers,method='POST')
        try:response=self.opener.open(request,timeout=self.timeout)
        except urllib.error.HTTPError as e:
            e.close();raise Rejected('UPSTREAM_HTTP_'+str(e.code),502)from None
        except (urllib.error.URLError,TimeoutError,OSError):raise Rejected('UPSTREAM_TRANSPORT_UNKNOWN',502)from None
        if not body['stream']:
            with response:
                raw=response.read(MAX_REPLY+1);need(len(raw)<=MAX_REPLY,'UPSTREAM_RESPONSE_BOUND')
                return strict_json(raw)
        def chunks():
            with response:
                need(response.headers.get_content_type()=='text/event-stream','UPSTREAM_NOT_SSE')
                total=0;data=[];done=False
                while True:
                    raw=response.readline(MAX_BODY+1)
                    if not raw:break
                    total+=len(raw);need(total<=MAX_REPLY and len(raw)<=MAX_BODY,'UPSTREAM_SSE_BOUND')
                    line=raw.decode('utf-8').rstrip('\r\n')
                    if line=='':
                        if data:
                            value='\n'.join(data);data=[]
                            if value=='[DONE]':done=True;break
                            chunk=strict_json(value);need('error'not in chunk,'UPSTREAM_STREAM_ERROR');yield chunk
                    elif line.startswith('data:'):data.append(line[5:].lstrip(' '))
                    elif line.startswith((':','event:','id:','retry:')):pass
                    else:raise Rejected('UPSTREAM_SSE_FORMAT',502)
                need(done,'UPSTREAM_STREAM_MISSING_DONE')
        return chunks()

class RelayEngine:
    def __init__(self,transport,ledger,*,model,max_output=4096,max_states=256,max_inflight=2,request_limit=None):
        self.transport,self.ledger,self.model=transport,ledger,model
        self.request_limit=request_limit
        self.max_output,self.max_states=max_output,max_states;self.states={};self.lock=threading.Lock();self.reserved=0
        self.capacity=threading.BoundedSemaphore(max_inflight)
    def lookup(self,ident,identity):
        with self.lock:
            state=self.states.get(ident)
            if state is None or state['identity']!=identity:raise Rejected('RESPONSE_NOT_FOUND',404)
            return copy.deepcopy(state)
    def retain_continuation(self,request,rid,identity,response,messages):
        # Default wire behavior is unchanged; only scientific PRIVATE custody
        # overrides this hook, without rewriting request/response or Chat body.
        if request.get('store',True):
            with self.lock:
                self.states[rid]=dict(identity=identity,response=copy.deepcopy(response),history=messages+[assistant_history(response)])
    def run(self,request,identity,emit=None):
        need(type(identity)is tuple and len(identity)==2 and all(isinstance(s,str)and s for s in identity),'TRUSTED_IDENTITY_REQUIRED')
        need(type(request)is dict,'JSON_OBJECT_REQUIRED')
        previous=request.get('previous_response_id')
        need(previous is None or (isinstance(previous,str)and 0<len(previous)<=128),'PREVIOUS_RESPONSE_ID')
        history=[]if previous is None else self.lookup(previous,identity)['history']
        chat,messages=prepare(request,history,model=self.model,max_output=self.max_output)
        if emit is None:need(not chat['stream'],'STREAM_EMITTER_REQUIRED')
        if not self.capacity.acquire(blocking=False):raise Rejected('RELAY_CAPACITY',429)
        reserved=False;rid=uid('resp_');request_sha=digest(request);sent=False;usage=None;mapper=None
        try:
            with self.lock:
                if len(self.states)+self.reserved>=self.max_states:raise Rejected('CONTINUATION_STATE_CAPACITY',429)
                self.reserved+=1;reserved=True
            response=base_response(request,rid)
            self.ledger.begin(rid,identity,request_sha,self.request_limit);sent=True
            if chat['stream']:
                mapper=StreamMapper(response,emit)
                for chunk in self.transport(chat):
                    if chunk.get('usage')is not None:usage=mapped_usage(chunk['usage'])
                    mapper.feed(chunk)
                response=mapper.done()
            else:
                raw=self.transport(chat)
                if type(raw)is dict and raw.get('usage')is not None:usage=mapped_usage(raw['usage'])
                response=nonstream(response,raw)
            usage=response['usage']
            # Persist exact counts before returning a successful response. No
            # response bodies, prompts or tools are written to the ledger.
            self.ledger.record(rid,identity,'COMPLETED',request_sha,response=response,usage=usage)
            sent=False
            self.retain_continuation(request,rid,identity,response,messages)
            if mapper is not None:mapper.event('response.'+response['status'],response=response)
            return response
        except Exception as exc:
            code=exc.code if isinstance(exc,Rejected)else'RELAY_INTERNAL_UNKNOWN'
            if sent:
                self.ledger.record(rid,identity,'ACCOUNTED_ERROR'if usage is not None else'UNKNOWN',request_sha,usage=usage,code=code)
            if mapper is not None:
                failed=base_response(request,rid);failed.update(status='failed',error=dict(type='server_error',code=code,message=code))
                mapper.event('response.failed',response=failed)
            if isinstance(exc,Rejected):raise
            raise Rejected(code,502)from None
        finally:
            if reserved:
                with self.lock:self.reserved-=1
            self.capacity.release()

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass # No raw paths/headers/errors or model content.
    def send_json(self,value,status=200):
        raw=wire(value);self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def identity(self):
        auth=self.headers.get('Authorization','')
        for token,identity in self.server.identities.items():
            if hmac.compare_digest(auth,'Bearer '+token):return identity
        raise Rejected('AUTHENTICATION_REQUIRED',401)
    def do_GET(self):
        try:
            if self.path=='/healthz':self.send_json(dict(status='ok',purpose='agensh_feasibility'));return
            identity=self.identity()
            if self.path=='/admin/usage':self.send_json([r for r in self.server.engine.ledger.totals()if(r['trajectory'],r['agent'])==identity]);return
            prefix='/v1/responses/'
            if self.path.startswith(prefix):self.send_json(self.server.engine.lookup(self.path[len(prefix):],identity)['response']);return
            raise Rejected('ROUTE_NOT_FOUND',404)
        except Rejected as exc:self.send_json(dict(error=dict(type='invalid_request_error',code=exc.code,message=exc.code)),exc.status)
    def do_POST(self):
        started=False;disconnected=False
        try:
            identity=self.identity();need(self.path=='/v1/responses','ROUTE_NOT_FOUND')
            need(not self.headers.get('Transfer-Encoding'),'CHUNKED_REQUEST_UNSUPPORTED')
            need(self.headers.get_content_type()=='application/json','JSON_CONTENT_TYPE_REQUIRED')
            lengths=self.headers.get_all('Content-Length',[]);need(len(lengths)==1 and lengths[0].isdigit(),'CONTENT_LENGTH_REQUIRED')
            length=int(lengths[0]);need(0<length<=MAX_BODY,'REQUEST_BODY_BOUND')
            raw=self.rfile.read(length);need(len(raw)==length,'REQUEST_BODY_INCOMPLETE');request=strict_json(raw)
            need(type(request)is dict,'JSON_OBJECT_REQUIRED')
            # Client metadata never selects the billing identity.
            metadata=request.get('metadata',{});need(type(metadata)is dict,'METADATA_OBJECT')
            for k,v in zip(('trajectory_id','agent_id'),identity):need(metadata.get(k,v)==v,'METADATA_IDENTITY_MISMATCH')
            emit=None
            if request.get('stream')is True:
                def emit(event):
                    nonlocal started,disconnected
                    if disconnected:return
                    try:
                        if not started:
                            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-cache');self.send_header('Connection','close');self.end_headers();self.close_connection=True;started=True
                        self.wfile.write(b'event: '+event['type'].encode()+b'\ndata: '+wire(event)+b'\n\n');self.wfile.flush()
                    except (BrokenPipeError,ConnectionResetError,OSError):disconnected=True
            response=self.server.engine.run(request,identity,emit=emit)
            if not started and not disconnected:self.send_json(response)
        except Rejected as exc:
            if not started:self.close_connection=True;self.send_json(dict(error=dict(type='invalid_request_error',code=exc.code,message=exc.code)),exc.status)
        except (BrokenPipeError,ConnectionResetError,OSError):self.close_connection=True

class Server(http.server.ThreadingHTTPServer):
    daemon_threads=False
    def __init__(self,address,engine,identities):
        super().__init__(address,Handler);self.engine,self.identities=engine,identities

def main():
    p=argparse.ArgumentParser();p.add_argument('--listen',default='127.0.0.1');p.add_argument('--port',type=int,required=True)
    p.add_argument('--upstream',required=True,help='Trusted Chat base ending /v1; no credentials in URL')
    p.add_argument('--upstream-key-file',required=True);p.add_argument('--identities-file',required=True)
    p.add_argument('--ledger',required=True);p.add_argument('--model',required=True);p.add_argument('--max-output',type=int,default=4096)
    p.add_argument('--request-limit',type=int,default=6,help='Persistent hard send cap; micro-test defaults to six')
    p.add_argument('--auth-style',choices=('bearer','api-key'),default='bearer');args=p.parse_args();os.umask(0o077);need(args.request_limit>0 and 0<args.max_output<=16384,'LAUNCH_BOUNDS')
    token=private_file(args.upstream_key_file).decode().strip();need(bool(token),'EMPTY_UPSTREAM_KEY')
    entries=strict_json(private_file(args.identities_file));need(type(entries)is list and 0<len(entries)<=32,'IDENTITIES_BOUND')
    identities={}
    for row in entries:
        need(type(row)is dict and set(row)=={'local_bearer','trajectory_id','agent_id'}and all(isinstance(v,str)and v for v in row.values()),'IDENTITY_FIELDS')
        key=row['local_bearer'];need(len(key)>=32 and key not in identities,'LOCAL_BEARER_REQUIRED');identities[key]=(row['trajectory_id'],row['agent_id'])
    ledger=UsageLedger(args.ledger);engine=RelayEngine(ChatTransport(args.upstream,token,auth_style=args.auth_style),ledger,model=args.model,max_output=args.max_output,request_limit=args.request_limit)
    server=Server((args.listen,args.port),engine,identities)
    print(json.dumps(dict(schema='agensh-relay-start-v1',pid=os.getpid(),listen=args.listen,port=server.server_port,model=args.model,retries=0,identities=len(identities),category='agensh_feasibility')),flush=True)
    try:server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt:pass
    finally:server.server_close();ledger.close()

if __name__=='__main__':main()
