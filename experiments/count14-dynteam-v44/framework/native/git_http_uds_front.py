#!/usr/bin/env python3
"""Worker-loopback smart Git front. Fixed UDS only; never a network proxy.

Native Git/libcurl talks HTTP to loopback, then fixed action/body travels over
this role's UDS. No backend credential/origin is known here. Instantiate once
inside the worker namespace before native CLI; bind loopback only, never 0.0.0.0.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import argparse,json,os,socket,struct,tempfile,threading
from common import sha,need,Refused,ident,wire,strict,private_dir,unix_socket_address
from bridge import HEADER_CAP,PACK_CAP
from native_git_http import SCHEMA,ACTIONS,BLOCK,read_exact

def validate_native_end(value):
 need(type(value)is dict and value.get('ok')is True and set(value)in({'ok'},{'ok','physical_terminal','operation_id'}),'GIT_FRONT_NATIVE_END_FRAME')
 # Legacy host framing is accepted for cold migration compatibility only. Its
 # physical_terminal/operation_id fields are not tool admission or accounting.

class WorkerGitFront:
 def __init__(self,socket_path,capability_file,private_home,*,organization,repository,port=0):
  ident(organization);ident(repository);self.socket=Path(socket_path);need(self.socket.is_absolute()and self.socket.resolve()==self.socket,'GIT_FRONT_FIXED_SOCKET')
  fd=os.open(capability_file,os.O_RDONLY|os.O_NOFOLLOW)
  try:self.capability=os.read(fd,4097).decode().strip();need(len(self.capability)>=48 and len(self.capability)<=4096,'GIT_FRONT_CAPABILITY_BOUND')
  finally:os.close(fd)
  self.home=private_dir(private_home,create=True);self.prefix='/'+organization+'/'+repository+'.git/';self.thread=None;self.slots=threading.BoundedSemaphore(2);owner=self
  class Handler(BaseHTTPRequestHandler):
   protocol_version='HTTP/1.1'
   def log_message(self,*args):pass
   def do_CONNECT(self):self.reject()
   def do_PUT(self):self.reject()
   def do_DELETE(self):self.reject()
   def do_HEAD(self):self.reject()
   def do_GET(self):self.run_git()
   def do_POST(self):self.run_git()
   def reject(self):
    self.close_connection=True;self.send_response(403);self.send_header('Content-Length','0');self.send_header('Connection','close');self.end_headers()
   def body(self,output):
    lengths=self.headers.get_all('Content-Length')or[];encodings=self.headers.get_all('Transfer-Encoding')or[]
    need(len(lengths)<=1 and len(encodings)<=1 and not(lengths and encodings),'GIT_FRONT_HTTP_FRAMING')
    total=0
    if encodings:
     need(encodings==['chunked'],'GIT_FRONT_FIXED_CHUNKED')
     while True:
      line=self.rfile.readline(64);need(line.endswith(b'\r\n')and len(line)<=32 and all(c in b'0123456789abcdefABCDEF'for c in line[:-2])and line[:-2],'GIT_FRONT_CHUNK_HEADER')
      size=int(line[:-2],16)
      if not size:need(self.rfile.readline(4)==b'\r\n','GIT_FRONT_NO_TRAILERS');break
      total+=size;need(total<=PACK_CAP,'GIT_FRONT_BODY_BOUND');remaining=size
      while remaining:
       chunk=read_exact(self.rfile,min(BLOCK,remaining));output.write(chunk);remaining-=len(chunk)
      need(read_exact(self.rfile,2)==b'\r\n','GIT_FRONT_CHUNK_DELIMITER')
    else:
     n=int(lengths[0])if lengths else 0;need(0<=n<=PACK_CAP,'GIT_FRONT_BODY_BOUND');total=n
     while n:
      chunk=read_exact(self.rfile,min(BLOCK,n));output.write(chunk);n-=len(chunk)
    return total
   def run_git(self):
    slot=False;headers_sent=False
    try:
     matches=[key for key,(verb,suffix,_)in ACTIONS.items()if self.command==verb and self.path==owner.prefix+suffix]
     need(len(matches)==1,'GIT_FRONT_FIXED_REPOSITORY_AND_METHOD_ONLY');action=matches[0]
     parents=self.headers.get_all('X-Count14-Native-Parent')or[]
     need(len(parents)<=1,'GIT_FRONT_SINGLE_ORIGINAL_PARENT_HEADER')
     parent=None if not parents else sha(parents[0])
     need(self.headers.get('Content-Encoding','')in('','gzip')and self.headers.get('Git-Protocol','')in('','version=1','version=2'),'GIT_FRONT_FIXED_HEADERS')
     slot=owner.slots.acquire(blocking=False);need(slot,'GIT_FRONT_BACKPRESSURE')
     self.connection.settimeout(120)
     with tempfile.TemporaryFile(dir=owner.home)as payload:
      size=self.body(payload);need(action in('upload','receive')or size==0,'GIT_FRONT_GET_BODY_FORBIDDEN');payload.seek(0)
      with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)as client:
       client.settimeout(120);
       with unix_socket_address(owner.socket)as address:client.connect(address)
       value={'schema':SCHEMA,'capability':owner.capability,'action':action,'size':size,'protocol':self.headers.get('Git-Protocol',''),'content_encoding':self.headers.get('Content-Encoding','')}
       if parent is not None:value['cli_ticket']=parent
       client.sendall(wire(value)+b'\n')
       for chunk in iter(lambda:payload.read(BLOCK),b''):client.sendall(chunk)
       client.shutdown(socket.SHUT_WR)
       with client.makefile('rb',buffering=0)as response:
        line=response.readline(HEADER_CAP+1);need(len(line)<=HEADER_CAP and line.endswith(b'\n'),'GIT_FRONT_RESPONSE_HEADER_BOUND');head=strict(line)
        need(type(head)is dict and set(head)=={'ok','status','content_type'}and head['ok']is True and type(head['status'])is int and 100<=head['status']<=599 and head['content_type']in(ACTIONS[action][2],'text/plain'),'GIT_FRONT_HOST_RESPONSE')
        self.send_response(head['status']);self.send_header('Content-Type',head['content_type']);self.send_header('Transfer-Encoding','chunked');self.send_header('Connection','close');self.end_headers();headers_sent=True
        total=0
        while True:
         n=struct.unpack('!I',read_exact(response,4))[0]
         if not n:break
         total+=n;need(0<n<=BLOCK and total<=PACK_CAP,'GIT_FRONT_RESPONSE_BOUND');chunk=read_exact(response,n)
         self.wfile.write(f'{n:x}\r\n'.encode()+chunk+b'\r\n');self.wfile.flush()
        line=response.readline(HEADER_CAP+1);need(len(line)<=HEADER_CAP and line.endswith(b'\n'),'GIT_FRONT_TERMINAL_BOUND');terminal=strict(line)
        # Ordinary transport EOF/framing only. New native host emits {ok:true};
        # no per-tool receipt, operation identity or physical custody proof.
        validate_native_end(terminal)
        self.wfile.write(b'0\r\n\r\n');self.wfile.flush()
    except Exception:
     # After headers, deliberately do NOT terminate chunked transfer successfully.
     # libcurl/native Git must observe truncation, never a fabricated clean EOF.
     if not headers_sent:
      try:self.reject()
      except OSError:pass
    finally:
     self.close_connection=True
     if slot:owner.slots.release()
  self.server=ThreadingHTTPServer(('127.0.0.1',port),Handler);self.server.daemon_threads=False;self.port=self.server.server_address[1]
 def start(self):
  need(self.thread is None,'GIT_FRONT_ALREADY_STARTED');self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def close_listener(self):
  if self.thread:self.server.shutdown();self.thread.join()
  self.server.server_close()

def main():
 p=argparse.ArgumentParser();p.add_argument('--socket',required=True);p.add_argument('--capability-file',required=True);p.add_argument('--private-home',required=True);p.add_argument('--organization',required=True);p.add_argument('--repository',required=True);p.add_argument('--port',required=True,type=int);args=p.parse_args();need(1<=args.port<=65535,'GIT_FRONT_OWNER_PORT')
 front=WorkerGitFront(args.socket,args.capability_file,args.private_home,organization=args.organization,repository=args.repository,port=args.port);front.server.serve_forever()
if __name__=='__main__':
 try:main()
 except Exception:raise SystemExit('AGENSH_GIT_FRONT_REFUSED')from None
