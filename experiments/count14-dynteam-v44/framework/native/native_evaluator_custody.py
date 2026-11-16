"""Metadata-only physical custody around the unchanged official Docker runner.

Durable ALLOCATING precedes containers.create. A failed/ambiguous create never
becomes zero scopes merely because no ID was returned. Only the original
runner's successful force-remove acknowledgement closes a known container.
No task/image/command/path/output/error-message contents enter this journal;
no daemon-wide scans, additional timeout, cleanup, retry or kill is introduced.
"""
from pathlib import Path
import os,re,sqlite3,threading,time,uuid
from common import need,private_dir,digest
from final_host_rpc import ControlFailure

def require(value,code):
    if not value:raise ControlFailure(code)

class EvaluatorCustody:
    def __init__(self,home):
        self.home=private_dir(home,create=True);self.path=self.home/'custody.sqlite';self.lock=threading.RLock()
        # Fresh independent child only. Retained databases are evidence, not a
        # recovery/replay API; a parent must audit the original container scope.
        fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
        self.db=sqlite3.connect(self.path,check_same_thread=False,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE scopes(scope TEXT PRIMARY KEY,state TEXT NOT NULL,container_id TEXT,wait_exit INTEGER,created_ns INTEGER NOT NULL,removed_ns INTEGER)')
        self.db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,scope TEXT NOT NULL,kind TEXT NOT NULL,at_ns INTEGER NOT NULL,error_type TEXT)')
        self.wrapped=False
    def _event(self,scope,kind,error_type=None):
        self.db.execute('INSERT INTO events(scope,kind,at_ns,error_type) VALUES(?,?,?,?)',(scope,kind,time.time_ns(),error_type))
    def allocate(self):
        with self.lock:
            scope=uuid.uuid4().hex
            try:
                self.db.execute('BEGIN IMMEDIATE');self.db.execute('INSERT INTO scopes VALUES(?,?,NULL,NULL,?,NULL)',(scope,'ALLOCATING',time.time_ns()));self._event(scope,'CREATE_DISPATCH');self.db.execute('COMMIT')
            except BaseException:
                if self.db.in_transaction:self.db.execute('ROLLBACK')
                raise ControlFailure('EVALUATOR_CUSTODY_CREATE_JOURNAL')from None
            return scope
    def created(self,scope,identifier):
        require(type(identifier)is str and re.fullmatch('[0-9a-f]{64}',identifier)is not None,'EVALUATOR_EXACT_CONTAINER_ID_REQUIRED')
        self._transition(scope,'ALLOCATING','KNOWN',container_id=identifier,kind='CREATE_RETURNED_ID')
    def _transition(self,scope,before,after,*,kind,container_id=None,exit_code=None):
        with self.lock:
            try:
                self.db.execute('BEGIN IMMEDIATE');row=self.db.execute('SELECT state,container_id FROM scopes WHERE scope=?',(scope,)).fetchone();require(row is not None and row[0]==before,'EVALUATOR_CUSTODY_STATE')
                self.db.execute('UPDATE scopes SET state=?,container_id=COALESCE(?,container_id),wait_exit=COALESCE(?,wait_exit),removed_ns=CASE WHEN ?=\'REMOVED\' THEN ? ELSE removed_ns END WHERE scope=?',(after,container_id,exit_code,after,time.time_ns(),scope));self._event(scope,kind);self.db.execute('COMMIT')
            except ControlFailure:
                if self.db.in_transaction:self.db.execute('ROLLBACK')
                raise
            except BaseException:
                if self.db.in_transaction:self.db.execute('ROLLBACK')
                raise ControlFailure('EVALUATOR_CUSTODY_STATE_JOURNAL')from None
    def error(self,scope,kind,error):
        with self.lock:
            name=type(error).__name__;require(re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,159}',name)is not None,'EVALUATOR_EXCEPTION_TYPE')
            try:self._event(scope,kind,name)
            except BaseException:raise ControlFailure('EVALUATOR_CUSTODY_ERROR_JOURNAL')from None
    def waited(self,scope,result):
        require(type(result)is dict and type(result.get('StatusCode'))is int,'EVALUATOR_WAIT_STATUS')
        self._transition(scope,'KNOWN','KNOWN',kind='WAIT_RETURNED_EXIT',exit_code=result['StatusCode'])
    def removed(self,scope):self._transition(scope,'KNOWN','REMOVED',kind='ORIGINAL_FORCE_REMOVE_ACKNOWLEDGED')
    def frontier(self):
        with self.lock:
            rows=self.db.execute('SELECT scope,state,container_id,wait_exit FROM scopes ORDER BY scope').fetchall();events=self.db.execute('SELECT scope,kind,at_ns,error_type FROM events ORDER BY seq').fetchall()
            return {'schema':'count14-agensh-evaluator-custody-frontier-v1','scopes':len(rows),'unresolved':sum(r[1]!='REMOVED'for r in rows),'physical_terminal':all(r[1]=='REMOVED'for r in rows),'metadata_sha256':digest({'scopes':rows,'events':events})}
    def wrap(self,runner):
        require(not self.wrapped and 'docker'in runner.__globals__,'EVALUATOR_CUSTODY_WRAP_ONCE')
        self.wrapped=True;runner.__globals__['docker']=CustodyDocker(runner.__globals__['docker'],self);return runner
    def close(self):self.db.close()

class CustodyDocker:
    def __init__(self,inner,custody):self.inner=inner;self.custody=custody
    def from_env(self,*args,**kwargs):return CustodyClient(self.inner.from_env(*args,**kwargs),self.custody)
class CustodyClient:
    def __init__(self,inner,custody):self.inner=inner;self.containers=CustodyContainers(inner.containers,custody)
    def __getattr__(self,name):return getattr(self.inner,name)
class CustodyContainers:
    def __init__(self,inner,custody):self.inner=inner;self.custody=custody
    def create(self,**kwargs):
        scope=self.custody.allocate()
        try:container=self.inner.create(**kwargs)
        except BaseException as error:self.custody.error(scope,'CREATE_EXCEPTION_CUSTODY_UNKNOWN',error);raise
        self.custody.created(scope,container.id);return CustodyContainer(container,self.custody,scope)
class CustodyContainer:
    def __init__(self,inner,custody,scope):self.inner=inner;self.custody=custody;self.scope=scope
    def __getattr__(self,name):return getattr(self.inner,name)
    def start(self,*args,**kwargs):return self.inner.start(*args,**kwargs)
    def logs(self,*args,**kwargs):return self.inner.logs(*args,**kwargs)
    def wait(self,*args,**kwargs):
        try:result=self.inner.wait(*args,**kwargs)
        except BaseException as error:self.custody.error(self.scope,'WAIT_EXCEPTION',error);raise
        self.custody.waited(self.scope,result);return result
    def remove(self,*args,**kwargs):
        require(args==()and kwargs=={'force':True},'EVALUATOR_ORIGINAL_FORCE_REMOVE_REQUIRED')
        try:result=self.inner.remove(*args,**kwargs)
        except BaseException as error:self.custody.error(self.scope,'REMOVE_EXCEPTION_CUSTODY_UNKNOWN',error);raise
        self.custody.removed(self.scope);return result
