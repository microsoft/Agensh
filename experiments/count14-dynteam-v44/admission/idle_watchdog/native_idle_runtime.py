"""Finite native watchdog control child. Runtime only; no scientific body export.

The original opaque-rendered MM JSON body passes through stdin unchanged. Only
COUNT/hash/role/type/HTTP/control timestamps persist. No model/API dispatcher.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time


def need(ok, code):
    if not ok: raise ValueError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def read_json(path, maximum=2*1024*1024):
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);raw=os.read(fd,maximum+1);b=os.fstat(fd)
        identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(path.resolve()==path and stat.S_ISREG(a.st_mode) and a.st_uid==os.geteuid() and
             a.st_nlink==1 and 0<len(raw)==a.st_size<=maximum and
             identity(a)==identity(b)==identity(path.lstat()),'IDLE_FIXED_CONTROL_FILE_IDENTITY')
    finally:os.close(fd)
    return json.loads(raw)


def append(path,value):
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    try:
        need(os.write(fd,raw)==len(raw),'IDLE_CONTROL_RECEIPT_WRITE');os.fsync(fd)
    finally:os.close(fd)


class ActiveProjection:
    """Unknown history starts now; wall metadata changes only reset active anchor.

    No wall-mtime is subtracted from active time. Original tick computes wall
    idle using wall-wall, then this projector substitutes active-active input.
    A later observed mtime/wake change conservatively resets to observation now.
    """
    def __init__(self,state=None):self.state={} if state is None else state
    def activity(self,role,mtime_signature,active):
        need(re.fullmatch(r'worker-[0-9]{2}',role) and type(active)is int and active>=0,
             'IDLE_ACTIVE_CLOCK_ROLE_AND_NONNEGATIVE_INTEGER')
        row=self.state.setdefault(role,{})
        old=row.get('activity')
        need(old is None or active>=old['anchor'],'IDLE_ACTIVE_CLOCK_NEVER_REGRESSES')
        if old is None or old['signature']!=mtime_signature:
            row['activity']=dict(signature=mtime_signature,anchor=active)
        return active-row['activity']['anchor']
    def wake(self,role,identity_signature,active):
        row=self.state.setdefault(role,{})
        old=row.get('wake')
        need(old is None or active>=old['anchor'],'IDLE_WAKE_ACTIVE_CLOCK_NEVER_REGRESSES')
        if old is None or old['signature']!=identity_signature:
            row['wake']=dict(signature=identity_signature,anchor=active)
        return row['wake']['anchor']


class Journal:
    def __init__(self,home):
        self.home=Path(home)
        need(self.home.resolve()==self.home and self.home.is_dir() and not self.home.is_symlink(),
             'IDLE_NEW_EXACT_CONTROL_HOME')
        pointer=self.home/'HEAD_CONTROL.json'
        self.state=dict(sequence=0,clock={},attempts={})
        if pointer.exists():
            head=read_json(pointer,4096);name=head['file']
            need(re.fullmatch(r'[0-9]{8}-STATE_PUBLIC.json',name),'IDLE_EXACT_CONTROL_HEAD_FILENAME')
            self.state=read_json(self.home/name)
        self.clock=ActiveProjection(self.state['clock'])
    def save(self):
        self.state['sequence']+=1
        name=f"{self.state['sequence']:08d}-STATE_PUBLIC.json"
        append(self.home/name,self.state)
        # Only the NEW metadata pointer is mutable; historical snapshots and
        # every INTENT/TERMINAL remain append-only. No ledger is involved.
        tmp=self.home/f'.head-{os.getpid()}'
        append(tmp,dict(file=name));os.replace(tmp,self.home/'HEAD_CONTROL.json')


def role_for(control,worker):
    prefix=control['organization']+'-worker'
    need(worker.startswith(prefix) and worker[len(prefix):].isdigit(),'IDLE_EXACT_REGISTERED_STABLE_WORKER')
    slot=int(worker[len(prefix):]);need(1<=slot<=32,'IDLE_ORIGINAL_32_WORKER_SLOTS')
    return 'worker-'+f'{slot-1:02d}'


def owner_live(control):
    pid=control['owner_pid'];root=Path('/proc')/str(pid)
    try:
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        raw=(root/'stat').read_text();start=int(raw[raw.rfind(')')+2:].split()[19])
        return boot==control['owner_boot_id'] and start==control['owner_start_ticks']
    except (OSError,ValueError,IndexError):return False


def admission(home):
    control=read_json(Path(home)/'ADMISSION_PUBLIC.json',8192)
    return control,control['held'] is False and control['closed'] is False and owner_live(control)


def post_once(home,worker,arguments,payload,*,run=subprocess.run):
    """Exactly one physical POST per original attempt; UNKNOWN blocks fallback.

    The native consider() may request its original channel fallback only after
    no POST happened, or an explicit non-acceptance status. Payload remains the
    exact original jq-rendered bytes; no message/response body is persisted.
    """
    control,opened=admission(home)
    if not opened:return 75
    role=role_for(control,worker);tick=read_json(Path(home)/'CURRENT_TICK_PUBLIC.json',8192)
    journal=Journal(home);key=f"{tick['ordinal']}:{role}"
    previous=journal.state['attempts'].get(key,[])
    last=journal.state.get('last_unknown',{}).get(role)
    if not previous and last is not None and tick['active_seconds']-last<600:return 75
    if previous and previous[-1]['terminal'] not in ('REJECTED_NOT_ACCEPTED',):return 75
    need(len(previous)<2,'IDLE_AT_MOST_NATIVE_DM_THEN_NATIVE_FALLBACK')
    args=list(arguments)
    need(args and args[-1]==control['mattermost_origin']+'/api/v4/posts' and
         '-X'in args and args[args.index('-X')+1]=='POST' and '-d'in args,
         'IDLE_ORIGINAL_NATIVE_MM_POST_ENDPOINT_AND_METHOD')
    at=args.index('-d');need(args[at+1]=='COUNT14_OPAQUE_STDIN','IDLE_BODY_ONLY_OPAQUE_STDIN')
    args[at:at+2]=['--data-binary','@-']
    ordinal=len(previous)+1;stem=f"T{tick['ordinal']:08d}-{role}-P{ordinal}"
    intent=dict(schema='count14-native-idle-original-MM-intent-v1',tick=tick['ordinal'],role=role,
        post_ordinal=ordinal,payload_sha256=hashlib.sha256(payload).hexdigest(),automatic_retry=False)
    append(Path(home)/(stem+'-INTENT_PUBLIC.json'),intent)
    previous.append(dict(terminal='INTENT_UNPROVEN',ordinal=ordinal))
    journal.state['attempts'][key]=previous;journal.save()
    terminal='UNKNOWN';code=None;exit_code=None
    try:
        # Same original curl args/headers/body/URL; only finite control timeout
        # and public HTTP status projection replace a discarded response body.
        command=['/usr/bin/curl','--connect-timeout','5','--max-time','15',*args,
                 '--output','/dev/null','--write-out','%{http_code}']
        result=run(command,input=payload,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20)
        exit_code=result.returncode
        if len(result.stdout)<=3 and result.stdout.isdigit():code=int(result.stdout)
        if exit_code==0 and code is not None and 200<=code<300:terminal='DELIVERED'
        elif exit_code==22 and code in (400,401,403,404,405,413,422,429):terminal='REJECTED_NOT_ACCEPTED'
    except (OSError,subprocess.TimeoutExpired):pass
    previous[-1]['terminal']=terminal
    if terminal=='UNKNOWN':journal.state.setdefault('last_unknown',{})[role]=tick['active_seconds']
    journal.save()
    append(Path(home)/(stem+'-TERMINAL_PUBLIC.json'),dict(intent,terminal=terminal,
        http_status=code,exit_code=exit_code,response_body_read=False))
    # UNKNOWN blocks ALL native fallback for this worker/tick, but native next
    # 600-active-second nudge remains a new original event, not re-POST.
    return 0 if terminal=='DELIVERED' else 22 if terminal=='REJECTED_NOT_ACCEPTED' else 75


def main(args):
    operation,home,*rest=args
    control=read_json(Path(home)/'ADMISSION_PUBLIC.json',8192)
    tick=read_json(Path(home)/'CURRENT_TICK_PUBLIC.json',8192)
    if operation=='ACTIVITY':
        worker,idle,wall=rest;role=role_for(control,worker)
        idle,wall=int(idle),int(wall)
        signature=None if idle<0 else wall-idle # wall-wall only, opaque mtime metadata
        j=Journal(home);active_idle=j.clock.activity(role,signature,tick['active_seconds']);j.save()
        print(active_idle,tick['active_seconds']);return 0
    if operation=='WAKE':
        worker=rest[0];role=role_for(control,worker)
        raw=sys.stdin.buffer.read(4097);need(len(raw)<=4096,'IDLE_FINITE_IDENTITY_CONTROL_ONLY')
        fields=raw.decode('ascii').split()
        if not fields:return 0 # original retired/pending returns no routing
        need(len(fields)==2 and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',fields[0]) and fields[1].isdigit(),
             'IDLE_ORIGINAL_ACCOUNT_ROUTING_SHAPE')
        j=Journal(home);stamp=j.clock.wake(role,digest(fields),tick['active_seconds']);j.save()
        print(fields[0],stamp);return 0
    if operation=='POST':
        worker,*argv=rest;payload=sys.stdin.buffer.read(2*1024*1024+1)
        need(len(payload)<=2*1024*1024,'IDLE_ORIGINAL_OPAQUE_MESSAGE_FINITE')
        return post_once(home,worker,argv,payload)
    if operation=='BOUNDED':
        # Only original readonly diagnosis/control invocations from the pinned
        # shell; never any scientific CLI or model process.
        need(bool(rest),'IDLE_ORIGINAL_METADATA_PROGRAM_REQUIRED')
        if rest[0]==control['docker_cli']:
            need(rest[1:4]==['--host',control['docker_socket'],'exec'] and
                 len(rest)>6 and rest[4]==control['mysql_container'] and rest[5]=='mysql' and
                 rest[-2]=='-e' and rest[-1].startswith("SELECT COUNT(*) FROM events WHERE agent='"),
                 'IDLE_EXACT_PRIVATE_DOCKER_REGISTERED_MYSQL_COUNT_ONLY')
        elif rest[0]=='/usr/bin/python3':
            need(len(rest)==4 and rest[1]=='-' and
                 Path(rest[2])==Path(control['profile_root'])/'identities'/rest[3],
                 'IDLE_ORIGINAL_FIXED_CURRENT_IDENTITY_METADATA_SCRIPT')
            role_for(control,rest[3])
        elif rest[0]=='/usr/bin/find':
            need(len(rest)==8 and Path(rest[1]).is_relative_to(Path(control['profile_root'])/'agents') and
                 rest[2:]==['-type','f','-name','*.jsonl','-printf',r'%T@\n'],
                 'IDLE_ORIGINAL_LOG_MTIME_ONLY_NO_BODY')
        else:raise ValueError('IDLE_ONLY_FIXED_ORIGINAL_METADATA_PROGRAMS')
        try:
            result=subprocess.run(rest,stdin=sys.stdin.buffer,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=15)
            if len(result.stdout)>1024*1024:return 75
            sys.stdout.buffer.write(result.stdout);return result.returncode
        except subprocess.TimeoutExpired:return 75
    raise ValueError('IDLE_FIXED_CONTROL_OPCODE')


if __name__=='__main__':
    try:raise SystemExit(main(sys.argv[1:]))
    except Exception as error:
        # The owner sees exit code/type only. No raw default traceback/message.
        print(json.dumps(dict(PUBLIC_code='NATIVE_IDLE_CONTROL_FAILURE',exception_type=type(error).__name__)),file=sys.stderr)
        raise SystemExit(2)
