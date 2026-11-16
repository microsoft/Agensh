"""Independent AUX_FINALIZATION K3 queue, not a search/retry controller.

One owner; at most twelve claimed/running/unknown children across all six tracks
and both cuts. Reopening an interrupted claim preserves custody and never creates
replacement work. Native execution/model/evaluator ports are a separate binding.
No worker/shared snapshot path is writable through this queue.
"""
from pathlib import Path
from contextlib import contextmanager
import fcntl,json,os,sqlite3,threading,time,uuid
from common import need,integer,sha,wire,digest,private_dir,Refused
from v21_inputs import verify_input
import final_attempts as attempts

ACTIVE=('CLAIMED','RUNNING','CHILD_EXITED_HOLD','CUSTODY_UNKNOWN')

def process_identity(pid):
    integer(pid,'FINAL_CHILD_PID',1)
    text=Path('/proc',str(pid),'stat').read_text();fields=text[text.rfind(')')+2:].split()
    need(fields[0]not in ('Z','X'),'FINAL_CHILD_NOT_EXECUTING')
    return {'pid':pid,'start':fields[19],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'ppid':int(fields[1])}

class FinalQueue:
    def __init__(self,home,*,manifest_sha256,global_cap=12):
        need(type(global_cap)is int and 1<=global_cap<=12,'FINAL_GLOBAL_CAP')
        self.home=private_dir(home,create=True);self.manifest=sha(manifest_sha256);self.cap=global_cap;self.mutex=threading.RLock()
        self.fd=os.open(self.home/'owner.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:os.close(self.fd);raise Refused('FINAL_QUEUE_ALREADY_OWNED')from None
        self.db=None
        try:
            need(not(self.home/'queue.sqlite').is_symlink(),'FINAL_QUEUE_DATABASE_SYMLINK')
            self.db=sqlite3.connect(self.home/'queue.sqlite',check_same_thread=False,isolation_level=None);self.db.row_factory=sqlite3.Row
            os.chmod(self.home/'queue.sqlite',0o600);self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA foreign_keys=ON')
            self.db.executescript('''CREATE TABLE IF NOT EXISTS config(singleton INTEGER PRIMARY KEY CHECK(singleton=1),manifest TEXT NOT NULL,cap INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS points(point TEXT PRIMARY KEY,trajectory TEXT NOT NULL,setting TEXT NOT NULL,target INTEGER NOT NULL,input_root TEXT NOT NULL,input_policy TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,point TEXT NOT NULL REFERENCES points,replicate INTEGER NOT NULL,state TEXT NOT NULL,claim TEXT,child TEXT,terminal TEXT,result TEXT,UNIQUE(point,replicate));
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,at_ns INTEGER NOT NULL,kind TEXT NOT NULL,metadata TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS no_update_event BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
            CREATE TRIGGER IF NOT EXISTS no_delete_event BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;''')
            attempts.initialize(self)
            with self.tx():
                old=self.db.execute('SELECT * FROM config').fetchone()
                if old is None:self.db.execute('INSERT INTO config VALUES(1,?,?)',(self.manifest,self.cap))
                else:need((old['manifest'],old['cap'])==(self.manifest,self.cap),'FINAL_QUEUE_CONFIG_CHANGED')
                for row in [r for r in attempts.all_rows(self) if r['state'] in ('CLAIMED','RUNNING')]:
                    self.db.execute("UPDATE "+attempts.table(self,row['id'])+" SET state='CUSTODY_UNKNOWN' WHERE id=?",(row['id'],));self.event('OWNER_REOPEN_NO_REPLAY',dict(job_id=row['id'],prior_state=row['state']))
        except BaseException:
            if self.db is not None:self.db.close()
            os.close(self.fd);raise
    @contextmanager
    def tx(self):
        with self.mutex:
            self.db.execute('BEGIN IMMEDIATE')
            try:yield;self.db.execute('COMMIT')
            except BaseException:self.db.execute('ROLLBACK');raise
    def event(self,kind,metadata):self.db.execute('INSERT INTO events(at_ns,kind,metadata)VALUES(?,?,?)',(time.time_ns(),kind,wire(metadata).decode()))
    def enqueue(self,input_root,*,policy_sha256,trajectory,setting):
        root=Path(input_root);need(root.is_absolute()and root.resolve()==root,'FINAL_QUEUE_INPUT_ROOT')
        p=verify_input(root,expected_policy_sha=policy_sha256,trajectory=trajectory,setting=setting)
        need(p['pins']['manifest']==self.manifest,'FINAL_QUEUE_MANIFEST_MISMATCH')
        from r16_natural_contract import natural
        nm=natural(p)
        key={'trajectory':trajectory,'target':p['target_tokens']}
        if nm is not None:key.update(point_kind='NATURAL_STOP',policy_sha256=nm['policy_sha256'])
        point=digest(key)
        row=(point,trajectory,setting,p['target_tokens'],str(root),policy_sha256)
        with self.tx():
            old=self.db.execute('SELECT * FROM points WHERE point=?',(point,)).fetchone()
            if old is not None:
                need(tuple(old)==row,'FINAL_POINT_CANNOT_REPLACE_FROZEN_INPUT')
                return [r[0]for r in self.db.execute('SELECT id FROM jobs WHERE point=? ORDER BY replicate',(point,))]
            self.db.execute('INSERT INTO points VALUES(?,?,?,?,?,?)',row);ids=[]
            for k in (1,2,3):
                job=digest({'point':point,'replicate':k});ids.append(job)
                self.db.execute("INSERT INTO jobs VALUES(?,?,?,'QUEUED',NULL,NULL,NULL,NULL)",(job,point,k))
            self.event('K3_ENQUEUED',{'point':point,'policy_sha256':policy_sha256,'jobs':ids,'billing_domain':'AUX_FINALIZATION'});return ids
    def _job(self,job):
        row=self.db.execute('SELECT jobs.*,points.trajectory,points.setting,points.target,points.input_root,points.input_policy FROM jobs JOIN points ON jobs.point=points.point WHERE jobs.id=?',(job,)).fetchone()
        if row is None:return attempts.replacement_job(self,job)
        return dict(row)
    def claim(self):
        # Full immutable-input verification can be large I/O. It must NOT own
        # queue.mutex: current FINAL authority takes ledger.mutex -> queue.mutex,
        # so the old I/O-sized critical section also blocked metadata state RPCs.
        with self.mutex:job=_claim_candidate(self)
        if job is None:return None
        verify_input(job['input_root'],expected_policy_sha=job['input_policy'],trajectory=job['trajectory'],setting=job['setting'])
        # Verify metadata and ALL capacity/unknown conditions afresh at the
        # actual atomic claim. A competing claim defers UNSENT, never replays.
        with self.tx():
            current=_claim_candidate(self)
            if current is None or current['id']!=job['id']:return None
            need(current==job,'FINAL_CLAIM_INPUT_DESCRIPTOR_CHANGED')
            claim=uuid.uuid4().hex;self.db.execute("UPDATE "+attempts.table(self,job['id'])+" SET state='CLAIMED',claim=? WHERE id=?",(claim,job['id']));self.event('CLAIMED',dict(job_id=job['id'],claim=claim));return self._job(job['id'])
    def attach(self,job_id,claim,child):
        """Trusted launcher passes the original Popen while the child is alive."""
        identity=process_identity(child.pid);need(identity['ppid']==os.getpid(),'FINAL_CHILD_NOT_OWNED')
        with self.tx():
            job=self._job(job_id);need(job['state']=='CLAIMED'and job['claim']==claim,'FINAL_CLAIM_SCOPE')
            self.db.execute("UPDATE "+attempts.table(self,job['id'])+" SET state='RUNNING',child=? WHERE id=?",(wire(identity).decode(),job_id));self.event('CHILD_ATTACHED',dict(job_id=job_id,identity=identity))
    def reap(self,job_id,claim,child):
        """Actual original child wait; absence alone is not terminal evidence."""
        with self.tx():
            job=self._job(job_id);need(job['state']=='RUNNING'and job['claim']==claim,'FINAL_RUNNING_SCOPE')
            recorded=json.loads(job['child']);need(child.pid==recorded['pid'],'FINAL_CHILD_HANDLE_DIFFERENT')
            # Check before poll: waitpid can reap a zombie and a later PID lookup
            # may refer to a reused process. No inference from a foreign PID.
            try:
                text=Path('/proc',str(child.pid),'stat').read_text();f=text[text.rfind(')')+2:].split()
                need(f[19]==recorded['start']and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==recorded['boot_id'],'FINAL_CHILD_IDENTITY_CHANGED')
            except FileNotFoundError:pass # Original Popen wait handle is still required below.
            rc=child.poll()
            if rc is None:return None
            need(type(rc)is int,'FINAL_CHILD_WAIT_REQUIRED');terminal={'identity':recorded,'exit_code':rc if rc>=0 else None,'signal':-rc if rc<0 else None,'wait_observed':True}
            self.db.execute("UPDATE "+attempts.table(self,job['id'])+" SET state='CHILD_EXITED_HOLD',terminal=? WHERE id=?",(wire(terminal).decode(),job_id));self.event('CHILD_TERMINAL',dict(job_id=job_id,**terminal));return terminal
    def complete(self,job_id,claim,*,result_sha256,verified_native_audit):
        """A failure/partial child is not an evaluated K; never automatic retry."""
        sha(result_sha256);need(type(verified_native_audit)is dict,'FINAL_NATIVE_AUDIT_REQUIRED')
        need(verified_native_audit.get('job_id')==job_id and verified_native_audit.get('result_sha256')==result_sha256 and verified_native_audit.get('complete')is True and type(verified_native_audit.get('unresolved_physical_custody'))is int and verified_native_audit['unresolved_physical_custody']==0,'FINAL_NATIVE_AUDIT_REQUIRED')
        with self.tx():
            job=self._job(job_id);need(job['state']=='CHILD_EXITED_HOLD'and job['claim']==claim,'FINAL_TERMINAL_SCOPE');t=json.loads(job['terminal']);need(t['exit_code']==0 and t['signal']is None,'FINAL_CHILD_FAILED_NO_RETRY')
            self.db.execute("UPDATE "+attempts.table(self,job['id'])+" SET state='COMPLETE',result=? WHERE id=?",(result_sha256,job_id));self.event('COMPLETE',dict(job_id=job_id,result_sha256=result_sha256,audit_sha256=digest(verified_native_audit)))
    def frontier(self):
        with self.mutex:return attempts.frontier(self)
    def close(self):
        with self.mutex:self.db.close();os.close(self.fd)


def _claim_candidate(queue):
    """Original guards under queue.mutex; metadata only, never archive I/O."""
    rows=attempts.live_rows(queue)
    need(not any(r['state']=='CUSTODY_UNKNOWN' for r in rows),'FINAL_QUEUE_UNKNOWN_NO_NEW_LAUNCH')
    if sum(r['state'] in ACTIVE for r in rows)>=queue.cap:return None
    blocked=getattr(queue,'_native_final_faulted_trajectories',frozenset())
    return next((r for r in rows if r['state']=='QUEUED' and r['trajectory']not in blocked),None)
