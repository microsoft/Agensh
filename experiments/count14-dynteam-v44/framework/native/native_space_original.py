"""Exact original materialization space functions; bootstrap is separately bound."""
def atomic(path, value):
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with tmp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

@contextlib.contextmanager
def locked(home):
    need(home.is_absolute() and home.resolve()==home,'canonical new materialization root')
    home.mkdir(parents=True,exist_ok=True)
    fd=os.open(home/'mutex.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'r+') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)

def measured_requirement(policy, private_bytes=0):
    need(type(private_bytes) is int and private_bytes>=0,'private opaque byte count')
    rows=policy['roles'].values()
    payload=sum(r['counts']['bytes'] for r in rows)+private_bytes
    members=sum(r['counts']['members'] for r in rows)
    need(type(payload) is int and payload>=0 and type(members) is int and members>=0,'sameCP measured counts')
    return dict(payload_bytes=payload,members=members,
                required_bytes=2*(payload+PER_MEMBER_OVERHEAD*members)+FINALIZER_WRITE_ALLOWANCE)

def free_bytes(path):
    value=os.statvfs(path)
    return value.f_bavail*value.f_frsize

class Reservation:
    def __init__(self,home,key,value):self.home=home;self.key=key;self.value=value
    def close(self, terminal):
        need(terminal in ('MATERIALIZED','RETAINED_PARTIAL'),'explicit retained allocation terminal')
        with locked(self.home):
            path=self.home/(self.key+'.json');current=json.loads(path.read_bytes())
            need(current==self.value,'materialization frontier changed')
            # Files stay on disk. Their allocation is already reflected by the
            # next statvfs, so only the promised future growth is discharged.
            current.update(stage=terminal,promised_bytes=0,closed_at=time.time())
            atomic(path,current);self.value=current

def try_reserve(home, *, job, policy_sha256, measured, free=free_bytes):
    need(type(job) is str and job and type(measured['required_bytes']) is int
         and measured['required_bytes']>0,'independent attempt/requirement')
    key=digest(job);path=home/(key+'.json')
    with locked(home):
        need(not path.exists(),'never replay an existing materialization intent')
        outstanding=0
        for p in home.glob('*.json'):
            need(not p.is_symlink(),'no linked reservation')
            row=json.loads(p.read_bytes());outstanding+=row['promised_bytes']
        available=free(home) # REQUIRED fresh sample inside shared transaction.
        need(type(available) is int and available>=0,'fresh available bytes')
        if available-outstanding-measured['required_bytes']<RESERVE_BYTES:return None
        from pilot_admission import process_identity
        writer=process_identity(os.getpid())
        value=dict(schema='count14-seeds-materialization-v1',manifest_sha256=MANIFEST_SHA256,
            job=job,policy_sha256=policy_sha256,measured=measured,stage='RESERVED',
            promised_bytes=measured['required_bytes'],sample_available_bytes=available,
            prior_promised_bytes=outstanding,reserve_bytes=RESERVE_BYTES,at=time.time(),pid=os.getpid(),writer=writer)
        atomic(path,value)
        return Reservation(home,key,value)
