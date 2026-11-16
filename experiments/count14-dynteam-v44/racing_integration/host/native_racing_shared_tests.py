"""Cold worker RO views + ORIGINAL system test_suite notifications.

No case/model/question body is opened here. Accepted cases remain scientific
guest-owned in the background's original /work writer domain. Only the exact
manager's strict PUBLIC publication ordinals cross this metadata seam. The
existing native publisher runs without a science lock; the same owner keeps
polling native model/control custody while its ordinary RPC completes.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy,json,os,shlex,stat,time

from common import need,digest
from native_beta_layout import native_aliases

PUBLIC_TARGET='/opt/count14-racing-public-tests'


def _append(path,value,*,mode=0o444):
    raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
    path.chmod(mode)


def _identity(path):
    p=Path(path);s=p.lstat()
    need(p.resolve()==p and not p.is_symlink() and stat.S_ISDIR(s.st_mode),
         'RACING_SHARED_PUBLIC_EXACT_CANONICAL_DIRECTORY')
    return s.st_dev,s.st_ino


def readonly_worker_overlay(aliases,source):
    """Pure cold config: 32 registered workers including future native births."""
    workers={r:a for r,a in aliases.items() if a['kind']=='worker'}
    need(len(workers)==32 and set(workers)=={f'worker-{i:02d}' for i in range(32)},
         'RACING_SHARED_ALL_32_NATIVE_WORKER_SLOTS')
    return {'services':{a['agent_service']:{'volumes':[{'type':'bind','source':str(source),
        'target':PUBLIC_TARGET,'read_only':True}]} for a in workers.values()}}


class RacingSharedPublicTests:
    def __init__(self,core,trajectory,manager):
        from original_relay_core import OriginalRelayCore
        from smoke_racing_tools_game_manager import NativeRacingGameManager
        need(type(core) is OriginalRelayCore and type(manager) is NativeRacingGameManager and
             manager.core is core and manager.t==trajectory and
             core.native_racing_game_managers[trajectory] is manager and
             core.rows[trajectory]['arm']=='DYNTEAM_RACING' and trajectory in core.gate.startup_held and
             not core.qualification_only,'RACING_SHARED_COLD_SAME_REAL_MANAGER_BEFORE_START')
        self.core,self.t,self.manager=core,trajectory,manager
        self.aliases=native_aliases('DYNTEAM_RACING')
        registry=core.native_containers
        need(not any((trajectory,r,'agent') in rows for rows in (registry.records,registry.boot_plans)
                     for r,a in self.aliases.items() if a['kind']=='worker'),
             'RACING_SHARED_RO_MOUNTS_COLD_BEFORE_ANY_WORKER_UP')
        layout=core.native_layout.current(trajectory)
        workspace=Path(layout['roles']['racing-background-00']['workspace'])
        need(workspace.resolve()==workspace and workspace.is_relative_to(Path(core.rows[trajectory]['root'])),
             'RACING_SHARED_WITHIN_BACKGROUND_ORIGINAL_WORKSPACE')
        self.source=workspace/'.count14-racing'/'public-accepted-tests'
        for path in (self.source.parent,self.source):
            need(not path.exists() and not path.is_symlink(),'RACING_SHARED_NEW_EXACT_TWO_DIRECTORIES')
            path.mkdir(mode=0o755);path.chmod(0o755);os.chown(path,10000,10000)
        self.source_identity=_identity(self.source)
        host=core.native_host_environment['trajectories'][trajectory]
        self.home=Path(core.rows[trajectory]['root'])/'racing-public-consumer';self.home.mkdir(mode=0o700)
        self.overlay=self.home/'compose.worker-racing-public-ro.json'
        _append(self.overlay,readonly_worker_overlay(self.aliases,self.source),mode=0o400)
        if 'native_bridge_user_layer' in host:
            from native_bridge_user_cold import append_existing_cold_overlay
            append_existing_cold_overlay(core,trajectory,self.overlay)
        else:
            command=list(host['compose']);at=command.index('--project-name')
            command[at:at]=['-f',str(self.overlay)]
            host['compose']=tuple(command);host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND']=shlex.join(command)
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='own-native-system-test-suite')
        self.active=None;self.completed=0;self.started=0;self.closing=False;self.failure=None;self.tester=None
        self.latest_live_ro_workers=0
        if not hasattr(core,'racing_public_consumers'):core.racing_public_consumers={}
        need(trajectory not in core.racing_public_consumers,'RACING_SHARED_ONE_CONSUMER_SAME_OWNER')
        core.racing_public_consumers[trajectory]=self

    def bind_original_publisher(self,tester):
        from smoke_bootstrap_task_tester import NativeTesterInitialRelease
        from formal_count14_tester import FormalCount14Tester
        ready=(type(tester) is NativeTesterInitialRelease and
               tester.state=='ORIGINAL_TESTER_CYCLE0_PUBLISHED_MODELS_HELD' or
               type(tester) is FormalCount14Tester and
               tester.state=='TASK_AWARE_NATIVE_CYCLE0_READY_MODELS_HELD')
        need(self.tester is None and ready and
             tester.core is self.core and tester.t==self.t and tester.run is not None and
             self.t in self.core.gate.startup_held,
             'RACING_SHARED_ONLY_EXISTING_ORIGINAL_SYSTEM_PUBLISHER')
        need(tester.run.workers==[self.core.native_layout.current(self.t)['org']+'-worker'+str(n)
                                for n in range(1,33)],'RACING_SHARED_ORIGINAL_32_NATIVE_ADDRESSEES')
        self.tester=tester

    def verify_actual_readonly_mounts(self):
        """Only fresh Docker/process/mount inode metadata; no science file read."""
        need(not self.core.ledger.mutex._is_owned(),'RACING_SHARED_NO_DOCKER_IO_UNDER_SCIENCE_LOCK')
        need(_identity(self.source)==self.source_identity,'RACING_SHARED_PUBLIC_SOURCE_INODE_CHANGED')
        registry=self.core.native_containers;count=0
        records={**registry.boot_plans,**registry.records}
        for role,alias in self.aliases.items():
            if alias['kind']!='worker':continue
            bound=records.get((self.t,role,'agent'))
            if bound is None:continue
            row=registry.docker.inspect(bound.cid)
            if not row['running']:continue
            from native_container_retirement import ContainerBinding
            if not isinstance(bound,ContainerBinding):
                bound=ContainerBinding(self.t,role,'agent',bound.cid,bound.image_id,bound.init_birth,bound.init_birth)
            registry.validate(bound,row,running=True)
            matches=[m for m in row['mounts'] if m.get('Destination')==PUBLIC_TARGET]
            need(len(matches)==1 and matches[0].get('Type')=='bind' and
                 matches[0].get('Source')==str(self.source) and matches[0].get('RW') is False,
                 'RACING_SHARED_TRUE_COLD_READONLY_MOUNT_REQUIRED')
            seen=Path('/proc',str(row['pid']),'root',PUBLIC_TARGET.lstrip('/')).stat()
            need((seen.st_dev,seen.st_ino)==self.source_identity,'RACING_SHARED_ACTUAL_CONTAINER_MOUNT_INODE')
            count+=1
        self.latest_live_ro_workers=count;return count

    def request_checkpoint_hold(self):
        # This is NOT a Game/future/model drain requirement. Only this bounded
        # original metadata RPC must not be a host writer across the cut.
        self.closing=True

    def resume_after_original_cut(self):
        need(self.active is None and self.failure is None,'RACING_SHARED_RESUME_ONLY_METADATA_CUSTODY_CLEAR')
        self.closing=False

    def checkpoint_ready(self):return self.closing and self.active is None and self.failure is None

    def capture_roots(self):
        # Cases themselves are already inside the background's ORIGINAL /work
        # whole-domain capture; include this host-only publication cursor as
        # well. No caller may interpret this as a cold SDK restore proof.
        need(not self.core.ledger.mutex._is_owned() and self.checkpoint_ready(),
             'RACING_SHARED_HOST_METADATA_DRAINED_BEFORE_CAPTURE')
        need(_identity(self.source)==self.source_identity and
             self.home.resolve()==self.home and self.home.is_dir(),
             'RACING_SHARED_EXACT_SOURCE_AND_HOST_RECEIPT_ROOT')
        return (self.home,)

    def poll(self):
        need(not self.core.ledger.mutex._is_owned(),'RACING_SHARED_PUBLICATION_OUTSIDE_SCIENCE_LOCK')
        if self.failure:return self.public()
        try:
            if self.active is not None:
                if not self.active['future'].done():return self.public()
                self.active['future'].result() # original call's genuine terminal; no retry here
                self.completed+=1
                _append(self.home/(f'{self.completed:08d}-DONE-PUBLIC.json'),{
                    'schema':'count14-racing-original-system-publication-done-v1',
                    'trajectory':self.t,'publication_ordinal':self.completed,
                    'system_event_id':self.active['row']['system_event_id'],'kind':'test_suite',
                    'original_native_publisher_returned':True,'worker_addressees':32,'official_verdict':False})
                self.active=None
            if self.closing or self.tester is None:return self.public()
            rows=self.manager.public_publication_receipts()
            if len(rows)<=self.completed:return self.public()
            row=rows[self.completed]
            need(row['trajectory']==self.t and row['publication_ordinal']==self.completed+1 and
                 row['public_test_path']==PUBLIC_TARGET and row['normal_science_git_push'] is True and
                 row['official_verdict'] is False,'RACING_SHARED_EXACT_MANAGER_ORDINAL')
            self.verify_actual_readonly_mounts()
            raw={'path':PUBLIC_TARGET,'published_tests':row['publication_ordinal'],
                 'round_ordinal':row['round_ordinal'],'official_verdict':False}
            summary=('New public count14 regression/reproduction tests are available at '+PUBLIC_TARGET+
                     '; public tests only, not official evaluation feedback.')
            _append(self.home/(f'{self.completed+1:08d}-INTENT-PUBLIC.json'),{
                'schema':'count14-racing-original-system-publication-intent-v1',
                'trajectory':self.t,'publication_ordinal':row['publication_ordinal'],
                'round_ordinal':row['round_ordinal'],'system_event_id':row['system_event_id'],
                'kind':'test_suite','worker_addressees':32,'public_path':PUBLIC_TARGET,
                'observed_live_RO_workers':self.latest_live_ro_workers,'official_verdict':False})
            self.started+=1
            # Original publisher preserves its own idempotent event semantics.
            # No provider key, actor token, case text, new model call/dispatcher
            # or ledger action is passed into this normal system notification.
            future=self.pool.submit(self.tester.run.publish,row['system_event_id'],self.tester.run.workers,
                                    'test_suite',summary,raw)
            self.active={'row':copy.deepcopy(row),'future':future,'started_ns':time.monotonic_ns()}
            return self.public()
        except Exception as error:
            frames=[];tb=error.__traceback__
            while tb:frames.append({'file':tb.tb_frame.f_code.co_filename,'line':tb.tb_lineno,
                                   'function':tb.tb_frame.f_code.co_name});tb=tb.tb_next
            self.failure={'PUBLIC_code':'RACING_SYSTEM_EVENT_PARTIAL_RETAINED_NO_RETRY',
                          'exception_type':type(error).__name__,'locations':frames}
            return self.public()

    def close_after_drained(self):
        need(self.closing and self.active is None,'RACING_SHARED_ONLY_NATURALLY_DRAINED_CLOSE')
        self.pool.shutdown(wait=False)

    def public(self):
        return {'schema':'count14-racing-public-consumer-control-v1','trajectory':self.t,
            'planned_readonly_worker_slots':32,'last_verified_live_RO_workers':self.latest_live_ro_workers,
            'events_started':self.started,'events_normal_return':self.completed,
            'event_physical_terminal_unproven':self.active is not None and not self.active['future'].done(),
            'failed_intent_retained':self.failure is not None,'checkpoint_hold':self.closing,
            'case_or_model_or_question_body_read_by_adapter':False,'failure':copy.deepcopy(self.failure)}
