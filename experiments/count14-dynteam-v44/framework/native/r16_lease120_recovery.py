"""User-approved R16 original-session recovery: fixed host-only metadata API.

No SSH/Docker/signals/session reads/SQL reset/old-event replay. OPS owns process
rebuild, original-session loading, source isolation and fresh native metadata.
This explicit adoption path does not weaken any first-start constructor.
"""
from contextlib import ExitStack
from pathlib import Path
from datetime import datetime,timezone
import copy,os,time
from bridge import process_identity
from common import need,digest,sha
from native_whole_team import NativeWholeTeamRegistration,NativeWholeTeamBackupPorts
from native_writer_fence import NativeWriterFence,CgroupV2Domain
from native_scientific_owner import NativeScientificOwner
from run_native_scientific6 import ScientificSixDriver

CLOCK_READER_SHA256='ee22d21d1285b251aa872e0b3f2a25d5d959b3a910ff9e28db4b4a65b99e2b6f'
LABEL='R16 基础设施恢复后续跑（原 session）'
PREFIX='agensh-comparison-20261027-scientific6-r16/'
SEEDS={1:4287909351,2:1636023914,3:2619738241}
TARGETS={PREFIX+setting+'/block-'+str(b)+'/seed-'+str(SEEDS[b])
         for setting,b in [('Agensh-1',2),('Agensh-1',3),('Agensh-16',1),('Agensh-16',2),('Agensh-16',3)]}
def utc():return datetime.now(timezone.utc).isoformat()
def _driver(d,owner):
    need(type(d)is ScientificSixDriver and d.shared_started and not d.failed and not d.finished,
         'STRICT_RECOVERY_ORIGINAL_RUNNING_DRIVER')
    need(process_identity(os.getpid())==owner,'STRICT_RECOVERY_EXACT_OWNER')
def _controller(d,t):
    need(t in TARGETS and t in d.records,'STRICT_RECOVERY_ONLY_AUTHORIZED_FIVE')
    c=d.records[t]['launch'].controller
    need(type(c)is NativeScientificOwner and c.t==t and c.ledger is d.ledger
         and c.state=='RUNNING' and not c.step_in_progress and c.cut is None and c.stage is None
         and c.team.writer_fence is c.fence and c.fence.state=='REGISTERED',
         'STRICT_RECOVERY_BETWEEN_ORIGINAL_CUTS_ONLY')
    f=d.ledger.frontier(t)
    need(f['state']=='RUNNING' and f['unresolved']==f['reserved']==f['active_operations']==0
         and not d.ledger.admission_fault(t),'STRICT_RECOVERY_NO_ACCEPTED_WORK_OR_FAULT')
    c._shared();return c

def _native(v):
    need(type(v)is dict and set(v)=={'pending','sending','retrying','failed_metadata_sha256'},
         'STRICT_RECOVERY_NATIVE_SAFE_FIELDS')
    need(all(type(v[k])is int and v[k]==0 for k in ('pending','sending','retrying')),
         'STRICT_RECOVERY_NATIVE_QUEUE_NOT_QUIESCENT')
    sha(v['failed_metadata_sha256']);return copy.deepcopy(v)

def prepare_original_recovery(driver, *, expected_owner, original_session_sha256,
                              native_before, preflight_evidence_sha256):
    """Before any affected process is retired. Hold capacity and neutral posts.

    ``native_before`` and session pins come ONLY from OPS original consistent
    metadata projection. No candidate/model/message/session body is accepted.
    Old router may now exit; old registration is retained, not forged live.
    """
    _driver(driver,expected_owner);sha(preflight_evidence_sha256)
    selected=set(original_session_sha256)
    need(bool(selected) and selected==set(native_before) and selected<=TARGETS,
         'STRICT_RECOVERY_SELECTED_ORIGINAL_PREFLIGHT')
    prior=getattr(driver,'_r16_original_recovery',None)
    need(prior is not None and prior['released'] and prior['owner']==expected_owner
         and all(original_session_sha256[t]==prior['plans'][t]['sessions'] for t in selected),
         'STRICT_RECOVERY_PRESERVE_ORIGINAL50_SESSION_PINS')
    need(not hasattr(driver,'_r16_lease120_recovery'),'STRICT_RECOVERY_PREPARE_ONCE')
    manager=driver._r16_natural_manager
    plans={}
    # Same lock order as original neutral monitor, then original controllers.
    with manager.lock,ExitStack()as locks:
        for t in sorted(selected):
            c=driver.records[t]['launch'].controller;locks.enter_context(c.lock);c=_controller(driver,t)
            need(set(original_session_sha256[t])==set(c.team.roles),'STRICT_RECOVERY_ORIGINAL_ROLE_PINS')
            for pin in original_session_sha256[t].values():sha(pin)
            native=_native(native_before[t]);old=c.fence.whole_team
            need(type(old)is NativeWholeTeamRegistration and old.owner is c.team,
                 'STRICT_RECOVERY_ORIGINAL_WHOLE_TEAM')
            old.current();c.fence._coverage()
            plans[t]={'controller':c,'original_registration':old,'original_fence':c.fence,
                      'original_backups':c.backup_ports,'original_graph':copy.deepcopy(c.graph),
                      'original_services':copy.deepcopy(old.services),'original_peers':copy.deepcopy(c.team.peers),
                      'sessions':copy.deepcopy(original_session_sha256[t]),'native_before':native,
                      'original_points_sha256':digest(c.points),'original_posts':manager.posts[t],
                      'native_ports':c.team._stage_registry,'status':'PREPARED'}
        with driver.ledger.tx():
            row=driver.ledger.db.execute('SELECT * FROM model_control WHERE singleton=1').fetchone()
            need(row is not None and row['paused']==0,'STRICT_RECOVERY_CAPACITY_PREVIOUSLY_RUNNING')
            driver.ledger.db.execute("UPDATE model_control SET paused=1,epoch=epoch+1,reason='R16_STRICT_ORIGINAL_SESSION_RECOVERY' WHERE singleton=1")
            driver.ledger.event('GLOBAL','R16_LEASE120_ORIGINAL_SESSION_RECOVERY_PREPARED',{
                'preflight_evidence_sha256':preflight_evidence_sha256,
                'original_session_roster_sha256':digest(original_session_sha256),
                'trajectories':sorted(selected),'search_or_aux_cancelled':0,'old_event_reset_or_bootstrap':False})
        old_poll=manager.poll_one
        def held_poll(t):
            if t in selected and not driver._r16_lease120_recovery['released']:return
            return old_poll(t)
        state={'plans':plans,'owner':copy.deepcopy(expected_owner),'started_at':utc(),
               'started_mono':time.monotonic(),'released':False,'original_poll_one':old_poll}
        driver._r16_lease120_recovery=state;manager.poll_one=held_poll
    with driver.ledger.capacity_changed:driver.ledger.capacity_changed.notify_all()
    return {'status':'PREPARED_CAPACITY_AND_NEUTRAL_HELD','roles':sum(len(v['sessions'])for v in plans.values()),
            'old_records_retained':True,'prompts_or_replay':False}

def _role_scope(fence,identity):
    need(type(identity)is dict and set(identity)=={'pid','start_ticks','boot_id'}
         and process_identity(identity['pid'])==identity,'STRICT_RECOVERY_NEW_OS_IDENTITY')
    matches=[i for i,d in enumerate(fence.domains)if d.contains(identity)]
    need(len(matches)==1,'STRICT_RECOVERY_NEW_PROCESS_ONE_TEAM_DOMAIN');return matches[0]

def rebind_original_track(driver, trajectory, *, services, writer_domains,
                          restored_roles, native_after, clock_reader_sha256):
    """Adopt actual replacement router/CLI identities, NEVER worker namespaces.

    Keep worker containers, UID/pidns/netns, SDKs, ports, credentials, mounts and
    all non-router services unchanged. Only backend-router-* process identities
    may change. New CgroupV2Domain objects use their ordinary kernel/proc guards.
    This is not a first-start constructor or an arbitrary scope replacement.
    """
    state=driver._r16_lease120_recovery;_driver(driver,state['owner'])
    need(clock_reader_sha256==CLOCK_READER_SHA256,'STRICT_RECOVERY_EXACT_V4_READER_SHA')
    need(not state['released'],'STRICT_RECOVERY_ALREADY_RELEASED')
    plan=state['plans'][trajectory];c=plan['controller'];launch=driver.records[trajectory]['launch']
    with driver._r16_natural_manager.lock,c.lock:
        c=_controller(driver,trajectory)
        need(plan['status']=='PREPARED' and driver.ledger.model_paused(),
             'STRICT_RECOVERY_ONE_REBIND_WHILE_HELD')
        native=_native(native_after)
        need(native==plan['native_before'],'STRICT_RECOVERY_FAILED_ROWS_OR_NATIVE_STATE_CHANGED')
        need(c.team.peers==plan['original_peers'] and c.team._stage_registry is plan['native_ports']
             and c.fence is plan['original_fence'] and c.backup_ports is plan['original_backups']
             and c.graph==plan['original_graph'] and digest(c.points)==plan['original_points_sha256'],
             'STRICT_RECOVERY_ORIGINAL_WORKERS_PORTS_POINTS_PRESERVED')
        previous=plan['original_registration'];routers={'backend-router-'+r for r in c.team.roles}
        need(type(services)is dict and set(services)==set(previous.services)
             and routers<=set(services),'STRICT_RECOVERY_EXACT_SERVICE_ROSTER')
        for name,row in services.items():
            old=plan['original_services'][name]
            need(type(row)is dict and set(row)=={'process','roots'} and row['roots']==old['roots'],
                 'STRICT_RECOVERY_KEEP_ALL_ORIGINAL_PHYSICAL_ROOTS')
            if name not in routers:need(row==old,'STRICT_RECOVERY_ONLY_ROUTERS_REPLACED')
        need(type(writer_domains)is tuple and len(writer_domains)==len(c.fence.domains)
             and all(type(d)is CgroupV2Domain for d in writer_domains),
             'STRICT_RECOVERY_COMPLETE_EXACT_NEW_CGROUP_SET')
        # Explicit recovery registration, not a bypass in the first-start API.
        registration=object.__new__(NativeWholeTeamRegistration)
        registration.owner=c.team;registration.ledger=c.ledger;registration.t=c.t
        registration.services=copy.deepcopy(services);registration.backends=previous.backends
        registration.inventory_sha=digest(services);registration.current()
        fence=NativeWriterFence(c.team,writer_domains,expected_domains_sha256=digest(sorted(d.binding_sha for d in writer_domains)),whole_team=registration)
        need(all(not d.frozen()and d.read('cgroup.freeze').strip()=='0'for d in writer_domains),
             'STRICT_RECOVERY_NEW_TEAM_NOT_PARKED')
        need(type(restored_roles)is dict and set(restored_roles)==set(c.team.roles),
             'STRICT_RECOVERY_ALL_ORIGINAL_ROLES_LOADED')
        safe={}
        for role,v in restored_roles.items():
            need(type(v)is dict and set(v)=={'session_sha256','loaded_original','prompt_sent','router','cli'}
                 and v['loaded_original']is True and v['prompt_sent']is False
                 and v['session_sha256']==plan['sessions'][role],
                 'ORIGINAL_SESSION_RESTORE_MISSING_FAILED_OR_SHA_CHANGED_NO_FALLBACK')
            router_domain=_role_scope(fence,v['router']);cli_domain=_role_scope(fence,v['cli'])
            peer=c.team.peers[role];worker={k:peer[k]for k in('pid','start_ticks')}
            worker['boot_id']=state['owner']['boot_id']
            need(cli_domain==_role_scope(fence,worker)
                 and router_domain==_role_scope(fence,services['backend-router-'+role]['process']),
                 'STRICT_RECOVERY_ROLE_BOUND_ROUTER_AND_CLI_SCOPE')
            safe[role]=copy.deepcopy(v)
        old_bp=plan['original_backups']
        backups=NativeWholeTeamBackupPorts(registration,old_bp.git,old_bp.relay,old_bp.bridge,roles=old_bp.roles)
        # Only now publish active pointers. Original objects remain in plan.
        plan['status']='REBIND_STARTED'
        c.team.writer_fence=fence;c.fence=fence;launch.fence=fence
        c.backup_ports=backups;c.backup_callable=backups;launch.backups=backups
        c.graph=copy.deepcopy(backups.graph);c.graph_sha=backups.graph_sha
        c.ledger.native_whole_team_registrations[c.t]=registration
        c._shared();fence._coverage();old_bp.bridge._runtime(c.ledger.frontier(c.t)['generation'])
        plan.update(status='REBOUND_ORIGINAL_SESSION',restored_roles=safe,
                    new_registration=registration,new_fence=fence,new_backups=backups,
                    rebound_at=utc(),native_after=native,clock_reader_sha256=clock_reader_sha256)
        with c.ledger.tx():c.ledger.event(c.t,'R16_LEASE120_ORIGINAL_SESSION_SCOPE_REBOUND',{
            'report_label':LABEL,'old_inventory_sha256':previous.inventory_sha,
            'new_inventory_sha256':registration.inventory_sha,'old_graph_sha256':digest(plan['original_graph']),
            'new_graph_sha256':c.graph_sha,'old_domains_sha256':plan['original_fence'].domains_sha,
            'new_domains_sha256':fence.domains_sha,'restored_roles':safe,
            'failed_rows_metadata_sha256':native['failed_metadata_sha256'],
            'original_points_sha256':plan['original_points_sha256'],'old_objects_retained':True,
            'new_session_or_event_reset_or_bootstrap':False})
        return {'status':plan['status'],'trajectory':c.t,'roles':len(safe),'report_label':LABEL}

def finish_original_recovery(driver, *, fresh_admission, recovery_evidence_sha256):
    """After ALL selected original sessions load+SHA+native state+scope proof succeed.

    OPS writes fresh per-role CLOCK_READY only after this returns. New original
    fixed neutral posts may queue, but no prompt ran during session preparation.
    All original accounting and the existing 600-second policy remain intact.
    """
    state=driver._r16_lease120_recovery;_driver(driver,state['owner']);sha(recovery_evidence_sha256)
    need(not state['released'],'STRICT_RECOVERY_FINISH_ONCE')
    manager=driver._r16_natural_manager
    with manager.lock,ExitStack()as locks:
        for t,plan in sorted(state['plans'].items()):
            c=plan['controller'];locks.enter_context(c.lock)
            need(plan['status']=='REBOUND_ORIGINAL_SESSION','STRICT_RECOVERY_ALL_FIVE_MUST_REBIND')
            _controller(driver,t);c.fence._coverage()
            for v in plan['restored_roles'].values():_role_scope(c.fence,v['router']);_role_scope(c.fence,v['cli'])
            need(manager.posts[t]==plan['original_posts'],'STRICT_RECOVERY_NO_EXTRA_NEUTRAL_DURING_HOLD')
        ended=utc();duration=time.monotonic()-state['started_mono']
        for t,plan in sorted(state['plans'].items()):
            c=plan['controller'] # original recovery annotation hook retained
            with c.ledger.tx():c.ledger.event(t,'R16_LEASE120_ORIGINAL_SESSION_RECOVERY_COMPLETED',{
                'report_label':LABEL,'intervention_started_at':state['started_at'],'intervention_ended_at':ended,
                'pause_seconds':duration,'roles':plan['restored_roles'],'neutral_messages_before':plan['original_posts'],
                'neutral_messages_after':manager.posts[t],'recovery_evidence_sha256':recovery_evidence_sha256,
                'clock_reader_sha256':plan['clock_reader_sha256'],'effective_reader_lease_ns':120_000_000_000,
                'historical_natural_points_and_K3_retained':True,'main_analysis_inclusion':'USER_DECISION_PENDING'})
        # Original capacity release validates current trusted owner/health pins;
        # no new owner/ledger/model-control construction or repeated charge.
        driver.capacity.release(owner_evidence=fresh_admission)
        state['released']=True;state['ended_at']=ended;state['pause_seconds']=duration
    with driver.ledger.capacity_changed:driver.ledger.capacity_changed.notify_all()
    return {'status':'SELECTED_ORIGINAL_RECOVERY_COMPLETE_CAPACITY_RELEASED','roles':sum(len(p['sessions']) for p in state['plans'].values()),
            'report_label':LABEL,'pause_seconds':duration,'extra_bootstrap_or_replay':False}
