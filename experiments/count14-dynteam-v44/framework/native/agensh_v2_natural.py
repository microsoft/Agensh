"""New-root binding of the qualified first-natural-stop policy.

Metadata-only supervisor. Native controller performs the original whole-team
freeze, backups, CAS, v2.1 and K3; no scientific payload is inspected here.
No router signal/attach/restart, task replay, failed-event reset or ledger reopen.
"""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,threading,time
from common import need,digest,wire,strict,hash_file,integer,sha
from r16_natural_contract import POLICY_SHA,TEMPLATE,TEMPLATE_SHA,metadata

PORT_FIELDS={'trajectory','pending','sending','retrying','team_model_inflight','activity_seq','channel_identity'}
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def check_sample(t,s):
    need(type(s)is dict and set(s)==PORT_FIELDS and s['trajectory']==t,'NATURAL_EXACT_IDLE_METADATA')
    for key in ('pending','sending','retrying','team_model_inflight'):integer(s[key],'NATURAL_IDLE_COUNT')
    sha(s['activity_seq']);need(type(s['channel_identity'])is str and 0<len(s['channel_identity'])<=128,'NATURAL_ORIGINAL_CHANNEL_ID')
    return not any(s[k]for k in ('pending','sending','retrying','team_model_inflight'))

class NaturalStopManager:
    def __init__(self,driver,policy,ports,*,monotonic=time.monotonic):
        need(policy['schema']=='ops-r16-natural-stop-neutral-policy-v1'and policy['idle_seconds']==600
             and policy['message']['template_utf8']==TEMPLATE
             and policy['message']['template_sha256']==TEMPLATE_SHA
             and policy['budget_tokens']==20000000,'NATURAL_FIXED_USER_POLICY')
        need(hashlib.sha256(TEMPLATE.encode()).hexdigest()==TEMPLATE_SHA,'NATURAL_FIXED_TEMPLATE')
        need(callable(ports.poll_native_idle)and callable(ports.post_neutral),'NATURAL_TRUSTED_PORTS')
        self.driver=driver;self.ledger=driver.ledger;self.policy=copy.deepcopy(policy);self.ports=ports
        self.clock=monotonic;self.lock=threading.RLock();self.stop=threading.Event();self.thread=None
        self.tracks={v['trajectory']:copy.deepcopy(v)for v in policy['tracks']}
        need(set(self.tracks)==set(driver.rows)and len(self.tracks)==6,'NATURAL_NEW_SIX_COMPILED_TRACKS')
        self.idle={};self.first={};self.last_errors={};self.posts={t:0 for t in self.tracks}
        self.outcomes={t:{key:0 for key in ('DELIVERED','REJECTED','UNKNOWN')}for t in self.tracks}
        self._status_snapshot={}
        # Never reopen either the ledger or queue. New derivative state only;
        # original requests/charges/events remain untouched append-only prefixes.
        with self.ledger.mutex:
            need(self.ledger.db.execute("SELECT 1 FROM sqlite_master WHERE name='r16_natural_first'").fetchone()is None,
                 'NATURAL_ALREADY_INSTALLED_RETAIN_NO_REAPPLY')
            self.ledger.db.executescript('''
                CREATE TABLE r16_natural_first(trajectory TEXT PRIMARY KEY,metadata TEXT NOT NULL);
                CREATE TABLE r16_neutral_intents(trajectory TEXT NOT NULL,ordinal INTEGER NOT NULL,metadata TEXT NOT NULL,PRIMARY KEY(trajectory,ordinal));
                CREATE TABLE r16_neutral_terminals(trajectory TEXT NOT NULL,ordinal INTEGER NOT NULL,metadata TEXT NOT NULL,PRIMARY KEY(trajectory,ordinal));
                CREATE TRIGGER r16_natural_first_no_update BEFORE UPDATE ON r16_natural_first BEGIN SELECT RAISE(ABORT,'append only');END;
                CREATE TRIGGER r16_natural_first_no_delete BEFORE DELETE ON r16_natural_first BEGIN SELECT RAISE(ABORT,'append only');END;
                CREATE TRIGGER r16_neutral_intents_no_update BEFORE UPDATE ON r16_neutral_intents BEGIN SELECT RAISE(ABORT,'append only');END;
                CREATE TRIGGER r16_neutral_intents_no_delete BEFORE DELETE ON r16_neutral_intents BEGIN SELECT RAISE(ABORT,'append only');END;
                CREATE TRIGGER r16_neutral_terminals_no_update BEFORE UPDATE ON r16_neutral_terminals BEGIN SELECT RAISE(ABORT,'append only');END;
                CREATE TRIGGER r16_neutral_terminals_no_delete BEFORE DELETE ON r16_neutral_terminals BEGIN SELECT RAISE(ABORT,'append only');END;
            ''')
        driver._r16_natural_point_count=0
        with self.ledger.tx():self.ledger.event('r16-natural-stop-neutral-control','R16_NATURAL_POLICY_INSTALLED',{'policy_sha256':POLICY_SHA,'template_sha256':TEMPLATE_SHA,'trajectories':list(self.tracks),'original_manifest_unchanged':True})

    def _controller(self,t):return self.driver.records[t]['launch'].controller
    def _event(self,t,kind,value):
        with self.ledger.tx():self.ledger.event(t,kind,value)
    def _stop_at_20m(self,t):
        c=self._controller(t);f=self.ledger.frontier(t)
        return f['actual']>=20000000 or any(p.get('point_kind')!='NATURAL_STOP'and p['target_tokens']==20000000 for p in c.points)

    def request_first(self,t,s,*,immediate=False):
        """Insert ONE exact actual-token cut before current regular target.
        stage is NOT advanced here; original resume moves through this extra cut
        to the unchanged original regular target. All reservations must be zero.
        No current 10M/20M point is skipped, relabeled, overwritten or requeued.
        """
        need(t in self.tracks and check_sample(t,s),'NATURAL_REQUEST_IDLE')
        c=self._controller(t)
        with c.lock,self.ledger.tx():
            if t in self.first:return False
            f=self.ledger.frontier(t)
            if (self.driver.failed or c.state!='RUNNING'or f['state']!='RUNNING'
                or f['unresolved']or f['reserved']or f['active_operations']
                or f['actual']>=20000000 or self.ledger.admission_fault(t)):return False
            targets=json.loads(self.ledger.account(t)['targets'])
            need(len(targets)==2 and targets==[10000000,20000000],'NATURAL_PRESERVE_ORIGINAL_REGULAR_TARGETS')
            stage=f['stage'];need(f['actual']<=targets[stage],'NATURAL_NO_BUDGET_OVERRUN')
            meta=metadata(t,f['generation'],f['actual']);updated=list(targets);updated.insert(stage,f['actual'])
            # Account counters, generation and stage are unchanged. Only the
            # explicitly authorized additional cut is inserted in its path.
            self.ledger.db.execute("UPDATE accounts SET targets=?,state='DRAINING' WHERE trajectory=?",(wire(updated).decode(),t))
            request={'natural_stop':meta,'at':utc(),'qualification':'USER_IMMEDIATE_CURRENT_FIVE'if immediate else'CONTINUOUS_IDLE_600S',
                'channel_identity':s['channel_identity'],'queue_metadata':copy.deepcopy(s),'original_stage':stage,
                'original_regular_targets':targets,'targets_with_natural_cut':updated,'original_manifest_unchanged':True,
                'actual_budget_tokens':f['actual'],'measured_search_tokens':f['measured_actual'],
                'unknown_reservation_charge':f['unknown_reservation_charge'],'effective_reservations':f['reserved']}
            self.ledger.db.execute('INSERT INTO r16_natural_first VALUES(?,?)',(t,wire(request).decode()))
            self.ledger.event(t,'ADMISSION_CLOSED',{'reason':'NATURAL_STOP','generation':f['generation'],'policy_sha256':POLICY_SHA})
            self.ledger.event(t,'R16_FIRST_NATURAL_STOP_RECORDED',request)
            c._r16_natural_stop=copy.deepcopy(meta);self.first[t]=request
            self.driver._r16_natural_point_count+=1
        c.gate.notify();return True

    def _completed_snapshot(self,t):
        if t not in self.first:return None
        c=self._controller(t)
        with c.lock:
            meta=self.first[t]['natural_stop']
            points=[p for p in c.points if p.get('point_kind')=='NATURAL_STOP'and p.get('natural_stop')==meta]
            need(len(points)<=1,'NATURAL_FIRST_POINT_ONLY')
            if not points:return None
            point=points[0]
            # Backend must be thawed before Mattermost POST. Waiting here does
            # not hold c.lock across HTTP or block independent K3 dispatch.
            if c.state!='RUNNING'or self.ledger.frontier(t)['generation']<=meta['generation']:return None
            if 'snapshot'not in self.first[t]:
                self.first[t]['snapshot']=copy.deepcopy(point['snapshot'])
                self.first[t]['jobs']=list(point['jobs'])
                self._event(t,'R16_NATURAL_SNAPSHOT_AND_K3_QUEUED',{'natural_stop':meta,'snapshot':point['snapshot'],'jobs':point['jobs'],'report_label':'自然停止点 @ 实际 token'})
            return self.first[t]['snapshot']

    def send(self,t,s):
        need(check_sample(t,s),'NATURAL_SEND_IDLE')
        snapshot=self._completed_snapshot(t)
        if snapshot is None or self._stop_at_20m(t):return False
        c=self._controller(t)
        with c.lock,self.ledger.tx():
            f=self.ledger.frontier(t)
            if self.driver.failed or c.state!='RUNNING'or f['state']!='RUNNING'or f['unresolved']or f['reserved']or f['active_operations']:return False
            need(s['channel_identity']==self.first[t]['channel_identity'],'NATURAL_CHANNEL_CHANGED')
            remaining=max(0,20000000-f['actual']-f['reserved'])
            if not remaining:return False
            ordinal=self.posts[t]+1;intent_id='r16-neutral-'+digest({'trajectory':t,'ordinal':ordinal,'policy':POLICY_SHA})
            text=TEMPLATE.format(remaining=remaining)
            intent={'trajectory':t,'ordinal':ordinal,'intent_id':intent_id,'intent_time':utc(),'channel_identity':s['channel_identity'],
                'remaining_tokens':remaining,'policy_sha256':POLICY_SHA,'template_sha256':TEMPLATE_SHA,
                'rendered_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'natural_snapshot_reference':snapshot,
                'no_auto_retry':True}
            self.ledger.db.execute('INSERT INTO r16_neutral_intents VALUES(?,?,?)',(t,ordinal,wire(intent).decode()))
            self.ledger.event(t,'R16_NEUTRAL_MESSAGE_INTENT',intent);self.posts[t]=ordinal
        # Intent is durably exclusive BEFORE any post. Even exceptions/reply
        # loss cannot cause this ordinal or input to be retried automatically.
        sent_at=utc()
        try:
            result=self.ports.post_neutral(t,text,intent_id)
            need(type(result)is dict and result.get('trajectory')==t and result.get('intent_id')==intent_id
                 and result.get('channel_identity')==s['channel_identity'] and result.get('terminal')in('DELIVERED','REJECTED','UNKNOWN'),
                 'NATURAL_POST_TERMINAL_SCHEMA')
            status=result.get('http_status');need(status is None or type(status)is int and 100<=status<=599,'NATURAL_POST_HTTP_STATUS')
            # Do NOT persist arbitrary trusted-host dictionary fields/body.
            terminal={**intent,'send_time':sent_at,'terminal_time':utc(),'terminal':result['terminal'],'http_status':status}
        except BaseException as e:
            terminal={**intent,'send_time':sent_at,'terminal_time':utc(),'terminal':'UNKNOWN','http_status':None,
                      'fixed_failure_code':'NATURAL_POST_UNKNOWN_NO_RETRY','exception_type':type(e).__name__}
        with self.ledger.tx():
            self.ledger.db.execute('INSERT INTO r16_neutral_terminals VALUES(?,?,?)',(t,ordinal,wire(terminal).decode()))
            self.ledger.event(t,'R16_NEUTRAL_MESSAGE_TERMINAL',terminal)
        self.outcomes[t][terminal['terminal']]+=1
        self.idle[t]={'seq':s['activity_seq'],'since':self.clock()};return True

    def poll_one(self,t):
        # New-root canary: never sample a track before its original task is posted.
        record=self.driver.records.get(t)
        if record is None or record.get('phase')!='ORIGINAL_TASK_RELEASED':return
        if self.driver.failed or self._stop_at_20m(t):return
        # Never spawn metadata SQL into a frozen/parking backend. A native cut
        # suspends idle observation; first post waits for original release.
        c=self._controller(t)
        if c.state!='RUNNING'or self.ledger.frontier(t)['state']!='RUNNING':
            self.idle.pop(t,None);return
        try:
            s=self.ports.poll_native_idle(t);idle=check_sample(t,s)
        except BaseException as e:
            self.idle.pop(t,None)
            code=type(e).__name__
            if self.last_errors.get(t)!=code:
                self._event(t,'R16_NATURAL_IDLE_METADATA_UNAVAILABLE',{'exception_type':code,'no_private_error_message':True})
                self.last_errors[t]=code
            return
        self.last_errors.pop(t,None);now=self.clock()
        if not idle:self.idle.pop(t,None);return
        previous=self.idle.get(t)
        if previous is None or previous['seq']!=s['activity_seq']:
            previous={'seq':s['activity_seq'],'since':now};self.idle[t]=previous
        elapsed=now-previous['since'];need(elapsed>=0,'NATURAL_MONOTONIC_CLOCK')
        if t not in self.first:
            immediate=self.tracks[t]['immediate_first_natural_stop']
            if immediate or elapsed>=600:self.request_first(t,s,immediate=immediate)
        if t in self.first and (self.posts[t]==0 or elapsed>=600):self.send(t,s)

    def poll(self):
        with self.lock:
            for t in self.tracks:self.poll_one(t)
            self._status_snapshot={'policy_sha256':POLICY_SHA,'first_natural_points':len(self.first),
                'message_attempts':dict(self.posts),'message_terminals':copy.deepcopy(self.outcomes),'first':copy.deepcopy(self.first),
                'metadata_unavailable':dict(self.last_errors)}
        return self.status()
    def status(self):
        # Atomically published immutable metadata, no controller/monitor locks.
        return {**copy.deepcopy(self._status_snapshot),'thread_alive':self.thread is not None and self.thread.is_alive()}
    def start(self):
        need(self.thread is None,'NATURAL_MONITOR_START_ONCE')
        def run():
            try:
                while not self.stop.is_set()and not self.driver.finished:
                    self.poll();self.stop.wait(10)
            except BaseException as e:
                # No automatic retry of started scientific/post side effects.
                self._event('r16-natural-stop-neutral-control','R16_NATURAL_MONITOR_FAILED_RETAIN_NO_RETRY',{'exception_type':type(e).__name__})
                self.last_errors['monitor']=type(e).__name__
        self.thread=threading.Thread(target=run,name='r16-natural-stop-neutral-metadata',daemon=True);self.thread.start()
        return self.status()

