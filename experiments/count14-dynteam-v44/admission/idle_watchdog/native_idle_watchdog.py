"""Cold-only original live-worker watchdog, driven by SAME owner poll.

No new science/model loop, forced worker birth, retired wake or v2 replacement
prompt. Original watchdog native condition bodies/render/MM helpers are pinned.
Metadata writers join the existing exact FormalHostWriters checkpoint custody.
"""
from pathlib import Path
from types import MethodType
from dataclasses import asdict
import copy
import hashlib
import json
import os
import subprocess
import time

from common import need,digest
from native_peer_registry import process_birth
from native_idle_source import NativeIdleSources,compile_script
from native_idle_runtime import append


class NativeIdleWatchdog:
    def __init__(self,cohort,*,sources):
        from native_formal_cohort import NativeFormalCohort
        from original_relay_core import OriginalRelayCore
        need(type(cohort)is NativeFormalCohort and type(cohort.core)is OriginalRelayCore and
             not cohort.activation_attempted and set(cohort.core.gate.startup_held)==set(cohort.tracks) and
             not cohort.core.qualification_only and not cohort.core.closed and
             not hasattr(cohort,'native_idle_watchdog') and not hasattr(cohort,'formal_retirement'),
             'IDLE_ONLY_NEW_EXACT_FORMAL_COHORT_BEFORE_ACTIVATION_AND_RETIREMENT_INSTALL')
        self.cohort,self.core=cohort,cohort.core
        self.birth=process_birth(os.getpid());self.sources=sources
        need(not self.core.ledger.mutex._is_owned(),'IDLE_INSTALL_OUTSIDE_SCIENCE_LOCK')
        with self.core.ledger.mutex:
            need(self.core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0,
                 'IDLE_COLD_INSTALL_BEFORE_ANY_EXPERIMENT_MODEL')
        self.script,self.source_proofs=compile_script(sources)
        self.runtime=Path(__file__).resolve().with_name('native_idle_runtime.py')
        self.runtime_sha256=hashlib.sha256(self.runtime.read_bytes()).hexdigest()
        self.rows={};cohort.native_idle_watchdog=self
        for t in cohort.tracks:
            home=Path(self.core.rows[t]['root'])/'native-idle-watchdog-control'
            need(home.parent.resolve()==home.parent and not home.exists() and not home.is_symlink(),
                 'IDLE_NEW_EXACT_CONTROL_ROOT_NO_OLD_SCOPE_REUSE')
            home.mkdir(mode=0o700)
            layout=self.core.native_layout.current(t)
            self.rows[t]=dict(home=home,org=layout['org'],sequence=0,ordinal=0,last_active=None,
                held=True,closed=False,control=None,child=None,birth=None,history=[],host=None,failure=None)
            path=home/'native-watchdog-tick.sh'
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
            try:os.write(fd,self.script);os.fsync(fd)
            finally:os.close(fd)
            self._control(t)
        self.original_poll,self.original_public,self.original_activate=cohort.poll,cohort.public,cohort.activate
        cohort.poll=MethodType(lambda own:self.poll_cohort(),cohort)
        cohort.public=MethodType(lambda own:self.cohort_public(),cohort)
        cohort.activate=MethodType(lambda own:self.activate_cohort(),cohort)

    def outside(self):
        need(process_birth(os.getpid())==self.birth and self.cohort.native_idle_watchdog is self and
             not self.core.ledger.mutex._is_owned(),'IDLE_SAME_ORIGINAL_OWNER_OUTSIDE_ALL_SCIENCE_LOCKS')

    def receipt(self,t,kind,**fields):
        row=self.rows[t];row['sequence']+=1
        value=dict(fields)
        value.update(schema='count14-native-idle-control-owner-v1',trajectory=t,kind=kind,
            sequence=row['sequence'],no_model_dispatch=True)
        append(row['home']/f"O{row['sequence']:08d}-{kind}_PUBLIC.json",value)
        return value

    def _pointer(self,path,value):
        tmp=path.with_name('.'+path.name+'-'+str(os.getpid()))
        append(tmp,value);os.replace(tmp,path)

    def _control(self,t):
        row=self.rows[t]
        state=getattr(self.core,'source_task_ports',None)
        native={} if state is None else state.ports['STATE'].get(t,{})
        control=dict(schema='count14-native-idle-admission-control-v1',organization=row['org'],
            owner_pid=self.birth.pid,owner_start_ticks=self.birth.start_ticks,owner_boot_id=self.birth.boot_id,
            held=row['held'],closed=row['closed'],mattermost_origin=native.get('origins',{}).get('mattermost'),
            profile_root=self.core.native_layout.current(t)['profile_root'],
            docker_cli=self.core.native_host_environment['trajectories'][t]['launcher_env']['COUNT14_NATIVE_DOCKER'],
            docker_socket=self.core.native_host_environment['trajectories'][t]['launcher_env']['COUNT14_NATIVE_DOCKER_SOCKET'],
            mysql_container=self.core.cold_bootstrap.infra_birth_records.get((t,'mysql'),{}).get('cid'))
        if control!=row['control']:
            self.receipt(t,'ADMISSION',**control)
            self._pointer(row['home']/'ADMISSION_PUBLIC.json',control)
            row['control']=control

    def _fail(self,t,error,phase):
        row=self.rows[t]
        if row['failure'] is not None:return
        frames=[];tb=error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        row['failure']=dict(PUBLIC_code='NATIVE_IDLE_PARTIAL_RETAINED_NO_RETRY',phase=phase,
            exception_type=type(error).__name__,locations=frames)
        row['held']=True
        try:
            self._control(t)
            self.receipt(t,'FAILED_RETAINED',**row['failure'])
        except Exception as diagnostic_error:
            row['failure']['metadata_receipt_exception_type']=type(diagnostic_error).__name__
        try:self.core.ledger.latch_fault(t,'FORMAL_NATIVE_IDLE_FRAMEWORK_PARTIAL_RETAINED')
        except Exception as latch_error:
            row['failure']['original_fault_latch_exception_type']=type(latch_error).__name__
        # Never strand original paid settlement by throwing out of owner.poll.

    def reap(self,t):
        row=self.rows[t];child=row['child']
        if child is None:return
        code=child.poll()
        if code is None:return
        self.receipt(t,'TICK_TERMINAL',ordinal=row['ordinal'],exit_code=code)
        row['history'].append(dict(child=child,birth=row['birth'],ordinal=row['ordinal'],exit_code=code))
        row['child']=None;row['birth']=None
        if code!=0:
            self._fail(t,RuntimeError(),'ORIGINAL_NATIVE_WATCHDOG_CHILD_EXIT')

    def physical_clear(self,t):
        row=self.rows[t]
        return row['child'] is None and row['failure'] is None

    def checkpoint_hold(self,t):
        self.outside();row=self.rows[t]
        row['held']=True;self._control(t);self.reap(t)
        return self.physical_clear(t)

    def resume_after_cut(self,t):
        self.outside();row=self.rows[t]
        need(row['held'] and not row['closed'] and self.physical_clear(t),
             'IDLE_RESUME_ONLY_SAME_NATURALLY_DRAINED_CONTROL_CHILD')
        row['held']=False;self._control(t)

    def close_admission(self,t):
        self.outside();row=self.rows[t]
        row['held'],row['closed']=True,True;self._control(t);self.reap(t)

    def attach_host(self,t):
        from formal_host_writers import FormalHostWriters
        row=self.rows[t];track=self.cohort.tracks[t];host=track['host']
        if host is None or row['host'] is not None:return
        need(type(host)is FormalHostWriters and host.core is self.core and host.t==t and
             t in self.core.gate.startup_held and not host.held and
             not hasattr(host,'native_idle_watchdog'),'IDLE_JOIN_EXACT_ORIGINAL_HOST_WRITERS_COLD_BEFORE_RELEASE')
        row['host']=host;host.native_idle_watchdog=self
        original_hold,original_roots,original_step=host.hold,host.roots,host.step
        original_clear=host.tester.physical_clear;original_close=host.tester.close_admission
        def hold(bound):
            self.checkpoint_hold(t)
            return original_hold() and self.physical_clear(t)
        def roots(bound):
            need(row['held'] and self.physical_clear(t),'IDLE_CONTROL_ROOT_CAPTURE_ONLY_AFTER_PHYSICAL_DRAIN')
            return (*original_roots(),row['home'])
        def step(bound):
            before=host.checkpoint.state
            value=original_step()
            if before=='RELEASING' and host.checkpoint.state=='RUNNING':self.resume_after_cut(t)
            return value
        def close(bound):
            self.close_admission(t);return original_close()
        host.hold=MethodType(hold,host);host.roots=MethodType(roots,host);host.step=MethodType(step,host)
        host.tester.physical_clear=MethodType(lambda own:original_clear() and self.physical_clear(t),host.tester)
        host.tester.close_admission=MethodType(close,host.tester)

    def activate_cohort(self):
        self.outside()
        need(all(Path(p).is_file() and os.access(p,os.X_OK) for p in
             ('/bin/bash','/usr/bin/curl','/usr/bin/jq','/usr/bin/envsubst','/usr/bin/python3','/usr/bin/find')),
             'IDLE_ORIGINAL_NATIVE_HOST_TOOL_METADATA_PREFLIGHT_BEFORE_PAID_ACTIVATION')
        for t in self.rows:self.attach_host(t)
        attach_finished_ns=time.time_ns()
        need(all(row['host'] is not None for row in self.rows.values()),
             'IDLE_ALL_SIX_REAL_HOST_WRITERS_BOUND_BEFORE_UNIQUE_ACTIVATE')
        # msg246: consume only a real publication whose original sampler INTENT
        # was created after all six attach calls, with no restamp/extra census.
        producer=self.core.resource_producer
        resources=self.core.cohort_resources
        deadline=time.monotonic()+90
        post_attach_original_sample=False
        while time.monotonic()<deadline:
            producer.poll()
            resources.refresh()
            latest=next((record for record in reversed(producer.records)
                         if record['state']=='OBSERVATION_PUBLISHED'),None)
            if (latest is not None and
                (latest['directory']/'INTENT_PUBLIC.json').stat().st_mtime_ns>attach_finished_ns and
                resources.experiment_open()):
                loaded=resources.path.read_bytes()
                published=json.loads((latest['directory']/'PUBLISHED_PUBLIC.json').read_bytes())
                post_attach_original_sample=(
                    hashlib.sha256(loaded).hexdigest()==producer.last_published==published['value_sha256'] and
                    digest(json.loads(loaded))==resources.state['raw_public_receipt_sha256'] and
                    time.monotonic()<deadline and resources.experiment_open())
                if post_attach_original_sample:break
            time.sleep(min(.5,max(0,deadline-time.monotonic())))
        # Timeout cannot consume original_activate or activation_attempted.
        need(post_attach_original_sample,
             'IDLE_ACTIVATE_POST_ATTACH_REAL_NEW_INTENT_RESOURCE_SAMPLE_90S_TIMEOUT')
        return self.original_activate()

    def start_tick(self,t,active):
        row=self.rows[t];host=self.core.native_host_environment['trajectories'][t]
        need(row['child'] is None and row['failure'] is None and not row['closed'] and not row['held'] and
             self.cohort.tracks[t]['gate_released'] and self.cohort.tracks[t]['host'] is row['host'],
             'IDLE_ONE_ORIGINAL_METADATA_TICK_ON_ACTUAL_LIVE_TRAJECTORY')
        need(hashlib.sha256(self.runtime.read_bytes()).hexdigest()==self.runtime_sha256,
             'IDLE_PINNED_CONTROL_RUNTIME_UNCHANGED')
        native=self.core.source_task_ports.ports['STATE'][t]
        mysql=self.core.cold_bootstrap.infra_birth_records[t,'mysql']
        row['ordinal']+=1;row['last_active']=active
        tick=dict(schema='count14-native-idle-original-tick-v1',ordinal=row['ordinal'],active_seconds=active,
            wall_seconds=int(time.time()),same_original_pause_aware_clock=True,unknown_history_conservative=True)
        append(row['home']/f"T{row['ordinal']:08d}-INPUT_PUBLIC.json",tick)
        self._pointer(row['home']/'CURRENT_TICK_PUBLIC.json',tick)
        dedup=row['home']/'original-account-dedup'
        if not dedup.exists():dedup.mkdir(mode=0o700)
        env=dict(PATH='/usr/bin:/bin',HOME=str(row['home']),LANG='C.UTF-8',**host['launcher_env'],
            ENV_FILE=host['envfile'],SPAWN_SOURCE=host['spawn_source'],TASK_CHANNEL_ID=native['task_channel'],
            MYSQL_CONTAINER=mysql['cid'],COUNT14_IDLE_NATIVE_ROOT=str(Path(self.sources.pbench_source).parent.parent),
            COUNT14_IDLE_PYTHON=host['launcher_env']['COUNT14_NATIVE_PYTHON'],COUNT14_IDLE_RUNTIME=str(self.runtime),
            COUNT14_IDLE_HOME=str(row['home']),COUNT14_IDLE_WALL_SECONDS=str(tick['wall_seconds']),
            COUNT14_IDLE_DEDUP=str(dedup))
        self.receipt(t,'TICK_INTENT',ordinal=row['ordinal'],active_seconds=active)
        row['child']=subprocess.Popen(['/bin/bash',str(row['home']/'native-watchdog-tick.sh')],
            cwd=host['project_root'],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        row['birth']=process_birth(row['child'].pid)
        self.receipt(t,'TICK_STARTED',ordinal=row['ordinal'],child_birth=asdict(row['birth']))

    def poll(self):
        self.outside()
        if self.core.closed:return self.public()
        for t,row in self.rows.items():
            try:
                self.attach_host(t);self.reap(t)
                track=self.cohort.tracks[t]
                if row['failure'] is not None or not track['gate_released'] or row['host'] is None:continue
                clock=self.core.active_clock.read(t)
                running=(clock['mode']=='RUNNING' and track['state']=='RUNNING_ORIGINAL_FORMAL_TRACK' and
                    track['checkpoint'].state in('BOUND_MODELS_HELD','RUNNING') and not row['host'].held and not row['closed'])
                if not running:
                    if not row['held']:self.checkpoint_hold(t)
                    continue
                if row['held']:self.resume_after_cut(t)
                active=clock['active_ns']//1_000_000_000
                if row['child'] is None and (row['last_active'] is None or active-row['last_active']>=60):
                    self.start_tick(t,active)
            except Exception as error:self._fail(t,error,'SAME_OWNER_NATIVE_WATCHDOG_POLL')
        return self.public()

    def poll_cohort(self):
        value=self.original_poll()
        self.poll()
        return self.cohort_public() if not self.core.closed else value

    def cohort_public(self):
        if self.core.closed:return copy.deepcopy(self.core.smoke_terminal_public)
        value=self.original_public();value['native_idle_watchdog']=self.public();return value

    def public(self):
        return dict(schema='count14-native-live-worker-watchdog-cold-WIP-v1',
            source_functions=self.source_proofs,original_idle_template_opaque_unread_by_DEV=True,
            per_track={t:dict(ticks_started=r['ordinal'],metadata_child_live=r['child'] is not None,
                host_writer_bound=r['host'] is not None,held=r['held'],closed=r['closed'],failure=copy.deepcopy(r['failure']))
                for t,r in self.rows.items()},tick_active_seconds=60,idle_and_repeat_active_seconds=600,
            no_worker_spawn_or_retired_identity_revival=True,first_formal_natural_point_K3_remaining=True,
            zero_live_no_pending_scientific_boundary_remaining=True,actual_Dev4_or_formal_qualification=False,
            formal_delivery=False)


def install_native_idle_watchdog(cohort,*,sources):
    return NativeIdleWatchdog(cohort,sources=sources)
