"""SAME-core RACING helper UP + exact guest Game exec custody, cold only.

The host never runs Game or writes scientific cases. Guest orchestration is an
exact registered control process in the original background agent cgroup; the
original whole-domain cut freezes it, so no host-future drain gate is added.
"""
from pathlib import Path
from types import SimpleNamespace
import concurrent.futures as cf
import dataclasses
import json
import os
import secrets
import shlex
import subprocess
import sys
import time

from common import need,digest
from native_beta_layout import native_aliases
from native_peer_registry import ProcessBirth,process_birth
from native_writer_fence import process_cgroup_v2
from racing_native_binding import BottleneckSchedule
from smoke_racing_tools_kernel_custody import kernel_census
from smoke_racing_tools_game_exec_custodian import inspect_own_exec,public_game_record
from smoke_racing_tools_game_package import verify_package

ROLE='racing-background-00'
HELPERS=(ROLE,*(f'racing-player-{i:02d}' for i in range(7)))


def _publish(path,value,mode=0o444):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb',closefd=False) as out:out.write((json.dumps(value,sort_keys=True)+'\n').encode());out.flush();os.fsync(fd)
    finally:os.close(fd)


def _last_public(path):
    if not path.exists():return None
    need(path.stat().st_size<=262144 and not path.is_symlink(),'DYNTEAM_RACING_PUBLIC_CONTROL_BOUND')
    lines=path.read_bytes().splitlines();return None if not lines else json.loads(lines[-1])


@dataclasses.dataclass(frozen=True)
class GameExecControl:
    trajectory:str
    role:str
    exec_id:str
    container_id:str
    process:ProcessBirth
    domain:str
    code_map_sha256:str


def registered_game_controls(core,t,role):
    """Only exact daemon-proven orchestration PIDs, NEVER arbitrary descendants."""
    value=getattr(core,'native_racing_game_exec_controls',{}).get((t,role))
    if value is None:return set()
    need(type(value) is GameExecControl and value.trajectory==t and value.role==role and
         role==ROLE and core.rows[t]['arm']=='DYNTEAM_RACING',
         'DYNTEAM_RACING_TYPED_ORIGINAL_GAME_EXEC_CONTROL')
    try:alive=process_birth(value.process.pid)==value.process
    except FileNotFoundError:alive=False
    if not alive:return set()
    record=core.native_containers.records[t,role,'agent']
    manager=core.native_racing_game_managers[t]
    need(value.container_id==record.cid and value.code_map_sha256==manager.code_sha and
         value.process.uid==value.process.gid==10000 and
         (value.process.pid_namespace,value.process.mount_namespace,value.process.network_namespace)==
         (record.init_birth.pid_namespace,record.init_birth.mount_namespace,record.init_birth.network_namespace),
         'DYNTEAM_RACING_REGISTERED_GAME_EXACT_CURRENT_CID_CODE_UID_NAMESPACES')
    need(str(process_cgroup_v2({'pid':value.process.pid,'start_ticks':value.process.start_ticks,'boot_id':value.process.boot_id}))==value.domain,
         'DYNTEAM_RACING_GAME_EXEC_DOMAIN_CHANGED')
    return {value.process}


class NativeRacingGameManager:
    def __init__(self,core,trajectory,*,code_directory,code_map_sha256,custodian_path,custodian_sha256,
                 public_tool_scope):
        need(core.rows[trajectory]['arm']=='DYNTEAM_RACING' and trajectory in core.gate.startup_held and
             hasattr(core,'cold_native_exports') and hasattr(core,'cohort_resources'),
             'DYNTEAM_RACING_COLD_SAME_CORE_ONLY')
        self.core,self.t=core,trajectory;self.row=core.rows[trajectory];self.sha=digest(core.contract)
        self.host=core.native_host_environment['trajectories'][trajectory]
        self.export=core.cold_native_exports['trajectories'][trajectory]
        self.code=Path(code_directory);self.code_sha=code_map_sha256
        self.custodian=Path(custodian_path);self.custodian_sha=custodian_sha256
        import hashlib
        need(self.code.is_absolute() and self.code.resolve()==self.code and self.code.is_dir() and
             self.custodian.resolve()==self.custodian and not self.custodian.is_symlink() and
             hashlib.sha256(self.custodian.read_bytes()).hexdigest()==custodian_sha256,
             'DYNTEAM_RACING_FROZEN_OWN_GAME_EXEC_CODE')
        need(verify_package(self.code)==self.code_sha,'DYNTEAM_RACING_COMPLETE_FROZEN_GUEST_CODE_MAP')
        self.scope=public_tool_scope.checked();self.aliases=native_aliases('DYNTEAM_RACING')
        self.root=Path(self.row['root'])/'native-racing-manager';self.root.mkdir(mode=0o700)
        self.game_export=Path(self.row['root'])/'native-racing-game-export';self.game_export.mkdir(mode=0o755)
        self.control_export=Path(self.row['root'])/'native-racing-game-control';self.control_export.mkdir(mode=0o755)
        self.game_export.chmod(0o755);self.control_export.chmod(0o755)
        self.helpers={};self.helper_index=0;self.pool=cf.ThreadPoolExecutor(max_workers=1,thread_name_prefix='own-native-helper-zero')
        self.schedule=BottleneckSchedule();self.games=[];self.accepted_public=0;self.control_sequence=0;self.last_control=0
        self.published_public=0;self.publication_receipts=[];self.setup_completion_triggers=0
        self.state='COLD_OVERLAY_READY_HELPERS_NOT_UP';self.failure=None;self._install_overlay()
        if not hasattr(core,'native_racing_game_managers'):core.native_racing_game_managers={}
        need(trajectory not in core.native_racing_game_managers,'DYNTEAM_SOLE_RACING_GAME_MANAGER')
        core.native_racing_game_managers[trajectory]=self

    def _install_overlay(self):
        need(self.t in self.core.gate.startup_held,'DYNTEAM_RACING_OVERLAY_BEFORE_SCIENTIFIC_ACTIVATION')
        phases=[]
        for role in HELPERS:
            route=self.export['phase_routes'][role]
            source=str(Path(route['socket']).parent)
            phases.append(source+':/run/count14-racing-phases/'+role+':ro')
        value={'services':{self.aliases[ROLE]['agent_service']:{'volumes':[
            str(self.code)+':/opt/count14-racing-code:ro',
            str(self.game_export)+':/run/count14-racing-game:ro',
            str(self.control_export)+':/run/count14-racing-control:ro',*phases]}}}
        path=self.root/'compose.racing-game-cold.json';_publish(path,value,0o400)
        if 'native_bridge_user_layer' in self.host:
            from native_bridge_user_cold import append_existing_cold_overlay
            append_existing_cold_overlay(self.core,self.t,path)
        else:
            command=list(self.host['compose']);at=command.index('--project-name');command[at:at]=['-f',str(path)]
            self.host['compose']=tuple(command)
            self.host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND']=shlex.join(command)
        self.overlay_path=path

    def _start_helper(self,role):
        key=self.t,role;resources=self.core.cohort_resources;resources.maybe_refresh()
        if not resources.reserve_native_launch(key):return False
        lease=self.core.membership_fences[self.t].acquire(role,'BIRTH')
        if lease is None:resources.defer_unadmitted_launch(key);return False
        effect=dict(lease=lease,birth_observed=False,committed=False)
        self.core.pending_native_launches[key]=effect
        record=dict(role=role,effect=effect,state='UP_INTENT',child=None,zero_future=None)
        self.helpers[role]=record
        services=' '.join(self.aliases[role][k] for k in ('agent_service','router_service'))
        env=dict(PATH='/usr/bin:/bin',LANG='C.UTF-8',HOME=str(self.root),**self.host['launcher_env'],
            SPAWN_SOURCE=self.host['spawn_source'],PROFILE=self.host['profile'],SERVICES=services)
        script='source "$SPAWN_SOURCE"; make up-slot PROFILE="$PROFILE" UP_FLAGS="--no-build --pull never" SERVICES="$SERVICES"'
        child=subprocess.Popen(['/bin/bash','-c',script],cwd=self.host['project_root'],env=env,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        record.update(child=child,state='UP_RUNNING');return True

    def _helper_step(self,role):
        r=self.helpers[role]
        if r['state']=='UP_RUNNING':
            code=r['child'].poll()
            if code is None:return False
            need(code==0,'DYNTEAM_RACING_ORIGINAL_HELPER_UP_FAILED_RETAIN_NO_RETRY')
            r['state']='UP_RETURNED'
        if r['state']=='UP_RETURNED':
            discovery=self.core.native_containers.sync_boot_plans(self.t,[role])
            if discovery['pending_components']:return False
            route=self.export['phase_routes'][role]
            if not Path(route['socket']).is_socket():return False
            r['zero_future']=self.pool.submit(self.export['phase_client'].prepare_zero_model,role)
            r['state']='ORIGINAL_ZERO_MODEL_PREPARE_RUNNING'
        if r['state']=='ORIGINAL_ZERO_MODEL_PREPARE_RUNNING':
            if not r['zero_future'].done():return False
            result=r['zero_future'].result();effect=r['effect'];key=self.t,role
            need(result=={'ZERO_MODEL_NATIVE_SESSION_PREPARED':True,'model_prompt_sent':False} and
                 effect['birth_observed'] is True and key not in self.core.roles.held,
                 'DYNTEAM_RACING_HELPER_ACTUAL_NATIVE_CLI_AND_SESSION_PREPARED')
            with self.core.ledger.mutex:
                need(self.core.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=?',key).fetchone()[0]==0,
                     'DYNTEAM_RACING_HELPER_ZERO_MODEL_PROOF')
            proof=digest(['NATIVE_RACING_HELPER_PREPARED',self.t,role,effect['native_cli_token_sha256'],result])
            self.core.membership_fences[self.t].finish(effect['lease'],original_control_receipt_sha256=proof)
            effect['committed']=True;del self.core.pending_native_launches[key]
            self.core.cohort_resources.finish_native_launch(key);r['state']='PREPARED_ZERO_MODELS'
        return r['state']=='PREPARED_ZERO_MODELS'

    def _progress(self):
        # Original accepted-CLAIM-driven native spawn commitment ordinal plus
        # prior original m7 public accepted tests, never a private result/body.
        return self.core.spawn_owner.next[self.t]-1+self.accepted_public

    def _control(self,*,force=False):
        now=time.monotonic()
        if not force and now-self.last_control<.5:return
        row=self.core.active_clock.read(self.t);self.control_sequence+=1
        current=next((g for g in reversed(self.games) if g.get('registered') and not g.get('terminal')),None)
        value=dict(schema='count14-racing-active-control-v1',trajectory=self.t,contract_sha256=self.sha,
            sequence=self.control_sequence,written_wall_ns=time.time_ns(),active_ns=row['active_ns'],
            observed_ns=row['observed_ns'],mode=row['mode'],membership_cut_held=self.core.membership_fences[self.t].public_counts()['cut_held'],
            progress_ordinal=self._progress(),game_exec_id='' if current is None else current['exec_id'],
            game_exec_registered=current is not None)
        tmp=self.control_export/('.control-'+secrets.token_hex(8));_publish(tmp,value)
        os.replace(tmp,self.control_export/'CONTROL_PUBLIC.json');self.last_control=now

    def _new_game(self,ordinal):
        record=self.core.native_containers.records[self.t,ROLE,'agent'];snapshot=self.core.native_containers.docker.inspect(record.cid)
        self.core.native_containers.validate(record,snapshot,running=True)
        census=kernel_census(record.init_birth)
        expected=dict(pid_namespace=record.init_birth.pid_namespace,mnt_namespace=record.init_birth.mount_namespace,
            cgroup_namespace=Path('/proc',str(record.init_birth.pid),'ns/cgroup').stat().st_ino,
            domain_device=census.domain_device,domain_inode=census.domain_inode)
        nonce=secrets.token_hex(16);root=self.root/('game-'+str(ordinal));root.mkdir(mode=0o700)
        plan=dict(schema='count14-own-racing-exec-custodian-plan-v1',job_root=str(root),nonce=nonce,
            container_id=record.cid,docker_socket=str(self.core.native_containers.docker.route.socket_path))
        _publish(root/'PLAN_PRIVATE.json',plan,0o400)
        game=dict(ordinal=ordinal,nonce=nonce,root=root,container=record,kernel_expected=expected,
            child=None,exec_id=None,registered=False,terminal=False,state='CUSTODIAN_START_INTENT',
            public_cursor=0,publications=0,setup_completion_triggers=0)
        self.games.append(game)
        # Custodian stdout is strict own PUBLIC diagnostics only; guest
        # scientific/model bodies never pass public_game_record. Retain the
        # original failure instead of discarding it into DEVNULL.
        with (root/'CUSTODIAN_DIAGNOSTICS_PUBLIC.jsonl').open('xb') as out, (root/'CUSTODIAN_INFRA.stderr').open('xb') as err:
            game['child']=subprocess.Popen([sys.executable,'-I','-B',str(self.custodian),str(root/'PLAN_PRIVATE.json')],
                stdin=subprocess.DEVNULL,stdout=out,stderr=err)
        game['state']='EXEC_CREATE_RUNNING'

    def _game_step(self,g):
        created=_last_public(g['root']/'EXEC_CREATED_PUBLIC.jsonl')
        if g['exec_id'] is None and created is not None:
            need(created['nonce']==g['nonce'] and created['container_id']==g['container'].cid,
                 'DYNTEAM_RACING_EXACT_OWN_EXEC_CREATE_RECEIPT')
            g['exec_id']=created['exec_id']
            manifest=dict(schema='count14-racing-game-cold-manifest-v1',trajectory=self.t,contract_sha256=self.sha,
                round_ordinal=g['ordinal'],search_seed=self.row['search_seed'],exec_id=g['exec_id'],
                code_map_sha256=self.code_sha,
                run_root='/work/.count14-racing/runs/r'+str(g['ordinal']),
                prompts_directory='/opt/count14-racing-code/prompts',runner='/opt/count14-racing-code/smoke_racing_tools_public_runner.cjs',
                control_file='/run/count14-racing-control/CONTROL_PUBLIC.json',
                native_science_git=dict(host='http://gitea:3000',
                    account=self.core.native_layout.current(self.t)['org']+'-'+self.aliases[ROLE]['native_short'],
                    credential_file='/opt/data/home/.git-credentials'),
                phase_routes={r:{'socket':'/run/count14-racing-phases/'+r+'/scientific.sock',
                    'secret':'/run/count14-racing-phases/'+r+'/phase.secret'} for r in HELPERS},
                kernel_expected=g['kernel_expected'],public_tool_scope=dataclasses.asdict(self.scope))
            path=self.game_export/'manifest.json'
            if path.exists():
                # Preserve the old manifest, never overwrite a history record.
                path.rename(self.game_export/('manifest-before-r'+str(g['ordinal'])+'.json'))
            _publish(path,manifest)
            _publish(g['root']/'START_PUBLIC.json',{'exec_id':g['exec_id'],'nonce':g['nonce'],'start_once':True})
            g['state']='EXEC_START_ATTEMPTED_RETAIN_ID'
        stream=_last_public(g['root']/'GAME_STREAM_PUBLIC.jsonl')
        if not g['registered'] and stream and stream.get('schema')=='count14-racing-game-ready-public-v1':
            need(stream['exec_id']==g['exec_id'],'DYNTEAM_RACING_GUEST_READY_EXACT_CREATED_EXEC_ID')
            info=inspect_own_exec(str(self.core.native_containers.docker.route.socket_path),g['exec_id'])
            need(info['id']==g['exec_id'] and info['container_id']==g['container'].cid and info['running'] and info['pid']>0,
                 'DYNTEAM_RACING_ACTUAL_OWN_EXEC_PID_RUNNING')
            birth=process_birth(info['pid']);init=g['container'].init_birth
            namespace_pids=[]
            for line in Path('/proc',str(birth.pid),'status').read_bytes().splitlines():
                if line.startswith(b'NSpid:'):namespace_pids=list(map(int,line.split()[1:]))
            need(birth.uid==birth.gid==10000 and (birth.pid_namespace,birth.mount_namespace,birth.network_namespace)==
                (init.pid_namespace,init.mount_namespace,init.network_namespace) and
                birth.start_ticks==stream['start_ticks'] and namespace_pids and namespace_pids[-1]==stream['namespace_pid'],
                'DYNTEAM_RACING_EXEC_ACTUAL_BIRTH_NAMESPACE_UID')
            domain=str(process_cgroup_v2({'pid':birth.pid,'start_ticks':birth.start_ticks,'boot_id':birth.boot_id}))
            init_domain=str(process_cgroup_v2({'pid':init.pid,'start_ticks':init.start_ticks,'boot_id':init.boot_id}))
            need(domain==init_domain,'DYNTEAM_RACING_EXEC_EXACT_ORIGINAL_AGENT_CGROUP')
            value=GameExecControl(self.t,ROLE,g['exec_id'],g['container'].cid,birth,domain,self.code_sha)
            if not hasattr(self.core,'native_racing_game_exec_controls'):self.core.native_racing_game_exec_controls={}
            self.core.native_racing_game_exec_controls[self.t,ROLE]=value
            g['registered']=True;g['state']='ACTUAL_GUEST_EXEC_REGISTERED';self._control(force=True)
        # Consume ONLY strict fixed PUBLIC records produced by this one exact
        # own exec. ROOT uses these immutable metadata receipts to call its
        # ORIGINAL native system test_suite publisher, never a new dispatcher.
        stream_path=g['root']/'GAME_STREAM_PUBLIC.jsonl'
        if stream_path.exists():
            need(not stream_path.is_symlink() and stream_path.stat().st_size<=262144,
                 'DYNTEAM_RACING_PUBLIC_COUNT_STREAM_BOUND')
            raw=stream_path.read_bytes();lines=raw.split(b'\n')
            if lines[-1]:lines=lines[:-1] # retain a partial append for next poll
            else:lines.pop()
            need(len(lines)>=g['public_cursor'],'DYNTEAM_RACING_PUBLIC_COUNT_STREAM_APPEND_ONLY')
            for line in lines[g['public_cursor']:]:
                row=public_game_record(json.loads(line))
                if row.get('schema')=='count14-racing-setup-completion-public-v1':
                    need(g['registered'] and g['ordinal']==row['round_ordinal']==1 and
                         self.setup_completion_triggers==g['setup_completion_triggers']==0,
                         'RACING_SETUP_COMPLETION_EXACT_FIRST_GAME_ONCE_INTENT')
                    self.setup_completion_triggers=1;g['setup_completion_triggers']=1
                elif row.get('schema')=='count14-racing-public-test-published-v1':
                    need(g['registered'] and row['round_ordinal']==g['ordinal'] and
                         row['publication_ordinal']==self.published_public+1 and
                         row['public_tests_in_round']==g['publications']+1,
                         'DYNTEAM_RACING_EXACT_OWN_EXEC_PUBLICATION_COUNTER_SEQUENCE')
                    self.published_public+=1;g['publications']+=1
                    self.publication_receipts.append(dict(trajectory=self.t,exec_id=g['exec_id'],
                        system_event_id='count14-racing-public-'+digest([self.sha,self.t,g['ordinal'],self.published_public]),
                        **row))
                g['public_cursor']+=1
        terminal=_last_public(g['root']/'EXEC_TERMINAL_PUBLIC.jsonl')
        if terminal is not None and not g['terminal']:
            need(terminal['id']==g['exec_id'] and terminal['nonce']==g['nonce'] and terminal['exit_code']==0 and
                 terminal['running'] is False,'DYNTEAM_RACING_OWN_EXEC_TERMINAL_NO_RETRY')
            final=_last_public(g['root']/'GAME_STREAM_PUBLIC.jsonl')
            need(final and final.get('schema')=='count14-racing-game-terminal-public-v1' and final.get('physical_terminal') is True,
                 'DYNTEAM_RACING_NATIVE_GAME_TYPED_TERMINAL_PUBLIC')
            need(final['setup_completion_trigger_count']==g['setup_completion_triggers'],
                 'RACING_SETUP_COMPLETION_TERMINAL_MATCHES_ORIGINAL_COUNT_STREAM')
            need(final['public_tests_published']==g['publications']==final['public_tests_accepted'] and
                 final['public_tests_catalogue_total']==self.published_public,
                 'DYNTEAM_RACING_EVERY_ACCEPTED_TEST_HAS_NORMAL_GIT_AND_PUBLIC_SHARE_RECEIPT')
            g['terminal']=True;self.accepted_public+=final['public_tests_accepted']
            self.schedule.close(g['ordinal'],physical_terminal=True);g['state']='PHYSICAL_TERMINAL';self._control(force=True)

    def poll(self):
        """Call from original owner's normal loop, not recursively inside it."""
        if self.failure:return self.public()
        try:
            self._control()
            if self.helper_index<len(HELPERS):
                role=HELPERS[self.helper_index]
                if role not in self.helpers:
                    if not self._start_helper(role):return self.public()
                if self._helper_step(role):self.helper_index+=1
                self.state='HELPERS_PREPARING';return self.public()
            self.state='HELPERS_PREPARED_ZERO_MODELS'
            for g in self.games:
                if not g['terminal']:
                    self._game_step(g)
                    if g['child'].poll() not in (None,0):raise RuntimeError('DYNTEAM_RACING_EXEC_CUSTODIAN_FAILED_RETAIN_ID')
            clock=self.core.active_clock.read(self.t)
            previous_clear=all(g['terminal'] for g in self.games)
            ordinal=self.schedule.observe(active_now=clock['active_ns']/1e9,progress_ordinal=self._progress(),
                original_admission_open=clock['mode']=='RUNNING' and not self.core.membership_fences[self.t].public_counts()['cut_held'],
                physical_previous_clear=previous_clear)
            if ordinal is not None:self._new_game(ordinal)
            return self.public()
        except Exception as error:
            self.failure={'exception_type':type(error).__name__,'locations':[]};tb=error.__traceback__
            while tb:self.failure['locations'].append({'file':tb.tb_frame.f_code.co_filename,'line':tb.tb_lineno,'function':tb.tb_frame.f_code.co_name});tb=tb.tb_next
            self.state='PARTIAL_RETAINED_NO_RETRY';return self.public()

    def public(self):
        return dict(state=self.state,trajectory=self.t,helpers_prepared=self.helper_index,helpers_expected=8,
            rounds_started=len(self.games),rounds_physically_terminal=sum(g['terminal'] for g in self.games),
            published_public_tests=self.published_public,
            setup_completion_trigger_count=self.setup_completion_triggers,
            racing_setup_completion_policy='AT_MOST_ONCE_FIRST_BACKGROUND_NORMAL_ENDTURN_EXACT_METADATA_MISSING',
            orchestration_exec_not_agent=True,scientific_host_writer=False,failure=self.failure)

    def public_publication_receipts(self):
        return tuple(dict(row) for row in self.publication_receipts)
