"""Host-only original-gate pause clock -> fixed readonly native router file.

Cumulative monotonic time suspends only a real unadmitted budget-cut wait, not
ordinary model/tool silence or shared capacity congestion. No model/ACP content,
IDs, credential, client-authored pause boolean or network endpoint is exposed.
Not a service freeze, TOOL terminal proof or an automatic stage release.
"""
from pathlib import Path
import copy,os,stat,threading,uuid
from admission_gate import AdmissionGate
from bridge import process_identity
from common import need,digest,sha,wire,private_dir,sync_dir

SCHEMA='agensh-native-budget-pause-v1'
BINDING='agensh-native-budget-pause-binding-v1'
VALID_FOR_NS=10_000_000_000

class NativeBudgetParkProjection:
    def __init__(self,gate,trajectory,directory):
        need(type(gate)is AdmissionGate,'BUDGET_PARK_ORIGINAL_GATE_REQUIRED')
        self.gate=gate;self.ledger=gate.ledger;self.t=trajectory
        self.directory=private_dir(directory,create=True)
        need(not any(self.directory.iterdir()),'BUDGET_PARK_NEW_PROJECTION_ROOT')
        with self.ledger.mutex:
            f=self.ledger.frontier(trajectory)
            need(f['state']=='RUNNING' and f['generation']==1
                 and self.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=?',(trajectory,)).fetchone()[0]==0,
                 'BUDGET_PARK_FIRST_START_BEFORE_MODEL')
            account=self.ledger.account(trajectory)
            import json
            self.roles=json.loads(account['roles']);manifest=account['manifest_sha']
        self.owner=process_identity(os.getpid());self.bindings={}
        st=self.directory.lstat();self.directory_identity=(st.st_dev,st.st_ino)
        self.stop_event=threading.Event();self.thread=None
        self.sequence=0;self.closed=False;self.lock=threading.RLock()
        for role in self.roles:
            self.bindings[role]={'schema':BINDING,'trajectory':trajectory,'role':role,
                                 'manifest_sha256':manifest,'owner':self.owner}
        # Bind mount this public metadata leaf directory read-only into router.
        # Private host ancestor and all credential/HOME/workspace modes untouched.
        os.chmod(self.directory,0o755)
        self.sample()
    def metadata(self,role):
        need(role in self.bindings,'BUDGET_PARK_REGISTERED_ROLE')
        return {'binding':copy.deepcopy(self.bindings[role]),'binding_sha256':digest(self.bindings[role]),
                'status_file':str(self.directory/(role+'.json'))}
    def _current(self):
        need(not self.closed and process_identity(os.getpid())==self.owner,
             'BUDGET_PARK_ORIGINAL_LIVE_OWNER')
        st=self.directory.lstat()
        need(self.directory.resolve()==self.directory and stat.S_ISDIR(st.st_mode)
             and st.st_uid==os.geteuid() and not st.st_mode&0o022
             and (st.st_dev,st.st_ino)==self.directory_identity,
             'BUDGET_PARK_TRUSTED_PROJECTION_DIRECTORY')
        need(not self.ledger.admission_fault(self.t),'BUDGET_PARK_SHARED_FAULT')
    def sample(self):
        with self.lock:
            self._current();self.sequence+=1
            for role in self.roles:
                value=self.gate.budget_pause(self.t,role)
                status={'schema':SCHEMA,'binding_sha256':digest(self.bindings[role]),
                        'sequence':self.sequence,'generation':value['generation'],
                        'sampled_at_mono_ns':str(value['sampled_ns']),
                        'valid_for_ns':str(VALID_FOR_NS),'total_paused_ns':str(value['total_ns']),
                        'paused':value['paused']}
                raw=wire(status);dest=self.directory/(role+'.json')
                temp=self.directory/('.'+uuid.uuid4().hex+'.partial')
                fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                try:
                    with os.fdopen(fd,'wb',closefd=False)as f:f.write(raw);f.flush();os.fchmod(fd,0o444);os.fsync(fd)
                    if dest.exists():
                        st=dest.lstat();need(stat.S_ISREG(st.st_mode)and st.st_uid==os.geteuid()
                                            and st.st_nlink==1 and stat.S_IMODE(st.st_mode)==0o444,'BUDGET_PARK_PROJECTION_REPLACED')
                        os.replace(temp,dest)
                    else:os.link(temp,dest,follow_symlinks=False)
                    sync_dir(self.directory)
                finally:
                    os.close(fd)
                    if temp.exists():temp.unlink()
                need(len(raw)<=4096,'BUDGET_PARK_METADATA_BOUND')
    def start(self):
        with self.lock:
            self._current();need(self.thread is None,'BUDGET_PARK_ONE_ORIGINAL_PUBLISHER')
            def run():
                while not self.stop_event.wait(.5):
                    try:self.sample()
                    except BaseException:
                        self.ledger.latch_fault(self.t,'NATIVE_BUDGET_PARK_PROJECTION_FAILED')
                        return
            self.thread=threading.Thread(target=run,name='native-budget-park-clock',daemon=False)
            self.thread.start()
    def close(self):
        # Retain last immutable observation. Expiry means custody unknown to the
        # consumer, never permission to close/reconnect/replay original ACP.
        with self.lock:self.closed=True;self.stop_event.set();thread=self.thread
        if thread is not None and thread is not threading.current_thread():thread.join()
