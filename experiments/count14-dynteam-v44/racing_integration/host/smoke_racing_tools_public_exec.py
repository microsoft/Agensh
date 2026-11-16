"""Scientific-only m7 public case port in an exact original native container.

No model/evaluator client, new Docker daemon, privilege, retry, cancellation or
cleanup. The coordinator must NEVER call/read this runtime's scientific inputs
or outputs. Proposed cmd/stdin/files and public executable binding belong only
to the original scientific runtime. PUBLIC management sees typed counts only.
"""
from dataclasses import dataclass
from pathlib import Path,PurePosixPath
import hashlib
import json
import os
import secrets
import stat
import subprocess
import time
import threading

from common import need,digest
from count14_public_racing_judge import (PublicToolScope,PublicRunOutcome,NativePublicProbePort)
from native_peer_registry import process_birth
from smoke_racing_tools_kernel_custody import kernel_census

RUNNER='/opt/count14-public-probe/runner.cjs'
NODE='/opt/agentrt/bin/node'
SCHEMA='count14-racing-public-exec-case-v1'
MAX_RESULT=32768


@dataclass(frozen=True)
class PublicProgramBinding:
    """Scientific runtime's explicit PUBLIC executable, not an official oracle.

    nloop cases have no slot field. This exact binding is mandatory, never
    inferred from a scientific command/path, target source or a private result.
    """
    trajectory_id:str
    role:str
    task_slot:int
    container_id:str
    program:str
    runner_host_path:Path
    runner_sha256:str


def _case(directory):
    # This runs ONLY inside trusted scientific runtime; not metadata/front-end.
    # Original upstream case loader, same cmd/stdin/files/note interpretation.
    from nloop.judge import read_test_dir
    result=read_test_dir(str(directory))
    need(type(result) is dict and set(result)=={'cmd','stdin','files','note'} and
         all(type(result[k]) is str for k in ('cmd','stdin','note')) and result['cmd'] and
         type(result['files']) is list and all(type(x) is dict and set(x)=={'path','content'} and
         type(x['path']) is str and type(x['content']) is str for x in result['files']),
         'DYNTEAM_RACING_ORIGINAL_NATIVE_CASE_ABI')
    return {k:result[k] for k in ('cmd','stdin','files')}


def payload(binding,case,nonce):
    need(type(binding) is PublicProgramBinding and type(case) is dict and
         type(nonce) is str and len(nonce)==32,'DYNTEAM_RACING_PUBLIC_EXEC_TYPED_INPUT')
    value=dict(schema=SCHEMA,nonce=nonce,workspace='/work',program=binding.program,
               task_slot=binding.task_slot,case=case)
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
    need(len(raw)<=8*1024*1024,'DYNTEAM_RACING_PUBLIC_CASE_SIZE_BOUND')
    return raw


class NativePublicDockerExec:
    """Actual Docker exec -> UID10000 native shell -> typed m7 public outcome.

    Deadline is checked BEFORE one execution. Once dispatched, it is retained
    until natural exit; no timeout-kill and no replay. New post-exec cgroup
    births imply retained physical custody, even if a shell callback returned.
    Files/probes are retained in the original scientific workspace, not deleted.
    """
    def __init__(self,core,*,binding,scope,existing_cases,active_now):
        need(type(binding) is PublicProgramBinding and type(scope) is PublicToolScope and
             callable(existing_cases) and callable(active_now),'DYNTEAM_RACING_NATIVE_PUBLIC_EXEC_PORTS')
        scope.checked()
        need(binding.trajectory_id in core.rows and core.rows[binding.trajectory_id]['arm']=='DYNTEAM_RACING' and
             binding.role in {'tester-00','racing-background-00'} and type(binding.task_slot) is int and
             1<=binding.task_slot<=14 and binding.role in core.rows[binding.trajectory_id]['roles'],
             'DYNTEAM_RACING_EXACT_PUBLIC_TESTER_BINDING')
        program=PurePosixPath(binding.program)
        need(program.is_absolute() and program.is_relative_to('/work') and str(program)!='//work' and
             '..' not in program.parts and str(program)==binding.program,
             'DYNTEAM_RACING_PUBLIC_EXECUTABLE_ONLY_NATIVE_WORKSPACE')
        runner=Path(binding.runner_host_path)
        need(runner.is_absolute() and runner.resolve()==runner and runner.name=='smoke_racing_tools_public_runner.cjs' and
             runner.is_file() and not runner.is_symlink() and runner.stat().st_uid in (0,os.geteuid()) and
             not runner.stat().st_mode&0o022 and
             hashlib.sha256(runner.read_bytes()).hexdigest()==binding.runner_sha256,
             'DYNTEAM_RACING_FROZEN_READONLY_NATIVE_RUNNER')
        self.core,self.binding,self.scope=core,binding,scope
        self.active_now,self.existing=active_now,existing_cases
        self.jobs={};self.busy=0;self.control_lock=threading.Lock()
        self.home=Path(core.rows[binding.trajectory_id]['root'])/'racing-public-exec-private'
        self.home.mkdir(mode=0o700)
        self._scope()

    def _scope(self):
        b=self.binding;registry=self.core.native_containers
        record=registry.records.get((b.trajectory_id,b.role,'agent'))
        need(record is not None and record.cid==b.container_id,'DYNTEAM_RACING_ORIGINAL_EXACT_AGENT_RECORD')
        snapshot=registry.docker.inspect(record.cid);registry.validate(record,snapshot,running=True)
        mounts=[m for m in snapshot['mounts'] if m.get('Destination')==RUNNER]
        need(len(mounts)==1 and mounts[0].get('Type')=='bind' and mounts[0].get('RW') is False and
             mounts[0].get('Source')==str(self.binding.runner_host_path),
             'DYNTEAM_RACING_EXACT_READONLY_RUNNER_MOUNT')
        need(not any('docker.sock' in str(m.get('Destination','')) or 'evaluator-private' in str(m.get('Destination',''))
                     for m in snapshot['mounts']), 'DYNTEAM_RACING_PUBLIC_CONTAINER_NO_DOCKER_OR_EVALUATOR_MOUNT')
        need(process_birth(record.init_birth.pid)==record.init_birth,'DYNTEAM_RACING_EXACT_NATIVE_CONTAINER_BIRTH')
        return record

    def _terminal(self,job):
        record=self._scope()
        after=kernel_census(record.init_birth)
        return set(after.members)<=set(job['before'].members)

    def run_case(self,directory,deadline):
        nonce=secrets.token_hex(16)
        if self.active_now()>=deadline:
            return PublicRunOutcome(self.scope.native_scope_sha256,digest(['UNADMITTED',nonce]),
                self.binding.task_slot,False,False,None,True)
        need(not self.core.ledger.mutex._is_owned(),'DYNTEAM_RACING_PUBLIC_EXEC_WAIT_OUTSIDE_SCIENCE_LOCK')
        record=self._scope();before=kernel_census(record.init_birth)
        raw=payload(self.binding,_case(directory),nonce)
        root=self.home/nonce;root.mkdir(mode=0o700)
        output=root/'result.private.json';fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        job=dict(nonce=nonce,before=before,child=None,state='INTENT',output=output)
        with self.control_lock:self.jobs[nonce]=job;self.busy+=1
        try:
            docker=self.core.native_containers.docker
            # No --privileged, --cap-add, root user, alternate daemon or shell
            # command in argv. Only the original runtime consumes stdin body.
            argv=docker.argv('exec','--user','10000:10000','--workdir','/work','-i',record.cid,NODE,RUNNER)
            with os.fdopen(fd,'wb',closefd=False) as out:
                child=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=out,stderr=subprocess.DEVNULL,
                    cwd='/',env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
                job.update(child=child,state='DISPATCHED_RETAIN_UNTIL_NATURAL_EXIT')
                child.communicate(input=raw) # NO timeout/signal/replay; same retained child
                out.flush();os.fsync(fd)
            job['exit_code']=child.returncode
            need(child.returncode==0 and 0<output.stat().st_size<=MAX_RESULT,
                 'DYNTEAM_RACING_PUBLIC_EXEC_ACTUAL_TERMINAL_RESULT_BOUND')
            value=json.loads(output.read_bytes())
            expected={'schema','nonce','task_slot','native_uid10000','capabilities_zero','official_verdict',
                'command_dispatched_once','exit_code','signal','stdout_sha256','stderr_sha256','stdout_bytes',
                'stderr_bytes','shell_process_physically_exited','all_descendants_terminal_not_claimed','case_root_retained'}
            need(set(value)==expected and value['schema']=='count14-racing-public-exec-result-v1' and
                 value['nonce']==nonce and value['task_slot']==self.binding.task_slot and
                 all(value[k] is True for k in ('native_uid10000','capabilities_zero','command_dispatched_once',
                     'shell_process_physically_exited','all_descendants_terminal_not_claimed','case_root_retained')) and
                 value['official_verdict'] is False and
                 (type(value['exit_code']) is int or value['exit_code'] is None) and
                 (type(value['signal']) is str or value['signal'] is None) and
                 all(type(value[k]) is str and len(value[k])==64 and all(c in '0123456789abcdef' for c in value[k])
                     for k in ('stdout_sha256','stderr_sha256')),
                 'DYNTEAM_RACING_TYPED_PRIVATE_NATIVE_SHELL_RESULT')
            physical=self._terminal(job);job['state']='PHYSICAL_TERMINAL' if physical else 'BACKGROUND_RETAINED_NO_REPLAY'
            # Public proposed shell assertions convention: 0 pass / 1 fail.
            # Other codes/signals are execution-invalid, never a hidden verdict.
            valid=value['exit_code'] in (0,1) and value['signal'] is None
            failure=valid and value['exit_code']==1
            signature=None if not failure else digest(['COUNT14_PUBLIC_ASSERTION_EXIT_V1',self.binding.task_slot,
                value['exit_code'],value['signal'],value['stdout_sha256'],value['stderr_sha256']])
            receipt=digest(dict(schema='count14-original-native-public-shell-exec-receipt-v1',nonce=nonce,
                native_scope_sha256=self.scope.native_scope_sha256,container_id=record.cid,init_birth=record.init_birth.__dict__,
                runner_sha256=self.binding.runner_sha256,result=value,physical_terminal=physical))
            return PublicRunOutcome(self.scope.native_scope_sha256,receipt,self.binding.task_slot,
                physical and valid,failure if physical else False,signature if physical else None,physical)
        except Exception:
            job['state']='FAILED_RETAINED_NO_REPLAY'
            return PublicRunOutcome(self.scope.native_scope_sha256,digest(['FAILED_RETAINED',nonce]),
                self.binding.task_slot,False,False,None,False)
        finally:
            os.close(fd)
            with self.control_lock:self.busy-=1

    def physical_clear(self):
        with self.control_lock:
            if self.busy:return False
            jobs=tuple(self.jobs.values())
        for job in jobs:
            if job['state']=='PHYSICAL_TERMINAL':continue
            child=job.get('child')
            if child is None or child.poll() is None:return False
            try:
                if not self._terminal(job):return False
            except Exception:return False
        return True

    def port(self):
        return NativePublicProbePort(scope=self.scope,run_case=self.run_case,
            existing_cases=self.existing,physical_clear=self.physical_clear)
