"""Fresh native child authorization under both real supervisor owner locks.

This is not a synthetic receipt factory: every call checks current supervisor,
flock descriptor/path/custody, exact live queue claim and original child identity.
"""
from pathlib import Path
import fcntl,os,json
from common import need,Refused
from final_queue import process_identity
class FinalAuthority:
    def __init__(self,ledger,queue,job_id,claim,child):
        self.ledger=ledger;self.queue=queue;self.job_id=job_id;self.claim=claim;self.child=child;self.supervisor=process_identity(os.getpid());self.child_identity=process_identity(child.pid)
        self.locks=[(ledger.home/'owner.lock',ledger.fd),(queue.home/'owner.lock',queue.fd)];self.lock_inodes=[(p.stat().st_dev,p.stat().st_ino)for p,_ in self.locks]
    def __call__(self):
        need(process_identity(os.getpid())==self.supervisor,'FINAL_AUTHORITY_SUPERVISOR_CHANGED')
        for (p,fd),expected in zip(self.locks,self.lock_inodes):
            s=p.lstat();f=os.fstat(fd);need((s.st_dev,s.st_ino)==(f.st_dev,f.st_ino)==expected and not p.is_symlink(),'FINAL_AUTHORITY_LOCK_INODE')
            probe=os.open(p,os.O_RDWR|os.O_NOFOLLOW)
            try:
                try:fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:pass
                else:fcntl.flock(probe,fcntl.LOCK_UN);raise Refused('FINAL_AUTHORITY_LOCK_NOT_HELD')
            finally:os.close(probe)
        with self.queue.mutex:
            job=self.queue._job(self.job_id);need(job['state']=='RUNNING'and job['claim']==self.claim and json.loads(job['child'])==self.child_identity,'FINAL_AUTHORITY_QUEUE_CLAIM')
        need(self.child.poll()is None and process_identity(self.child.pid)==self.child_identity,'FINAL_AUTHORITY_CHILD_TERMINAL_OR_CHANGED')
        return True
