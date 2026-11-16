"""Cold-only original native bridge transport; opaque SDK state stays in SDK.

No TurnState.begin/configure/refresh/finish, archive inspection, cleanup, TERM,
cancel, replay or new logical turn. Normal fresh branch returns immediately.
"""
from pathlib import Path
import hashlib,json,os,socket,stat,subprocess,threading


def need(ok,code):
    if not ok:raise ValueError(code)


def _descriptor():
    path=os.environ.get('COUNT14_COLD_SDK_RESTORE_FILE');pin=os.environ.get('COUNT14_COLD_SDK_RESTORE_SHA256')
    if path is None and pin is None:return None
    need(path=='/run/count14-dynteam/cold-sdk-restore.json'and type(pin)is str and len(pin)==64,'COLD_SDK_BRIDGE_FIXED_DESCRIPTOR_PIN')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode)and s.st_uid==0 and not s.st_mode&0o222 and s.st_nlink==1 and s.st_size<=16384,'COLD_SDK_BRIDGE_HOST_OWNED_RO_METADATA')
        raw=os.read(fd,16385);after=os.fstat(fd)
        need(len(raw)==s.st_size and (s.st_dev,s.st_ino,s.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_mtime_ns)and hashlib.sha256(raw).hexdigest()==pin,'COLD_SDK_BRIDGE_DESCRIPTOR_CHANGED')
        v=json.loads(raw);need(v['schema']=='count14-formal-cold-sdk-load-control-v1'and v['no_prompt']is True and v['no_fallback']is True,'COLD_SDK_BRIDGE_EXACT_LOAD_DESCRIPTOR')
        return v
    finally:os.close(fd)


def serve_if_cold(server,*,sock_path,child_cmd,child_popen_kwargs,lifecycle):
    binding=_descriptor()
    if binding is None:return False
    need(os.geteuid()==0 and child_popen_kwargs.get('user')==10000 and child_popen_kwargs.get('group')==10000,
         'COLD_SDK_BRIDGE_ORIGINAL_PRIVILEGE_DROP_NO_ELEVATION')
    route=lifecycle.route
    need(route['trajectory_id']==binding['trajectory']and route['role_slot']==binding['role'],
         'COLD_SDK_BRIDGE_SAME_NATIVE_ROUTE')
    # These are original native control/credential records, consumed ONLY in
    # the normal native bridge runtime. The host coordinator never opens them.
    identity=json.loads(Path(os.environ['ACP_IDENTITY_FILE']).read_bytes())
    current=json.loads((Path(sock_path).parent/'current-turn.json').read_bytes())
    digest=lambda v:hashlib.sha256(json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    base='70e2ca54c078597e3314755064d2ef1a83344c8e'
    need(current['turn_id']==binding['native_turn']and
         digest([base,binding['trajectory'],binding['role'],identity['username']])==binding['logical_birth_sha256']and
         digest([base,binding['trajectory'],binding['role'],current['turn_id']])==binding['native_turn_sha256'],
         'COLD_SDK_BRIDGE_ORIGINAL_ACCOUNT_AND_TURN_NOT_REGENERATED')
    turn=Path(os.environ['ACP_TRAJECTORY_DIR'])/current['turn_id']
    need(turn.resolve()==turn and turn.is_dir()and not turn.is_symlink(),'COLD_SDK_BRIDGE_RETAINED_ORIGINAL_TURN_ONLY')
    # One explicit original load connection. A failed/disconnected prefix is
    # retained; there is no second accept/CLI/retry or cleanup loop.
    client,_=server.accept()
    env=os.environ.copy();env.update(GITEA_TOKEN=identity['gitea_token'],MATTERMOST_TOKEN=identity['mattermost_token'],
        WORKER_ACCOUNT=identity['username'],ACP_TURN_ID=turn.name)
    proc=subprocess.Popen(child_cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        bufsize=0,close_fds=True,env=env,start_new_session=True,**child_popen_kwargs)
    lifecycle.born(proc,identity,turn) # existing exact host peer/direct-child gate
    failures=[]
    def copy_bytes(direction):
        pending=b''
        try:
            while True:
                raw=client.recv(65536)if direction=='input'else proc.stdout.read(65536)
                if not raw:break
                pending+=raw;lines=pending.split(b'\n');pending=lines.pop()
                need(len(pending)<=16*1024*1024,'COLD_SDK_ACP_FINITE_CONTROL_LINE')
                lifecycle.observe_control(proc,lines,direction) # original control fields only
                if direction=='input':proc.stdin.write(raw);proc.stdin.flush()
                else:client.sendall(raw)
        except Exception as error:failures.append(type(error).__name__)
        finally:
            if direction=='input':
                try:proc.stdin.close()
                except OSError:pass
            else:
                try:client.shutdown(socket.SHUT_WR)
                except OSError:pass
    incoming=threading.Thread(target=copy_bytes,args=('input',),daemon=True);incoming.start()
    copy_bytes('output')
    # Waiting does not send signals or fake old ARCHIVED_END. Any surviving
    # SDK/Popen/tool/unknown remains original custody and blocks future plans.
    proc.wait();incoming.join(timeout=2)
    need(not incoming.is_alive()and not failures,'COLD_SDK_TRANSPORT_PARTIAL_RETAINED_NO_CLEANUP')
    client.close();return True
