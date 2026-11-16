#!/usr/bin/env python3
"""Finite stdlib-only control child of the registered ORIGINAL spawn shell.

No model, payload, task, argv inspection, signal or retry. Shell invokes this
with exec in command substitution, so SO_PEERCRED's parent is the exact native
launcher (not an unbounded ancestry search or a worker-supplied PID).
"""
from pathlib import Path
import hashlib
import http.client
import json
import os
import socket
import stat
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from native_spawn_protocol import BASE,checked_spawn


class _Unix(http.client.HTTPConnection):
    def __init__(self,path):super().__init__('localhost',timeout=32);self.path=Path(path)
    def connect(self):
        fd=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(32)
            self.sock.connect('/proc/self/fd/'+str(fd)+'/'+self.path.name)
        finally:os.close(fd)


def load_route(path,pin):
    path=Path(path)
    if path.parent.resolve()!=path.parent:raise ValueError('DYNTEAM_NATIVE_SPAWN_ROUTE_CANONICAL')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,8193);after=os.fstat(fd)
        if not(stat.S_ISREG(before.st_mode) and before.st_uid in (0,os.geteuid()) and
            not before.st_mode&0o077 and 0<before.st_size<=8192 and len(raw)==before.st_size and
            (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and hashlib.sha256(raw).hexdigest()==pin):
            raise ValueError('DYNTEAM_NATIVE_SPAWN_ROUTE_PIN_MODE')
    finally:os.close(fd)
    row=json.loads(raw)
    if not(type(row) is dict and set(row)=={'schema','source_commit','trajectory_id','control_socket'} and
        row['schema']=='count14-native-spawn-client-route-v1' and row['source_commit']==BASE and
        type(row['control_socket']) is str and Path(row['control_socket']).is_absolute()):
        raise ValueError('DYNTEAM_NATIVE_SPAWN_ROUTE_SCHEMA')
    return row


def request(route,event,slot=0,ordinal=0,nonce='0'*32,reuse=False,succeeded=False,container_ids=None):
    row=dict(schema='count14-native-spawn-control-v2',source_commit=BASE,trajectory_id=route['trajectory_id'],
        role_slot='worker-00',event=event,worker_slot=slot,spawn_ordinal=ordinal,
        operation_id=nonce,reuse=reuse,succeeded=succeeded,container_ids=[] if container_ids is None else container_ids)
    checked_spawn(row);raw=json.dumps(row,separators=(',',':')).encode()
    client=_Unix(route['control_socket'])
    try:
        client.request('POST','/native-spawn-control',body=raw,headers={'Content-Type':'application/json'})
        response=client.getresponse();data=response.read(2049)
        if response.status!=200 or len(data)>2048:raise ValueError('DYNTEAM_NATIVE_SPAWN_RECEIPT_REFUSED')
        result=json.loads(data)
        if not(result.get('schema')=='count14-native-spawn-control-ack-v1' and
            result.get('binding_sha256')==hashlib.sha256(raw).hexdigest() and
            result.get('status') in ('RUNNING','HOLD','FINAL','ALLOW','RETAINED','DONE') and
            type(result.get('active_seconds')) is int and result['active_seconds']>=0 and
            type(result.get('operation_id')) is str and len(result['operation_id'])==32 and
            all(c in '0123456789abcdef' for c in result['operation_id'])):
            raise ValueError('DYNTEAM_NATIVE_SPAWN_RECEIPT_BINDING')
        return result
    finally:client.close()


def main(args):
    route=load_route(os.environ['COUNT14_NATIVE_SPAWN_ROUTE'],os.environ['COUNT14_NATIVE_SPAWN_ROUTE_SHA256'])
    if args==['READ']:result=request(route,'READ')
    elif len(args)==4 and args[0]=='BEGIN' and args[3] in ('0','1'):
        result=request(route,'BEGIN',int(args[1]),int(args[2]),reuse=args[3]=='1')
    elif len(args)==5 and args[0]=='FINISH' and args[4] in ('0','1'):
        result=request(route,'FINISH',int(args[1]),int(args[2]),nonce=args[3],succeeded=args[4]=='1')
    elif len(args)==6 and args[0]=='RETIRE_BEGIN':
        result=request(route,'RETIRE_BEGIN',int(args[1]),int(args[2]),nonce=args[3],container_ids=args[4:])
    elif len(args)==4 and args[0]=='RETIRE_POLL':
        result=request(route,'RETIRE_POLL',int(args[1]),int(args[2]),nonce=args[3])
    else:raise ValueError('DYNTEAM_NATIVE_SPAWN_CLIENT_FIXED_ARGUMENTS')
    print(result['status'],result['active_seconds'],result['operation_id'])


if __name__=='__main__':
    try:main(sys.argv[1:])
    except Exception as error:
        # No message, traceback/private paths, command or scientific body.
        print(json.dumps({'PUBLIC_code':'DYNTEAM_NATIVE_SPAWN_CONTROL_FAILED_RETAIN',
                          'exception_type':type(error).__name__}),file=sys.stderr)
        raise SystemExit(2)
