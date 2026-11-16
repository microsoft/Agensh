"""Bounded cold observer: fresh relay counts never wait for health census.

Only fixed PUBLIC terminal controls are decoded. Index is OUR new scratch
cache, not an experiment ledger. Source receipts/ledgers are never written.
mtime is neither a request timestamp nor a window predicate. Original request
ID is hashed only as public control identity; never hash body/pkl/logs.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import collections,contextlib,datetime,fcntl,hashlib,json,math,os,sqlite3,stat,time
PREFIX='count14-own-resource-dirfd-health-v1'
BASE=Path((_C14_SCRATCH))/PREFIX
STATES=('COMPLETED','UNKNOWN_CHARGED','REJECTED_PREGEN','RETRYABLE_REJECTED')

def ns(value,need):
    d=datetime.datetime.fromisoformat(value);need(d.tzinfo is not None);return int(d.timestamp()*10**9)

def initialize(db):
    db.execute('PRAGMA busy_timeout=100')
    db.execute('CREATE TABLE IF NOT EXISTS terminals(rid TEXT PRIMARY KEY,at_ns INTEGER NOT NULL,state TEXT NOT NULL,http_status INTEGER)')
    db.execute('CREATE INDEX IF NOT EXISTS terminal_time ON terminals(at_ns)')
    db.execute('CREATE TABLE IF NOT EXISTS directories(device INTEGER,root_inode INTEGER,inode INTEGER,rid TEXT NOT NULL,PRIMARY KEY(device,root_inode,inode))')
    db.commit()

def terminal_fd(observer,fd):
    s=os.fstat(fd);observer.need(stat.S_ISREG(s.st_mode)and s.st_size<=65536)
    raw=os.read(fd,65537);e=os.fstat(fd)
    observer.need(len(raw)==s.st_size and(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)==(e.st_dev,e.st_ino,e.st_size,e.st_mtime_ns))
    text=raw.decode('utf-8','strict');v=observer.SelectedJSON(text).select({'completed_at','state'})
    observer.need(v['state']in STATES);at=ns(v['completed_at'],observer.need)
    status=200 if v['state']=='COMPLETED'else observer.SelectedJSON(text).select({'http_status'})['http_status']
    observer.need(status is None or type(status)is int and 100<=status<=599)
    return at,v['state'],status

def scan(observer,roots,path,*,budget=4.,clock=time.monotonic):
    """Fixed-root O_NOFOLLOW dirfd census; at most budget seconds of new work.

    Cached directories skip all source-file reads. Exact same request control
    tuple must agree across original copies. Immutable terminal-v1/v54 ABI is
    the basis for reuse, not mtime or a private-content hash.
    """
    started=clock();processed=hits=0;complete=True
    if not path.exists():
        fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
    observer.canonical(path);s=path.lstat();observer.need(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and not s.st_mode&0o022)
    with contextlib.closing(sqlite3.connect(path,timeout=.1))as db:
        initialize(db)
        known={(d,r,i):rid for d,r,i,rid in db.execute('SELECT device,root_inode,inode,rid FROM directories')}
        for value in roots:
            if clock()-started>=budget:complete=False;break
            root=observer.canonical(value);rfd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:
                rs=os.fstat(rfd)
                with os.scandir(rfd)as entries:
                    for entry in entries:
                        if clock()-started>=budget:complete=False;break
                        # Original request root has only native control IDs;
                        # ignore ordinary files, reject symlink request dirs.
                        if entry.is_symlink():observer.need(False)
                        if not entry.is_dir(follow_symlinks=False):continue
                        observer.need(entry.name.startswith('count14-v4-'))
                        rid=hashlib.sha256(entry.name.encode('utf-8')).hexdigest()
                        key=(rs.st_dev,rs.st_ino,entry.inode())
                        if key in known:observer.need(known[key]==rid);hits+=1;continue
                        qfd=os.open(entry.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=rfd)
                        try:
                            try:tfd=os.open('receipt-terminal.json',os.O_RDONLY|os.O_NOFOLLOW,dir_fd=qfd)
                            except FileNotFoundError:continue # still SENT, not a finished/error request
                            try:row=terminal_fd(observer,tfd)
                            finally:os.close(tfd)
                        finally:os.close(qfd)
                        prior=db.execute('SELECT at_ns,state,http_status FROM terminals WHERE rid=?',(rid,)).fetchone()
                        observer.need(prior is None or prior==row)
                        if prior is None:db.execute('INSERT INTO terminals VALUES(?,?,?,?)',(rid,*row))
                        db.execute('INSERT INTO directories VALUES(?,?,?,?)',(*key,rid));known[key]=rid;processed+=1
                        if processed%128==0:db.commit()
                if not complete:break
            finally:os.close(rfd)
        db.commit()
    return dict(complete=complete,new_terminal_controls=processed,cached_directory_hits=hits,scan_budget_seconds=budget)

def counts(path,now_ns):
    with contextlib.closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.1))as db:
        db.execute('PRAGMA query_only=ON')
        return db.execute("SELECT COUNT(*),COALESCE(SUM(state='UNKNOWN_CHARGED'OR http_status BETWEEN 500 AND 599),0)FROM terminals WHERE at_ns>?AND at_ns<=?",(now_ns-600*10**9,now_ns)).fetchone()

def undefined(now_ns,calls,bad,p95,*,progress=None):
    return dict(schema='count14-own-resource-health-v1',observed_ns=now_ns,gateway_FP8_TTFT_p95_seconds=p95,
        own_window_seconds=600,own_window_covered_seconds=0,own_rate_defined=False,own_requests=calls,own_5xx_or_UNKNOWN_requests=bad,
        own_health_scan_complete=False,own_window_state='UNDEFINED_BOUNDED_INDEX_BOOTSTRAP_NOT_ZERO_PERCENT',index_progress=progress)

def health(observer,roots,directory,pin,now_ns,native_calls,native_bad,system_calls,system_bad,p95,*,budget=4):
    directory.mkdir(mode=0o700,parents=True,exist_ok=True);observer.canonical(directory)
    fd=os.open(directory/'index.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600);path=directory/'PUBLIC_TERMINAL_CONTROL_INDEX.sqlite'
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            # Never block the fresh SYSTEM/own-count producer on health work.
            samples=sorted(directory.glob('HEALTH_COMPLETE_???????????????????.PUBLIC.json'))
            if samples:
                latest=observer.public(samples[-1])
                if 0<=now_ns-latest['observed_ns']<=60*10**9:
                    latest['gateway_FP8_TTFT_p95_seconds']=p95;latest['reused_original_recent_health_snapshot_not_restamped']=True;return latest
            return undefined(now_ns,native_calls+system_calls,native_bad+system_bad,p95)
        progress=scan(observer,roots,path,budget=budget)
        calls,bad=counts(path,now_ns);calls+=native_calls+system_calls;bad+=native_bad+system_bad
        observer.need(0<=bad<=calls)
        if not progress['complete']:return undefined(now_ns,calls,bad,p95,progress=progress)
        window=directory/'window';window.mkdir(mode=0o700,exist_ok=True)
        w=observer.window(window,now_ns,calls,bad,pin)
        value=dict(schema='count14-own-resource-health-v1',observed_ns=now_ns,gateway_FP8_TTFT_p95_seconds=p95,
            **w,own_health_scan_complete=True,index_progress=progress)
        observer.append(directory/f'HEALTH_COMPLETE_{now_ns:019d}.PUBLIC.json',value);return value
    finally:os.close(fd)

def collect(observer,*,registered=None,directory=BASE,budget=4):
    with observer.deadline(25):
        if registered is None:
            observer.need(os.geteuid()==0 and os.uname().nodename==(_C14_HOSTNAME)and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==observer.BOOT)
            observer.canonical(observer.BASE);observer.need(os.path.ismount(observer.BASE)and observer.BASE.stat().st_dev!=Path('/').stat().st_dev)
            value,pin=observer.inventory()
        else:value,pin=registered # explicit OWN fixture only; not exposed as CLI
        started=time.time_ns();rows=[];calls=bad=0;seen=set()
        # NO old observer.lock. Physical counts are fresh regardless of index.
        for p in value['native_ledgers']:
            n=observer.native(p,now_ns=started);key=(n['device'],n['inode']);observer.need(key not in seen);seen.add(key)
            rows.append(dict(root=str(Path(p).parent.parent),FP8_inflight=n['inflight'],raw_relay_pending=n['raw'],explicit_closed502_slots_excluded=n['explicit_closed502_slots_only']))
            if p not in value.get('health_excluded_native_ledgers',[]):calls+=n['terminals'];bad+=n['errors']
        books,roots=observer.scale_sources(value)
        for p in books:
            s=observer.canonical(p).stat();key=(s.st_dev,s.st_ino);observer.need(key not in seen);seen.add(key)
            rows.append(dict(root=str(Path(p).parent),FP8_inflight=observer.reservation(p)))
        retained=observer.canonical(value['scale_physical_unknown_root']);number=0
        for p in retained.glob('*.json'):
            s=p.lstat();observer.need(p.resolve()==p and stat.S_ISREG(s.st_mode));number+=1
        rows.append(dict(root=str(retained),FP8_inflight=number,retained_UNKNOWN_relay_receipts=True))
        number,system_calls,system_bad=observer.system(value['system_health'],value['system_root'],now_ns=started)
        rows.append(dict(root=value['system_root'],FP8_inflight=number))
        p95=observer.ttft();h=health(observer,roots,directory/pin[:20],pin,started,calls,bad,system_calls,system_bad,p95,budget=budget)
        own=dict(schema='count14-own-fp8-relay-counts-v1',observed_ns=started,all_count14_roots_included=True,counts_from_relay_ledgers=True,
            roots=rows,total_FP8_inflight=sum(r['FP8_inflight']for r in rows),inventory_sha256=pin,SAMPLE_NONATOMIC_CONSERVATIVE=True,health_census_does_not_hold_fresh_counts=True)
        return own,h

def install(observer):
    observer.need(not getattr(observer,'_count14_dirfd_health_index_v1',False))
    observer.collect=lambda:collect(observer)
    observer._count14_dirfd_health_index_v1=True
