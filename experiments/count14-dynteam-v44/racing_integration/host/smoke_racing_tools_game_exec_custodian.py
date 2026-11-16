#!/usr/bin/python3
"""Finite own-control cold entry retaining one exact native Game Docker exec.

Only this fixed own exec's metadata/API is read. No general inspect/log/command
projection, model client, signal, cancellation, retry, root exec or new daemon.
Once start is attempted its exec ID is retained even after observation failure.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH1 = _count14_os.environ.get('COUNT14_SCRATCH1_ROOT', '/srv/count14/scratch1')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
import hashlib,http.client,json,os,pathlib,socket,stat,sys,time


def need(ok,code):
    if not ok:raise RuntimeError(code)


def read(path):
    p=pathlib.Path(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_uid==0 and not s.st_mode&0o022 and
            s.st_size<=65536,'DYNTEAM_RACING_EXEC_FIXED_CONTROL_FILE')
        data=os.read(fd,65537);need(len(data)==s.st_size,'DYNTEAM_RACING_EXEC_CONTROL_BOUND');return json.loads(data)
    finally:os.close(fd)


def append(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o444)
    try:os.write(fd,(json.dumps(value,sort_keys=True)+'\n').encode());os.fsync(fd)
    finally:os.close(fd)


class Unix(http.client.HTTPConnection):
    def __init__(self,path):super().__init__('localhost',timeout=2.5);self.path=pathlib.Path(path)
    def connect(self):
        fd=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(2.5)
            self.sock.connect('/proc/self/fd/'+str(fd)+'/'+self.path.name)
        finally:os.close(fd)


def inspect_own_exec(socket_path,exec_id):
    c=Unix(socket_path)
    try:
        need(type(exec_id) is str and len(exec_id)==64 and all(x in '0123456789abcdef' for x in exec_id),
             'DYNTEAM_RACING_OWN_EXEC_FIXED_ID')
        c.request('GET','/exec/'+exec_id+'/json');r=c.getresponse()
        need(r.status==200,'DYNTEAM_RACING_OWN_EXEC_INSPECT_STATUS_NO_ERROR_BODY')
        raw=r.read(65537)
        need(len(raw)<=65536,'DYNTEAM_RACING_OWN_EXEC_PUBLIC_INSPECT_BOUND')
        value=json.loads(raw)
        # The exec was CREATED by this frozen entry with fixed own argv; its
        # schema has no scientific request/response/log body. Output only these.
        result={'id':value['ID'],'container_id':value['ContainerID'],'running':value['Running'],
                'pid':value['Pid'],'exit_code':value['ExitCode']}
        need(result['id']==exec_id and type(result['container_id']) is str and len(result['container_id'])==64 and
             all(c in '0123456789abcdef' for c in result['container_id']) and type(result['running']) is bool and
             type(result['pid']) is int and result['pid']>=0 and
             (type(result['exit_code']) is int or
              result['exit_code'] is None and (result['running'] or result['pid']==0)),
             'DYNTEAM_RACING_OWN_EXEC_TYPED_PUBLIC_INSPECT')
        return result
    finally:c.close()


def exec_process_identity(pid):
    """Only exact owned exec PID/start/boot plus kernel state, no argv/env."""
    need(type(pid) is int and pid>0,'DYNTEAM_RACING_EXEC_POSITIVE_KERNEL_PID')
    raw=pathlib.Path('/proc',str(pid),'stat').read_bytes();at=raw.rfind(b')')
    need(at>=0,'DYNTEAM_RACING_EXEC_KERNEL_STAT_BOUND')
    fields=raw[at+2:].split()
    return ({'pid':pid,'start_ticks':int(fields[19]),
             'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()},fields[0].decode('ascii'))


def prove_exec_kernel_terminal(terminal,birth):
    """A daemon may retain Pid after exit; never invent Pid0 or exit0.

    Attached stream EOF + exact exec/CID API terminal + recorded PID birth no
    longer live are all required. A reused PID is not the original execution.
    Caller still records the real exit status, including nonzero failures.
    """
    need(terminal['running'] is False and type(terminal['exit_code']) is int and
         terminal['pid'] in (0,birth['pid']),
         'DYNTEAM_RACING_EXEC_ACTUAL_DAEMON_PHYSICAL_TERMINAL_REQUIRED')
    try:current,state=exec_process_identity(birth['pid'])
    except FileNotFoundError:return
    need(current!=birth or state in ('Z','X'),
         'DYNTEAM_RACING_EXEC_ORIGINAL_BIRTH_STILL_LIVE_REFUSE_TERMINAL')


def await_owned_exec_birth(socket_path,eid,cid,root,nonce):
    while True:
        running=inspect_own_exec(socket_path,eid)
        need(running['container_id']==cid,'DYNTEAM_RACING_EXEC_STARTED_EXACT_CONTAINER')
        if running['running'] and running['pid']>0:
            try:birth,state=exec_process_identity(running['pid'])
            except FileNotFoundError:pass # same exec only; observe its real terminal next
            else:
                if state not in ('Z','X'):
                    append(root/'EXEC_BIRTH_PUBLIC.jsonl',dict(kind='EXEC_BIRTH',exec_id=eid,container_id=cid,birth=birth))
                    break
        if not running['running'] and type(running['exit_code']) is int:
            append(root/'EXEC_EARLY_TERMINAL_PUBLIC.jsonl',dict(kind='EXEC_ENDED_BEFORE_PROVEN_BIRTH',nonce=nonce,**running))
            need(False,'DYNTEAM_RACING_EXEC_ENDED_BEFORE_PROVEN_BIRTH_RETAIN_REAL_EXIT')
        time.sleep(.02)
    return birth


def await_owned_exec_terminal(socket_path,eid,cid):
    while True:
        terminal=inspect_own_exec(socket_path,eid)
        need(terminal['container_id']==cid,'DYNTEAM_RACING_EXEC_TERMINAL_EXACT_CONTAINER')
        if terminal['running'] is False and type(terminal['exit_code']) is int:break
        time.sleep(.02)
    return terminal


def public_game_record(value):
    """Strict allowlist; never forward a message/locals/body or arbitrary key."""
    need(type(value) is dict,'DYNTEAM_RACING_EXEC_PUBLIC_RECORD_DICT')
    schema=value.get('schema')
    if schema=='count14-racing-game-ready-public-v1':
        need(set(value)=={'schema','exec_id','namespace_pid','start_ticks'} and
             type(value['exec_id']) is str and len(value['exec_id'])==64 and
             all(c in '0123456789abcdef' for c in value['exec_id']) and
             all(type(value[k]) is int and value[k]>0 for k in ('namespace_pid','start_ticks')),
             'DYNTEAM_RACING_EXEC_STRICT_READY_PUBLIC')
    elif schema=='count14-racing-game-terminal-public-v1':
        counts={'round_ordinal','rounds_started','rounds_completed','public_tests_written','public_tests_accepted',
                'public_tests_published','public_tests_catalogue_total','faults','setup_completion_trigger_count'}
        need(set(value)=={'schema','physical_terminal','method','players','background_roles','official_verdict'}|counts and
             value['physical_terminal'] is True and value['method']=='m7' and value['players']==7 and
             value['background_roles']==1 and value['official_verdict'] is False and
             type(value['setup_completion_trigger_count']) is int and value['setup_completion_trigger_count'] in (0,1) and
             (value['setup_completion_trigger_count']==0 or value['round_ordinal']==1) and
             all(type(value[k]) is int and value[k]>=0 for k in counts),
             'DYNTEAM_RACING_EXEC_STRICT_TERMINAL_COUNTS_PUBLIC')
    elif schema=='count14-racing-setup-completion-public-v1':
        need(set(value)=={'schema','round_ordinal','trigger_count','policy','stage',
             'first_background_normal_end_turn','original_receipts_physical_terminal','all_calls_charged_SEARCH'} and
             type(value['round_ordinal']) is type(value['trigger_count']) is int and
             value['round_ordinal']==value['trigger_count']==1 and
             value['policy']=='AT_MOST_ONCE_FIRST_BACKGROUND_NORMAL_ENDTURN_EXACT_METADATA_MISSING' and
             value['stage']=='INTENT_BEFORE_SAME_SID_PROMPT_NO_REPLAY' and
             all(value[k] is True for k in ('first_background_normal_end_turn',
                 'original_receipts_physical_terminal','all_calls_charged_SEARCH')),
             'RACING_SETUP_COMPLETION_STRICT_ANONYMOUS_ONCE_INTENT_ONLY')
    elif schema=='count14-racing-public-test-published-v1':
        counts={'round_ordinal','publication_ordinal','public_tests_in_round'}
        need(set(value)=={'schema','public_test_path','normal_science_git_push','official_verdict'}|counts and
             value['public_test_path']=='/opt/count14-racing-public-tests' and
             value['normal_science_git_push'] is True and value['official_verdict'] is False and
             all(type(value[k]) is int and value[k]>0 for k in counts),
             'DYNTEAM_RACING_EXEC_STRICT_NORMAL_GIT_PUBLICATION_COUNTS_ONLY')
    else:
        base={'PUBLIC_code','exception_type','locations'}
        extra={'setup_failure_code','background_stop_reason','setup_completion_attempted'}
        need(set(value) in (base,base|extra) and
             value['PUBLIC_code']=='DYNTEAM_RACING_GAME_FAILED_RETAIN_NO_REPLAY' and
             type(value['exception_type']) is str and value['exception_type'].isidentifier() and
             type(value['locations']) is list and len(value['locations'])<=64,
             'DYNTEAM_RACING_EXEC_STRICT_FAILURE_PUBLIC')
        if set(value)==base|extra:
            need(value['setup_failure_code']=='DYNTEAM_RACING_PUBLIC_PROGRAM_MISSING_AFTER_BACKGROUND' and
                 value['background_stop_reason'] in ('end_turn','max_tokens','max_turn_requests',
                    'refusal','cancelled','UNAVAILABLE','OTHER') and
                 type(value['setup_completion_attempted']) is bool,
                 'RACING_SETUP_COMPLETION_STRICT_FIXED_FAILURE_ENUM_NO_BODY')
        for row in value['locations']:
            need(type(row) is dict and set(row)=={'file','line','function'} and type(row['file']) is str and
                 0<len(row['file'])<=4096 and not any(c in row['file'] for c in '\n\r\0') and
                 type(row['line']) is int and row['line']>0 and type(row['function']) is str and
                 len(row['function'])<=256 and not any(c in row['function'] for c in '\n\r\0'),
                 'DYNTEAM_RACING_EXEC_ONLY_EXCEPTION_PUBLIC_LOCATIONS')
    return value


def main():
    need(os.geteuid()==0 and len(sys.argv)==2,'DYNTEAM_RACING_EXEC_OWN_ROOT_ENTRY')
    plan=read(sys.argv[1]);root=pathlib.Path(plan['job_root'])
    need(set(plan)=={'schema','job_root','nonce','container_id','docker_socket'} and
        plan['schema']=='count14-own-racing-exec-custodian-plan-v1',
        'DYNTEAM_RACING_EXEC_FIXED_OWN_CONTROL_PLAN')
    need(root.resolve()==root and root.is_dir() and
        (root.is_relative_to((_C14_SCRATCH)) or root.is_relative_to((_C14_SCRATCH1))),
        'DYNTEAM_RACING_EXEC_ONLY_NEW_SCRATCH_CONTROL_ROOT')
    socket_path=plan['docker_socket'];p=pathlib.Path(socket_path)
    need(p.resolve()==p and stat.S_ISSOCK(p.stat().st_mode) and
        (p.is_relative_to((_C14_SCRATCH)) or p.is_relative_to((_C14_SCRATCH1))),
        'DYNTEAM_RACING_EXEC_ORIGINAL_PRIVATE_SOCKET_ONLY')
    cid=plan['container_id'];nonce=plan['nonce']
    need(len(cid)==64 and all(c in '0123456789abcdef' for c in cid) and len(nonce)==32,
        'DYNTEAM_RACING_EXEC_FULL_CID_AND_NONCE')
    body={'AttachStdin':False,'AttachStdout':True,'AttachStderr':False,'Tty':False,
        'Cmd':['/usr/bin/python3','-I','-B','/opt/count14-racing-code/smoke_racing_tools_game_entry.py',
               '/run/count14-racing-game/manifest.json'],
        'User':'10000:10000','Privileged':False,'WorkingDir':'/work'}
    append(root/'CONTROL_PUBLIC.jsonl',{'kind':'CREATE_INTENT','nonce':nonce,'cid':cid,'argv_sha256':hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()})
    c=Unix(socket_path)
    try:
        c.request('POST','/containers/'+cid+'/exec',json.dumps(body),{'Content-Type':'application/json'})
        r=c.getresponse();need(r.status==201,'DYNTEAM_RACING_EXEC_CREATE_STATUS_NO_ERROR_BODY_NO_RETRY')
        raw=r.read(4097);need(len(raw)<=4096,'DYNTEAM_RACING_EXEC_CREATE_UNPROVEN_NO_RETRY')
        value=json.loads(raw);eid=value['Id'];need(len(eid)==64 and all(x in '0123456789abcdef' for x in eid),'DYNTEAM_RACING_OWN_EXEC_ID')
    finally:c.close()
    append(root/'EXEC_CREATED_PUBLIC.jsonl',{'kind':'EXEC_CREATED','exec_id':eid,'nonce':nonce,'container_id':cid})
    end=time.monotonic()+60
    while True:
        start=root/'START_PUBLIC.json'
        if start.exists():
            v=read(start);need(v=={'exec_id':eid,'nonce':nonce,'start_once':True},'DYNTEAM_RACING_EXEC_EXACT_SINGLE_START_TICKET');break
        need(time.monotonic()<end,'DYNTEAM_RACING_EXEC_PRESTART_TICKET60_RETAIN_ID');time.sleep(.1)
    append(root/'CONTROL_PUBLIC.jsonl',{'kind':'START_INTENT','exec_id':eid,'nonce':nonce})
    c=Unix(socket_path)
    try:
        c.request('POST','/exec/'+eid+'/start',json.dumps({'Detach':False,'Tty':False}),{'Content-Type':'application/json'})
        c.sock.settimeout(None) # accepted own Game process: never timeout-cancel
        r=c.getresponse();need(r.status==200,'DYNTEAM_RACING_EXEC_START_UNPROVEN_RETAIN_NO_REPLAY')
        birth=await_owned_exec_birth(socket_path,eid,cid,root,nonce)
        pending=b''
        while True:
            header=r.read(8)
            if not header:break
            need(len(header)==8 and header[0]==1 and header[1:4]==b'\0\0\0',
                 'DYNTEAM_RACING_EXEC_ONLY_STDOUT_NO_STDERR_BODY')
            size=int.from_bytes(header[4:8],'big');need(size<=1024*1024,'DYNTEAM_RACING_EXEC_PUBLIC_FRAME_BOUND')
            block=r.read(size);need(len(block)==size,'DYNTEAM_RACING_EXEC_STREAM_UNPROVEN_RETAIN')
            pending+=block;need(len(pending)<=131072,'DYNTEAM_RACING_EXEC_PUBLIC_LINE_BOUND')
            lines=pending.split(b'\n');pending=lines.pop()
            for line in lines:
                if not line:continue
                value=public_game_record(json.loads(line))
                append(root/'GAME_STREAM_PUBLIC.jsonl',value)
        need(not pending,'DYNTEAM_RACING_EXEC_NO_PARTIAL_PUBLIC_RECORD')
    finally:c.close() # stream detachment is NOT a guest/process/model signal
    terminal=await_owned_exec_terminal(socket_path,eid,cid)
    need(terminal['id']==eid and terminal['container_id']==cid,
         'DYNTEAM_RACING_EXEC_ACTUAL_TERMINAL_EXACT_ID_AND_CONTAINER')
    prove_exec_kernel_terminal(terminal,birth)
    append(root/'EXEC_TERMINAL_PUBLIC.jsonl',dict(kind='EXEC_TERMINAL',nonce=nonce,**terminal))


if __name__=='__main__':
    try:main()
    except Exception as error:
        locations=[];tb=error.__traceback__
        while tb:locations.append({'file':tb.tb_frame.f_code.co_filename,'line':tb.tb_lineno,'function':tb.tb_frame.f_code.co_name});tb=tb.tb_next
        # No message, API error body, locals, command or scientific output.
        print(json.dumps({'PUBLIC_code':'DYNTEAM_RACING_EXEC_CUSTODIAN_FAILED_RETAIN_NO_REPLAY',
            'exception_type':type(error).__name__,'locations':locations}),flush=True)
        raise SystemExit(2)
