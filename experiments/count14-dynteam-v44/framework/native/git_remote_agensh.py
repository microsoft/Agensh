#!/usr/bin/env python3
"""Git remote helper for the single fixed UDS repository. Stdlib-only worker code.
Install as git-remote-agensh. Logical URL MUST be agensh::registered; no URL/path
is transmitted to the host broker. Secrets/data are never printed as diagnostics.
"""
import json,os,socket,sys,threading

def main():
    # Git strips the transport:: prefix before invoking a remote helper.
    if len(sys.argv)!=3 or sys.argv[2]!='registered':return 78
    sockpath=os.environ['AGENSH_GIT_SOCKET'];keypath=os.environ['AGENSH_BRIDGE_CAPABILITY_FILE']
    fd=os.open(keypath,os.O_RDONLY|os.O_NOFOLLOW)
    try:key=os.read(fd,4096).decode().strip()
    finally:os.close(fd)
    def line():
        b=bytearray()
        while not b.endswith(b'\n'):
            x=os.read(0,1)
            if not x:return bytes(b)
            b+=x
            if len(b)>4096:raise ValueError()
        return bytes(b)
    while True:
        command=line()
        if not command:return 0
        if command==b'capabilities\n':os.write(1,b'connect\n\n');continue
        if command not in (b'connect git-upload-pack\n',b'connect git-receive-pack\n'):return 78
        method=command.decode().strip().split(' ',1)[1];s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect(sockpath)
        s.sendall(json.dumps({'schema':'agensh-worker-bridge-v1','method':method,'capability':key,'payload':{}},separators=(',',':')).encode()+b'\n')
        header=bytearray()
        while not header.endswith(b'\n'):
            b=s.recv(1)
            if not b or len(header)>=16384:return 78
            header.extend(b)
        if header!=b'OK\n':return 78
        os.write(1,b'\n')
        def send():
            try:
                for b in iter(lambda:os.read(0,65536),b''):s.sendall(b)
                s.shutdown(socket.SHUT_WR)
            except OSError:pass
        t=threading.Thread(target=send,daemon=True);t.start()
        try:
            for b in iter(lambda:s.recv(65536),b''):
                view=memoryview(b)
                while view:n=os.write(1,view);view=view[n:]
        finally:s.close()
        return 0
if __name__=='__main__':
    try:sys.exit(main())
    except Exception:sys.stderr.write('AGENSH_GIT_BRIDGE_REFUSED\n');sys.exit(78)
