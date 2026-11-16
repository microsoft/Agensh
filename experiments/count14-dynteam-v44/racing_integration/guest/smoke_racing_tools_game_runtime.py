"""Pinned m7 scientific run INSIDE the original background agent container.

No Docker socket/key/financial owner is available here. Eight original private
ACP phase ports supply every charged model turn. All scientific logs/cases live
under this same /work RW mount and are frozen by the original whole-domain cut.
Only fixed PUBLIC control codes/counts go to stdout. Never a replacement model
dispatcher, evaluator, retry path or host-side scientific writer.
"""
from dataclasses import dataclass
from pathlib import Path,PurePosixPath
import ctypes
import hashlib
import json
import os
import random
import secrets
import stat
import subprocess
import sys
import threading
import time

from common import need,digest
from count14_public_racing_judge import PublicToolScope,PublicRunOutcome,NativePublicProbePort,Count14PublicRacingJudge
from native_racing_phase_client import NativeRacingPhaseClient
from racing_native_binding import NativeRacingLLM,Count14RacingGame,Count14RacingPrompts,RoundControl
from nloop.players import ThinkerPlayer
from nloop.prompts import fill
from nloop.runlog import RunLog
from nloop.judge import read_test_dir,list_existing,write_test_dir
from smoke_racing_tools_publication import PublicAcceptedPublication
from bounded_racing_setup import try_first_setup_completion

PROGRAM_METADATA='/work/.count14-racing/public-program.json'
RACING_SETUP=(
    'Before any brainstorming, use your original native public-task tools to read '
    '/opt/count14-approved-input/task-description.bin and inspect/extract the approved '
    '/opt/count14-approved-input/source.tar.gz into your own '
    '/work/.count14-racing/public-program/ workspace. These are the SAME approved '
    'Write /work/.count14-racing/public-program.json with the specified schema and '
    'a program field pointing to an EXISTING EXECUTABLE public wrapper under '
    '/work/.count14-racing/public-program/; do not point to an unprotected /work root file. '
    'count14 public task and source, not a reference/evaluator. Do not query or '
    'request org/main access, admin, Mattermost credentials, official outcomes or '
    'hidden data. Read the actual task with those normal tools; do not infer its '
    'contents from this integration instruction. All setup belongs to this SAME '
    'charged background stage; no additional setup model role or free call. '
    'COUNT14 RACING INTEGRATION (public tools only; not an official verdict). '
    'Use the existing public task workspace/toolchain to select one count14 task '
    'and prepare an existing executable public regression/reproduction wrapper '
    'under /work/.count14-racing/public-program/. Keep its required public '
    'workspace in that exact persistent subtree (other per-turn /work temporary '
    'files may be normally retired). Never use an official evaluator, private reference or hidden '
    'feedback. Before completing this background stage, write '+PROGRAM_METADATA+
    ' with exactly {"schema":"count14-racing-public-program-v1",'
    '"task_slot":<integer 1..14>,"program":"/work/.count14-racing/public-program/<existing executable public wrapper>"}. '
    'The file must be owned by your normal UID 10000 and not group/world writable. '
    'The wrapper uses the usual public assertion exit convention (0 pass, 1 '
    'assertion failed; other outcomes are invalid, not official verdicts). '
    'PROG in the original racing test format denotes this public wrapper. '
    'Do not invent a private oracle. Keep all original FINAL_OUTPUT formats.\n\n'
)


def _json(path,*,uid,mode=None,maximum=65536,atomic_replacement_retries=0):
    path=Path(path)
    parent_before=None;entry_before=None
    if atomic_replacement_retries:
        parent_before=path.parent.lstat()
        need(path.parent.resolve()==path.parent and stat.S_ISDIR(parent_before.st_mode) and
             parent_before.st_uid==uid and not parent_before.st_mode&0o022,
             'DYNTEAM_RACING_ATOMIC_CONTROL_PARENT')
        entry_before=path.lstat()
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_uid==uid and not a.st_mode&0o022 and
            (mode is None or stat.S_IMODE(a.st_mode)==mode) and 0<a.st_size<=maximum,
            'DYNTEAM_RACING_FIXED_CONTROL_FILE_OWNER_MODE_BOUND')
        raw=os.read(fd,maximum+1);b=os.fstat(fd);c=path.lstat()
        fields=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
        stable=len(raw)==a.st_size and fields(a)==fields(b)==fields(c) and not path.is_symlink()
        if not stable and atomic_replacement_retries:
            # The host publishes this ONE immutable control filename by replace.
            # Re-open only a proven retired FD/new regular publication race.
            # No stale snapshot is accepted and no model/phase is re-dispatched.
            d=os.fstat(fd);parent_after=path.parent.lstat()
            data=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_uid,x.st_gid,x.st_mode)
            directory=lambda x:(x.st_dev,x.st_ino,x.st_uid,x.st_gid,x.st_mode)
            need(parent_before is not None and directory(parent_before)==directory(parent_after) and
                 path.parent.resolve()==path.parent and len(raw)==a.st_size and data(a)==data(d) and
                 entry_before is not None and entry_before.st_nlink==1 and data(entry_before)==data(a) and
                 a.st_nlink in (0,1) and d.st_nlink==0 and c.st_dev==a.st_dev and c.st_ino!=a.st_ino and
                 stat.S_ISREG(c.st_mode) and c.st_nlink==1 and c.st_uid==uid and not c.st_mode&0o022 and
                 (mode is None or stat.S_IMODE(c.st_mode)==mode) and 0<c.st_size<=maximum and
                 not path.is_symlink(),'DYNTEAM_RACING_FIXED_CONTROL_FILE_STABLE')
            value=_json(path,uid=uid,mode=mode,maximum=maximum,
                        atomic_replacement_retries=atomic_replacement_retries-1)
            need(directory(parent_before)==directory(path.parent.lstat()) and
                 path.parent.resolve()==path.parent,'DYNTEAM_RACING_ATOMIC_CONTROL_PARENT')
            return value
        need(stable,'DYNTEAM_RACING_FIXED_CONTROL_FILE_STABLE')
        return json.loads(raw)
    finally:os.close(fd)


@dataclass(frozen=True)
class PublicProgram:
    task_slot:int
    path:str
    device:int
    inode:int
    uid:int
    mode:int

    def current(self):
        path=Path(self.path);s=path.lstat()
        need(path.resolve()==path and stat.S_ISREG(s.st_mode) and
             (s.st_dev,s.st_ino,s.st_uid,s.st_mode)==(self.device,self.inode,self.uid,self.mode) and
             s.st_mode&0o111,'DYNTEAM_RACING_PUBLIC_EXECUTABLE_BINDING_CHANGED')
        return self


def read_public_program(path=PROGRAM_METADATA,*,workspace='/work',uid=10000):
    workspace=Path(workspace);path=Path(path)
    need(workspace.resolve()==workspace and path.parent.resolve()==path.parent and path.is_relative_to(workspace),
         'DYNTEAM_RACING_PROGRAM_METADATA_ONLY_EXACT_WORKSPACE')
    value=_json(path,uid=uid,maximum=4096)
    need(type(value) is dict and set(value)=={'schema','task_slot','program'} and
         value['schema']=='count14-racing-public-program-v1' and type(value['task_slot']) is int and
         1<=value['task_slot']<=14 and type(value['program']) is str,
         'DYNTEAM_RACING_SCIENTIFIC_PROGRAM_METADATA_EXACT_FIELDS')
    program=Path(value['program']);s=program.lstat()
    need(program.is_absolute() and program.resolve()==program and program.is_relative_to(workspace) and
         program!=workspace and stat.S_ISREG(s.st_mode) and s.st_uid==uid and not s.st_mode&0o022 and s.st_mode&0o111,
         'DYNTEAM_RACING_EXISTING_PUBLIC_EXECUTABLE_UID_PATH_INODE')
    return PublicProgram(value['task_slot'],str(program),s.st_dev,s.st_ino,s.st_uid,s.st_mode)


class ActiveControl:
    def __init__(self,path,trajectory,contract_sha,*,owner_uid=0):
        self.path,self.t,self.sha,self.uid=Path(path),trajectory,contract_sha,owner_uid
        self.sequence=0;self.last=None;self._read_lock=threading.RLock()

    def read(self):
        with self._read_lock:
            row=_json(self.path,uid=self.uid,mode=0o444,maximum=8192,atomic_replacement_retries=3)
            fields={'schema','trajectory','contract_sha256','sequence','written_wall_ns','active_ns','observed_ns',
                    'mode','membership_cut_held','progress_ordinal','game_exec_id','game_exec_registered'}
            need(set(row)==fields and row['schema']=='count14-racing-active-control-v1' and
                 row['trajectory']==self.t and row['contract_sha256']==self.sha and
                 type(row['sequence']) is int and row['sequence']>=self.sequence and
                 all(type(row[k]) is int and row[k]>=0 for k in ('active_ns','observed_ns','written_wall_ns','progress_ordinal')) and
                 row['mode'] in ('RUNNING','HOLD','FINAL') and type(row['membership_cut_held']) is bool and
                 type(row['game_exec_registered']) is bool and type(row['game_exec_id']) is str and
                 (row['game_exec_id']=='' if not row['game_exec_registered'] else
                  len(row['game_exec_id'])==64 and all(c in '0123456789abcdef' for c in row['game_exec_id'])),
                 'DYNTEAM_RACING_ORIGINAL_ACTIVE_CONTROL_SCHEMA_AND_BINDING')
            need(0<=time.time_ns()-row['written_wall_ns']<=60_000_000_000,
                 'DYNTEAM_RACING_ORIGINAL_ACTIVE_CONTROL_FRESH60')
            self.sequence=row['sequence'];self.last=row;return row

    def now(self):
        row=self.read();return (row['active_ns']+(max(0,time.monotonic_ns()-row['observed_ns']) if row['mode']=='RUNNING' else 0))/1e9

    def admission(self):
        try:row=self.read();return row['mode']=='RUNNING' and not row['membership_cut_held']
        except Exception:return False


def guest_census(expected):
    """Real PRIVATE container cgroup root only, double PID/start census.

    Host fills expected namespace/domain identities from this exact registered
    container. No host /proc scan, cmdline, stack, body or source is inspected.
    """
    need(os.getuid()==os.getgid()==10000,'DYNTEAM_RACING_GAME_NATIVE_UID10000')
    for key in ('pid','mnt','cgroup'):
        need(Path('/proc/self/ns/'+key).stat().st_ino==expected[key+'_namespace'],
             'DYNTEAM_RACING_GAME_EXACT_NATIVE_CONTAINER_NAMESPACES')
    groups=Path('/proc/self/cgroup').read_text().splitlines()
    need(groups==['0::/'],'DYNTEAM_RACING_GAME_PRIVATE_CGROUP_NAMESPACE_REQUIRED')
    root=Path('/sys/fs/cgroup');s=root.stat()
    need((s.st_dev,s.st_ino)==(expected['domain_device'],expected['domain_inode']),
         'DYNTEAM_RACING_GAME_EXACT_CONTAINER_CGROUP_ROOT')
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        out=(ctypes.c_long*32)();lib=ctypes.CDLL(None,use_errno=True)
        need(lib.fstatfs(fd,ctypes.byref(out))==0 and out[0]==0x63677270,'DYNTEAM_RACING_GAME_REAL_CGROUP2')
    finally:os.close(fd)
    end=time.monotonic()+.5
    def scan():
        pending=[root];pids=set();dirs=[]
        while pending:
            need(time.monotonic()<end and len(dirs)<256,'DYNTEAM_RACING_GAME_FINITE_KERNEL_SCAN')
            path=pending.pop();st=path.lstat();need(path.resolve()==path and stat.S_ISDIR(st.st_mode),
                'DYNTEAM_RACING_GAME_NO_DOMAIN_ALIAS')
            dirs.append((str(path),st.st_dev,st.st_ino))
            raw=(path/'cgroup.procs').read_bytes();need(len(raw)<=65536,'DYNTEAM_RACING_GAME_PID_BOUND')
            pids.update(int(p) for p in raw.splitlines());need(len(pids)<=4096,'DYNTEAM_RACING_GAME_MEMBER_BOUND')
            pending.extend(p for p in path.iterdir() if p.is_dir() and not p.is_symlink())
        births=[]
        for pid in sorted(pids):
            need(time.monotonic()<end,'DYNTEAM_RACING_GAME_FINITE_BIRTH_SCAN')
            raw=Path('/proc',str(pid),'stat').read_bytes();births.append((pid,int(raw[raw.rfind(b')')+2:].split()[19])))
        return tuple(sorted(dirs)),tuple(births)
    a=scan();need(a==scan(),'DYNTEAM_RACING_GAME_KERNEL_CENSUS_STABLE');return a[1]


class LocalPublicExec:
    """Same native /work shell scope, no Docker/evaluator inside this runtime."""
    def __init__(self,program,scope,*,root,runner,active_now,kernel_expected):
        self.program,self.scope=program,scope.checked();self.root=Path(root);self.runner=Path(runner)
        self.now,self.expected=active_now,kernel_expected;self.lock=threading.Lock();self.jobs=[]
        self.root.mkdir(mode=0o700)

    def run_case(self,directory,deadline):
        nonce=secrets.token_hex(16)
        if self.now()>=deadline:return PublicRunOutcome(self.scope.native_scope_sha256,digest(['UNADMITTED',nonce]),self.program.task_slot,False,False,None,True)
        with self.lock: # local tool serialization only; never ledger/science lock
            if self.now()>=deadline:return PublicRunOutcome(self.scope.native_scope_sha256,digest(['UNADMITTED',nonce]),self.program.task_slot,False,False,None,True)
            self.program.current();directory=Path(directory)
            need(directory.is_absolute() and directory.resolve()==directory and directory.is_dir() and
                 directory.is_relative_to('/work/.count14-racing'),
                 'DYNTEAM_RACING_PUBLIC_CASE_SAME_WORKSPACE_NO_ALIAS')
            count=total=0
            for base,dirs,files in os.walk(directory,followlinks=False):
                for name in (*dirs,*files):
                    path=Path(base)/name;s=path.lstat();count+=1
                    need(count<=4096 and not path.is_symlink() and
                         (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)),
                         'DYNTEAM_RACING_PUBLIC_CASE_FINITE_REGULAR_TREE')
                    if stat.S_ISREG(s.st_mode):total+=s.st_size
                    need(total<=8*1024*1024,'DYNTEAM_RACING_PUBLIC_CASE_TREE_BOUND')
            case=read_test_dir(str(directory))
            need(type(case) is dict,'DYNTEAM_RACING_ORIGINAL_PUBLIC_CASE_DIR')
            before=guest_census(self.expected);job={'before':before,'child':None,'terminal':False};self.jobs.append(job)
            raw=json.dumps(dict(schema='count14-racing-public-exec-case-v1',nonce=nonce,workspace='/work',
                program=self.program.path,task_slot=self.program.task_slot,case={k:case[k] for k in ('cmd','stdin','files')})).encode()
            need(len(raw)<=8*1024*1024,'DYNTEAM_RACING_PUBLIC_CASE_BOUND')
            output=self.root/(nonce+'.private.json')
            with output.open('xb') as out:
                child=subprocess.Popen(['/opt/agentrt/bin/node',str(self.runner)],stdin=subprocess.PIPE,stdout=out,stderr=subprocess.DEVNULL)
                job['child']=child;child.communicate(raw) # accepted execution: NEVER timeout-kill/replay
            need(child.returncode==0 and 0<output.stat().st_size<=32768,'DYNTEAM_RACING_PUBLIC_EXEC_TYPED_TERMINAL')
            value=json.loads(output.read_bytes())
            fields={'schema','nonce','task_slot','native_uid10000','capabilities_zero','official_verdict',
                'command_dispatched_once','exit_code','signal','stdout_sha256','stderr_sha256','stdout_bytes',
                'stderr_bytes','shell_process_physically_exited','all_descendants_terminal_not_claimed','case_root_retained'}
            need(type(value) is dict and set(value)==fields and
                 value.get('schema')=='count14-racing-public-exec-result-v1' and value.get('nonce')==nonce and
                 value.get('task_slot')==self.program.task_slot and value.get('native_uid10000') is True and
                 value.get('capabilities_zero') is True and value.get('official_verdict') is False and
                 all(value[k] is True for k in ('command_dispatched_once','shell_process_physically_exited',
                      'all_descendants_terminal_not_claimed','case_root_retained')) and
                 all(type(value[k]) is int and value[k]>=0 for k in ('stdout_bytes','stderr_bytes')) and
                 all(type(value[k]) is str and len(value[k])==64 and all(c in '0123456789abcdef' for c in value[k])
                     for k in ('stdout_sha256','stderr_sha256')),
                 'DYNTEAM_RACING_NATIVE_PUBLIC_RESULT_NOT_OFFICIAL')
            terminal=set(guest_census(self.expected))<=set(before);job['terminal']=terminal
            valid=terminal and type(value.get('exit_code')) is int and value['exit_code'] in (0,1) and value.get('signal') is None
            fail=valid and value['exit_code']==1
            signature=None if not fail else digest(['COUNT14_PUBLIC_ASSERTION_EXIT_V1',self.program.task_slot,
                value['exit_code'],value['signal'],value['stdout_sha256'],value['stderr_sha256']])
            return PublicRunOutcome(self.scope.native_scope_sha256,digest(['NATIVE_LOCAL_PUBLIC_EXEC',nonce,value]),
                self.program.task_slot,valid,fail,signature,terminal)

    def physical_clear(self):
        for job in self.jobs:
            child=job['child']
            if child is None or child.poll() is None:return False
            if not job['terminal']:
                try:
                    if not set(guest_census(self.expected))<=set(job['before']):return False
                    job['terminal']=True
                except Exception:return False
        return True


def run_game(manifest,*,native_turn=None,public_port=None,control=None,publication=None,qualification_only=False):
    """Actual background -> selected public PROG -> original m7 Game.run chain.

    Injectable OWN ports are permitted ONLY by explicit qualification_only; the
    production entry below never reads that flag from a caller's manifest.
    """
    need(qualification_only or native_turn is public_port is control is publication is None,
         'DYNTEAM_RACING_PRODUCTION_NO_OWN_PORT_INJECTION')
    if not qualification_only:
        need(os.getuid()==os.getgid()==10000,'DYNTEAM_RACING_GAME_NO_UID_FALLBACK')
        control=ActiveControl(manifest['control_file'],manifest['trajectory'],manifest['contract_sha256'])
        native_turn=NativeRacingPhaseClient(routes=manifest['phase_routes'],native_secret_owner_uid=10000)
        guest_census(manifest['kernel_expected'])
    root=Path(manifest['run_root']);need(root.is_absolute() and root.resolve()==root,'DYNTEAM_RACING_NEW_SCIENTIFIC_GAME_ROOT')
    root.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    need(root.parent.resolve()==root.parent,'DYNTEAM_RACING_GAME_PARENT_NO_ALIAS')
    root.mkdir(mode=0o700);(root/'tests').mkdir();log=RunLog(str(root/'logs-private'))
    if not qualification_only:
        # This is the Game process's environment only. Original CLI phase HOME
        # and /tmp cleanup cannot own these scientific orchestration files.
        temporary=Path('/work/.count14-racing/game-tmp');temporary.mkdir(mode=0o700,exist_ok=True)
        need(temporary.resolve()==temporary and temporary.stat().st_uid==10000,
             'DYNTEAM_RACING_GAME_TMP_IN_EXACT_PERSISTENT_WORKSPACE')
        os.environ['TMPDIR']=str(temporary)
        home=Path('/work/.count14-racing/game-home');home.mkdir(mode=0o700,exist_ok=True)
        need(home.resolve()==home and home.stat().st_uid==10000,
             'DYNTEAM_RACING_GAME_NORMAL_UID_HOME_IN_OWN_PERSISTENT_WORKSPACE')
        os.environ['HOME']=str(home)
        import tempfile
        tempfile.tempdir=str(temporary)
        publication=PublicAcceptedPublication(round_ordinal=manifest['round_ordinal'],
            native_git=manifest['native_science_git'],
            emit_public=lambda row:print(json.dumps(row,sort_keys=True),flush=True))
    faults=[]
    llm=NativeRacingLLM(turn=native_turn,admission_open=control.admission,retain_fault=faults.append)
    prompts=Count14RacingPrompts(manifest['prompts_directory']);prompts.require_m4v()
    sysprompt,left=fill(prompts.background,dict(N='3000',BOARD_USAGE=prompts.board_full,TEST_FORMAT=prompts.test_format))
    need(not left,'DYNTEAM_RACING_ORIGINAL_BACKGROUND_PROMPT_FULLY_BOUND')
    if not qualification_only:
        parts=[{'type':'text','text':RACING_SETUP},{'type':'text','text':sysprompt},{'type':'text','text':prompts.bg_kickoff}]
    else:parts=[{'type':'text','text':sysprompt},{'type':'text','text':prompts.bg_kickoff}]
    material=llm.background(parts) # Original charged background, unchanged and retained.
    log.write_text('background.md',material)
    existing=[];existing_root=None;setup_completion_triggers=0
    if public_port is None:
        try:
            program=read_public_program(workspace='/work/.count14-racing')
        except FileNotFoundError as error:
            if error.filename == PROGRAM_METADATA:
                error._count14_setup_artifact_state = 'MISSING_AFTER_BACKGROUND'
                error._count14_background_stop_reason = llm.last_background_stop_reason
            completed = (not qualification_only and try_first_setup_completion(error,
                manifest=manifest,llm=llm,log=log,
                emit_public=lambda row:print(json.dumps(row,sort_keys=True),flush=True)))
            if not completed:raise
            setup_completion_triggers=1
            try:
                # EXACT original UID/path/inode/mode/executable guard again.
                program=read_public_program(workspace='/work/.count14-racing')
            except FileNotFoundError as final_error:
                if final_error.filename == PROGRAM_METADATA:
                    final_error._count14_setup_artifact_state = 'MISSING_AFTER_BACKGROUND'
                    final_error._count14_background_stop_reason = llm.last_background_stop_reason
                    final_error._count14_setup_completion_attempted = True
                raise
        existing_root=Path('/work/.count14-racing/public-existing-tests')/str(program.task_slot)
        existing_root.mkdir(parents=True,mode=0o700,exist_ok=True)
        need(existing_root.resolve()==existing_root,'DYNTEAM_RACING_PUBLIC_EXISTING_CASE_ROOT')
        existing=list_existing(str(existing_root))
        for item in existing:item['_dir']=str(existing_root/item['id'])
        scope=PublicToolScope(**manifest['public_tool_scope']).checked()
        execution=LocalPublicExec(program,scope,root=root/'public-exec-private',runner=manifest['runner'],
            active_now=control.now,kernel_expected=manifest['kernel_expected'])
        public_port=NativePublicProbePort(scope=scope,run_case=execution.run_case,
            existing_cases=lambda:tuple((item['id'],item['_dir']) for item in existing),physical_clear=execution.physical_clear)
    judge=Count14PublicRacingJudge(public_port,active_now=control.now)
    rng=random.Random(str(manifest['search_seed'])+':'+str(manifest['round_ordinal'])+':m7')
    order=list(range(len(prompts.seeds)));rng.shuffle(order)
    cfg=dict(method='m7',P=7,max_rounds=1000,pool_max=0,exec_workers=2,pool_existing_chars=24000,
        seeds_by_player={f'P{i}':prompts.seeds[order[i%len(order)]] for i in range(7)},
        phase_policy={'close_frac':.75,'caps':{'submit':150,'review':60,'defend':90},'lead':0.0},
        notice_dropped=prompts.notice_dropped,verdict_cap_s=60,existing_nonblocking=True)
    if qualification_only:cfg['max_rounds']=1
    game=Count14RacingGame(cfg,prompts,[ThinkerPlayer(f'P{i}',llm) for i in range(7)],llm,judge,
        RoundControl(active_now=control.now,admission_open=control.admission),log,existing,material,str(root/'tests'),
        active_now=control.now,rng=rng)
    summary=game.run()
    # All tails and this waiting process are in the same whole-freeze domain.
    # A checkpoint does NOT wait for this guest process/future to exit.
    while not game.physical_tail_done():time.sleep(.25)
    accepted=set(summary.get('accepted_in_loop',[]))
    for submission in game.subs:
        if submission.id in accepted:
            if existing_root is not None:
                write_test_dir(str(existing_root),'r'+str(manifest['round_ordinal'])+'-'+submission.id,submission.final)
            if publication is not None:publication.publish(submission.id,submission.final)
    return dict(schema='count14-racing-game-terminal-public-v1',round_ordinal=manifest['round_ordinal'],
        physical_terminal=True,method='m7',players=7,background_roles=1,
        rounds_started=summary.get('rounds_started',0),rounds_completed=summary.get('rounds_completed',0),
        public_tests_written=summary.get('n_tests_written',0),public_tests_accepted=summary.get('n_accepted_in_loop',0),
        public_tests_published=0 if publication is None else publication.in_round,
        public_tests_catalogue_total=0 if publication is None else publication.total,
        faults=len(faults),setup_completion_trigger_count=setup_completion_triggers,official_verdict=False)


def main():
    need(len(sys.argv)==2 and sys.argv[1]=='/run/count14-racing-game/manifest.json',
         'DYNTEAM_RACING_GAME_EXACT_COLD_ENTRY_MANIFEST')
    manifest=_json(sys.argv[1],uid=0,mode=0o444)
    fields={'schema','trajectory','contract_sha256','round_ordinal','search_seed','exec_id','run_root',
        'prompts_directory','runner','control_file','phase_routes','kernel_expected','public_tool_scope','code_map_sha256',
        'native_science_git'}
    need(type(manifest) is dict and set(manifest)==fields and
         manifest['schema']=='count14-racing-game-cold-manifest-v1' and
         type(manifest['exec_id']) is str and len(manifest['exec_id'])==64 and
         all(c in '0123456789abcdef' for c in manifest['exec_id']) and
         type(manifest['round_ordinal']) is int and manifest['round_ordinal']>0 and
         manifest['run_root']=='/work/.count14-racing/runs/r'+str(manifest['round_ordinal']) and
         manifest['prompts_directory']=='/opt/count14-racing-code/prompts' and
         manifest['runner']=='/opt/count14-racing-code/smoke_racing_tools_public_runner.cjs' and
         manifest['control_file']=='/run/count14-racing-control/CONTROL_PUBLIC.json',
         'DYNTEAM_RACING_GAME_COLD_MANIFEST_SCHEMA')
    from smoke_racing_tools_game_package import verify_package
    need(verify_package('/opt/count14-racing-code')==manifest['code_map_sha256'],
         'DYNTEAM_RACING_GAME_ACTUAL_CODE_MAP_PIN')
    guest_census(manifest['kernel_expected'])
    raw=Path('/proc/self/stat').read_bytes();ticks=int(raw[raw.rfind(b')')+2:].split()[19])
    print(json.dumps(dict(schema='count14-racing-game-ready-public-v1',exec_id=manifest['exec_id'],
        namespace_pid=os.getpid(),start_ticks=ticks),sort_keys=True),flush=True)
    # No phase secret/model call is opened until the HOST daemon proves this
    # exact exec -> host PID/start/ns/cgroup and publishes the original control.
    control=ActiveControl(manifest['control_file'],manifest['trajectory'],manifest['contract_sha256'])
    end=time.monotonic()+60
    while True:
        row=control.read()
        if row['game_exec_registered'] and row['game_exec_id']==manifest['exec_id']:break
        need(time.monotonic()<end,'DYNTEAM_RACING_GAME_EXACT_HOST_EXEC_ACK60_NO_MODEL')
        time.sleep(.1)
    result=run_game(manifest)
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        locations=[];tb=error.__traceback__
        while tb:
            locations.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        failure=dict(PUBLIC_code='DYNTEAM_RACING_GAME_FAILED_RETAIN_NO_REPLAY',
                     exception_type=type(error).__name__,locations=locations)
        if getattr(error, '_count14_setup_artifact_state', None) == 'MISSING_AFTER_BACKGROUND':
            reason=getattr(error, '_count14_background_stop_reason', 'UNAVAILABLE')
            allowed=('end_turn','max_tokens','max_turn_requests','refusal','cancelled','UNAVAILABLE','OTHER')
            failure.update(setup_failure_code='DYNTEAM_RACING_PUBLIC_PROGRAM_MISSING_AFTER_BACKGROUND',
                           background_stop_reason=reason if type(reason) is str and reason in allowed else 'OTHER',
                           setup_completion_attempted=getattr(error,'_count14_setup_completion_attempted',False) is True)
        print(json.dumps(failure),flush=True)
        raise SystemExit(2)
