"""Approved exact18 retired-health-window scan seam, new private modules only.

No collector count/root enumeration/health/window/TTFT/validator is changed.
A separate frozen real lifecycle reader MUST supply fresh original controls;
its production binding is not supplied or certified by this component.
"""
from pathlib import Path
from types import ModuleType,FunctionType
import ast,copy,datetime,hashlib,inspect,json,os,stat,time

PLAN_PIN='7b754107d928b8e8597ad0c4171707127921fb4216847eb34a65f5bce29d0e69'
V10_PIN='f1b2e735627cda814a6efad738da5da0562e24d520bd7eb4780015bd0536c2fd'
SCAN_SOURCE_PIN='3f55fbcdfb0d2beb13e56010a730151e786b61fec7e0c042358a506f1d255888'

def need(ok,code):
    if not ok:raise ValueError(code)

def stamp(s):
    return (s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def public_identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,uid=s.st_uid,gid=s.st_gid,mode=stat.S_IMODE(s.st_mode))

def canonical(path,directory=False):
    p=Path(path);s=p.lstat()
    need(p.is_absolute() and p.resolve()==p and not p.is_symlink() and
         (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)),
         'RETIRED_EXACT_CANONICAL_DIRECTORY_OR_REGULAR')
    return p,s

def utc_ns(value):
    d=datetime.datetime.fromisoformat(value)
    need(d.tzinfo is not None,'RETIRED_ORIGINAL_AWARE_CONTROL_TIME')
    delta=d.astimezone(datetime.timezone.utc)-datetime.datetime(1970,1,1,tzinfo=datetime.timezone.utc)
    return (delta.days*86400+delta.seconds)*10**9+delta.microseconds*1000

class RetiredRoots:
    def __init__(self,plan_raw,*,new_arm_root,registered_roots,registered_books,
                 original_observer,fresh_lifecycle_reader,lifecycle_source_sha256,
                 qualification_only=False,OWN_path_mapping=None):
        need(hashlib.sha256(plan_raw).hexdigest()==PLAN_PIN,'RETIRED_EXACT_APPROVED_PLAN')
        plan=json.loads(plan_raw);rows=plan['exact_whitelist']
        need(len(rows)==18 and len({r['exact_registered_request_root']for r in rows})==18,
             'RETIRED_EXACT18_NOT_ANCESTOR_WHITELIST')
        self.arm,_=canonical(new_arm_root,directory=True)
        need(callable(fresh_lifecycle_reader) and len(lifecycle_source_sha256)==64 and
             hashlib.sha256(inspect.getsource(fresh_lifecycle_reader).encode()).hexdigest()==lifecycle_source_sha256,
             'RETIRED_REQUIRES_REVIEWED_FROZEN_LIFECYCLE_READER_NOT_RECEIPT_BOOL')
        self.lifecycle=fresh_lifecycle_reader;self.lifecycle_pin=lifecycle_source_sha256
        self.observer=original_observer;self.rows={};self.retired={};self.present={};self.cache=None
        mapping=OWN_path_mapping or {}
        if qualification_only:
            need(set(mapping)=={r['exact_registered_request_root']for r in rows} and
                 all(any(x.startswith('OWN-')for x in Path(p).parts)for p in [self.arm,*mapping.values()]),
                 'RETIRED_ONLY_EXPLICIT_OWN_PATH_PORT')
        else:need(not mapping,'RETIRED_NO_PRODUCTION_PATH_PROJECTION')
        for r in rows:
            root=Path(mapping.get(r['exact_registered_request_root'],r['exact_registered_request_root']))
            need(str(root) in registered_roots and str(root.parent/'ledger.json.reservations-v52.json')in registered_books,
                 'RETIRED_ROOT_AND_BOOK_STAY_IN_ORIGINAL_REGISTRY')
            term=r['actual_rm_terminal'];started=r['actual_rm_started'];node=r['original_removed_node']
            p=r['exact_registered_request_root']
            need(r['approved_cleanup_plan_sha256']==V10_PIN and len(r['original_approval_entry_sha256'])==64 and
                 node['path']==started['path']==term['path']==p and node['kind']=='dir' and
                 type(node['dev'])is int and type(node['ino'])is int and
                 started['event']=='RM_STARTED' and started['genuine_parent_Popen']is True and
                 type(started['start_ticks'])is int and started['start_ticks']>0 and
                 started['pid']==term['child_pid'] and started['boot_id'] and
                 term['event']=='RM_TERMINAL' and term['code']=='RM_EXITED' and
                 type(term['exit_code'])is int and term['exit_code']==0 and
                 term['status']=='COMPLETE' and term['removed']is True and
                 term['remaining_node']is None and term['no_automatic_retry']is True,
                 'RETIRED_ORIGINAL_APPROVED_ACTUAL_REMOVAL_NOT_NEVER_RAN')
            at=utc_ns(term['at']);need(utc_ns(started['at'])<=at,'RETIRED_ORIGINAL_START_PRECEDES_TERMINAL')
            self.rows[str(root)]=dict(original_root=p,terminal_ns=at)
        self.proof=dict(exact18=True,registry_roots_removed=0,books_or_UNKNOWN_counts_changed=False,
                        actual_lifecycle_binding_qualified=False)

    def begin(self,index_path):
        p=Path(index_path);self.cache,s=canonical(p.parent,directory=True)
        need(self.cache.is_relative_to(self.arm) and self.cache!=self.arm and s.st_uid in (0,os.geteuid()) and
             not stat.S_IMODE(s.st_mode)&0o022,'RETIRED_LIFECYCLE_CACHE_ONLY_OWN_PRIVATE_ROOT')
        self.retired={};self.present={}

    def marker(self,root):
        return self.cache/('RETIRED_ROOT_SEEN_PRESENT_'+hashlib.sha256(str(root).encode()).hexdigest()+'.PUBLIC.json')

    def _seen(self,root):
        p=self.marker(root)
        try:p.lstat()
        except FileNotFoundError:return False
        _,s=canonical(p)
        need(s.st_uid in (0,os.geteuid()) and stat.S_IMODE(s.st_mode)==0o444 and s.st_nlink==1 and s.st_size<4096,
             'RETIRED_OWN_PERSISTENT_PRESENT_MARKER_IDENTITY')
        value=self.observer.public(p)
        need(value.get('schema')=='count14-exact18-root-observed-present-v1' and value.get('root')==str(root),
             'RETIRED_NO_OLD_TOMBSTONE_AFTER_PRESENT')
        return True

    def mark_present(self,root,fd):
        root=Path(root)
        if str(root)not in self.rows:return
        try:
            p,s=canonical(root,directory=True);opened=os.fstat(fd)
            need((s.st_dev,s.st_ino)==(opened.st_dev,opened.st_ino),'RETIRED_OPENED_PRESENT_SAME_ROOT')
            self.present[str(root)]=(s.st_dev,s.st_ino)
            if not self._seen(root):
                value=dict(schema='count14-exact18-root-observed-present-v1',root=str(root),device=s.st_dev,inode=s.st_ino)
                raw=(json.dumps(value,sort_keys=True)+'\n').encode()
                out=os.open(self.marker(root),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
                with os.fdopen(out,'wb')as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
                directory_fd=os.open(self.cache,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                try:os.fsync(directory_fd)
                finally:os.close(directory_fd)
        except BaseException:
            os.close(fd)
            raise

    def _fresh_snapshot(self,root):
        root=Path(root);row=self.rows.get(str(root));need(row is not None,'RETIRED_UNKNOWN_MISSING_ROOT_REFUSED')
        now=time.time_ns();need(row['terminal_ns']<now-600*10**9,'RETIRED_ORIGINAL_TERMINAL_STRICTLY_OUTSIDE_600S')
        need(not self._seen(root),'RETIRED_PRESENT_THEN_MISSING_FAIL_CLOSED')
        try:root.lstat()
        except FileNotFoundError:pass
        else:need(False,'RETIRED_ABSENCE_REQUIRED_NOT_SYMLINK_OR_PRESENT')
        facts=self.lifecycle(row['original_root'])
        # Only a frozen actual reader can provide this. OLD deletion/book0 by
        # themselves never satisfy the required original lifecycle evidence.
        need(type(facts)is dict and facts.get('root')==row['original_root'] and
             facts.get('lifecycle_reader_sha256')==self.lifecycle_pin and
             type(facts.get('observed_ns'))is int and 0<=time.time_ns()-facts['observed_ns']<=60*10**9 and
             facts.get('original_active_jobs')==0 and type(facts.get('original_active_jobs'))is int and
             facts.get('original_pending_jobs')==0 and type(facts.get('original_pending_jobs'))is int and
             facts.get('original_no_reentry')is True and facts.get('actual_original_lifecycle_bound')is True and
             type(facts.get('lifecycle_reference'))is dict and
             len(facts['lifecycle_reference'].get('sha256',''))==64,
             'RETIRED_FRESH_ORIGINAL_NO_ACTIVE_PENDING_OR_REENTRY_REQUIRED')
        parent,ps=canonical(root.parent,directory=True)
        book,bs=canonical(root.parent/'ledger.json.reservations-v52.json')
        need(public_identity(ps)==facts['registered_parent_identity'] and
             public_identity(bs)==facts['registered_book_identity'] and
             ps.st_dev==bs.st_dev and bs.st_nlink==1 and not stat.S_IMODE(bs.st_mode)&0o022,
             'RETIRED_FRESH_EXACT_REGISTERED_PARENT_AND_BOOK')
        need(self.observer.reservation(book)==0,'RETIRED_ORIGINAL_BOOK_ACTIVE_ZERO_REQUIRED')
        need(stamp(ps)==stamp(parent.lstat()) and stamp(bs)==stamp(book.lstat()),
             'RETIRED_PARENT_BOOK_STABLE_DURING_FRESH_CONTROL_READ')
        try:root.lstat()
        except FileNotFoundError:pass
        else:need(False,'RETIRED_ROOT_APPEARED_DURING_GUARD_REQUIRES_ORIGINAL_SCAN')
        return dict(parent=stamp(ps),book=stamp(bs),lifecycle_reference=facts['lifecycle_reference'])

    def accept_absent(self,root):
        self.retired[str(root)]=self._fresh_snapshot(root)

    def finish(self):
        for root,previous in self.retired.items():
            need(self._fresh_snapshot(root)==previous,'RETIRED_FRESH_CONTROL_CHANGED_DURING_SCAN')
        for root,identity in self.present.items():
            _,s=canonical(root,directory=True)
            need((s.st_dev,s.st_ino)==identity,'RETIRED_PRESENT_ROOT_CHANGED_DURING_SCAN')


def private_performance(original,guard):
    """Return NEW module globals, leave original module/functions untouched."""
    raw=Path(original.__file__).read_bytes()
    need(hashlib.sha256(raw).hexdigest()==SCAN_SOURCE_PIN,'RETIRED_ORIGINAL_PERFORMANCE_SOURCE_PIN')
    tree=ast.parse(raw);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='scan')
    baseline=copy.deepcopy(node);sites=[]
    for parent in ast.walk(node):
        body=getattr(parent,'body',None)
        if isinstance(body,list):
            for i,n in enumerate(body):
                if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='rfd':
                    sites.append((body,i,n))
    need(len(sites)==1,'RETIRED_ONE_ORIGINAL_ROOT_OPEN_SITE')
    body,i,opened=sites[0]
    need(ast.unparse(opened.value)=='os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)',
         'RETIRED_EXACT_ORIGINAL_DIRFD_NOFOLLOW_OPEN')
    handler=ast.ExceptHandler(type=ast.Name(id='FileNotFoundError',ctx=ast.Load()),name=None,
        body=ast.parse('_retired_guard.accept_absent(root)\ncontinue').body)
    replacement=ast.Try(body=[opened],handlers=[handler],orelse=[],finalbody=[])
    mark=ast.parse('_retired_guard.mark_present(root,rfd)').body[0]
    body[i:i+1]=[replacement,mark]
    inverse=copy.deepcopy(node)
    for n in ast.walk(inverse):
        if isinstance(getattr(n,'body',None),list):
            out=[]
            for x in n.body:
                if isinstance(x,ast.Try)and len(x.body)==1 and isinstance(x.body[0],ast.Assign)and len(x.body[0].targets)==1 and isinstance(x.body[0].targets[0],ast.Name)and x.body[0].targets[0].id=='rfd'and len(x.handlers)==1 and isinstance(x.handlers[0].type,ast.Name)and x.handlers[0].type.id=='FileNotFoundError':
                    out.extend(x.body);continue
                if isinstance(x,ast.Expr)and isinstance(x.value,ast.Call)and ast.unparse(x.value.func)=='_retired_guard.mark_present':continue
                out.append(x)
            n.body=out
    need(ast.dump(inverse,include_attributes=False)==ast.dump(baseline,include_attributes=False),
         'RETIRED_ALL_OTHER_ORIGINAL_SCAN_AST_UNCHANGED')
    module=ModuleType(original.__name__+'_exact18_private');module.__dict__.update(original.__dict__)
    module._retired_guard=guard
    ns=dict(module.__dict__);exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                                       __file__+':original_scan_single_open_seam','exec'),ns)
    modified=ns['scan']
    def scan(observer,roots,path,*,budget=4.,clock=time.monotonic):
        guard.begin(path)
        result=modified(observer,roots,path,budget=budget,clock=clock)
        guard.finish()
        result=dict(result,retired_registered_roots_outside_current_window=len(guard.retired),
                    original_registered_root_list_unchanged=True)
        return result
    module.scan=scan
    for name in ('health','collect'):
        f=getattr(original,name);g=FunctionType(f.__code__,module.__dict__,f.__name__,f.__defaults__,f.__closure__)
        g.__kwdefaults__=f.__kwdefaults__;setattr(module,name,g)
    module.private_retired_proof=dict(original_scan_inverse_AST=True,original_health_collect_CodeTypes_unchanged=True,
        original_module_or_globals_modified=False,exact_root_open_exception_only=True,actual_production_lifecycle_binding_qualified=False)
    return module
