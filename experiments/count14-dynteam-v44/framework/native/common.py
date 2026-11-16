"""Small strict metadata and private-file primitives; no production discovery."""
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
import hashlib,json,os,re,stat,uuid
class Refused(RuntimeError):
    def __init__(self,code):self.code=code;super().__init__(code)
def need(condition,code):
    if not condition:raise Refused(code)
def integer(x,code,minimum=0):
    need(type(x)is int and x>=minimum,code);return x
def ident(x):
    need(type(x)is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}',x),'IDENTIFIER');return x
def trajectory_id(x):
    # Compiler identities are hierarchical (experiment/setting/block/seed), not
    # a single role/file-name identifier. Preserve the exact string; never
    # sanitize it into an alias that would collapse independent accounts.
    need(type(x)is str and 0<len(x)<=512,'TRAJECTORY_ID')
    for segment in parts(x):ident(segment)
    return x
def sha(x):
    need(type(x)is str and re.fullmatch('[0-9a-f]{64}',x),'SHA256');return x
def wire(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(wire(x)).hexdigest()
def strict(raw):
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'DUPLICATE_KEY');d[k]=v
        return d
    try:return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'NONFINITE_JSON'))
    except (ValueError,UnicodeError):raise Refused('INVALID_JSON')from None
def parts(name):
    need(type(name)is str and bool(name) and '\x00'not in name and '\\'not in name,'RELATIVE_PATH')
    p=PurePosixPath(name);need(not p.is_absolute() and all(x not in ('','.','..') for x in name.split('/')),'RELATIVE_PATH');return p.parts
def stamp(s):return(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
def hash_file(path):
    with regular_fd(path) as fd:
        before=os.fstat(fd);h=hashlib.sha256();n=0
        for b in iter(lambda:os.read(fd,1024*1024),b''):h.update(b);n+=len(b)
        need(stamp(before)==stamp(os.fstat(fd)) and stamp(before)==stamp(Path(path).lstat()),'FILE_CHANGED')
        return {'size':n,'sha256':h.hexdigest()}
@contextmanager
def regular_fd(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:need(stat.S_ISREG(os.fstat(fd).st_mode),'REGULAR_FILE');yield fd
    finally:os.close(fd)
def private_dir(path,*,create=False):
    p=Path(path)
    need(p.is_absolute() and p.resolve()==p,'CANONICAL_PRIVATE_DIRECTORY')
    if create:p.mkdir(mode=0o700,parents=True,exist_ok=True)
    s=p.lstat();need(stat.S_ISDIR(s.st_mode) and s.st_uid==os.geteuid() and not(s.st_mode&0o077),'PRIVATE_DIRECTORY');return p
def sync_dir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
def publish(path,raw,*,mode=0o600):
    """Durable atomic no-clobber publication, never expose a partial reference."""
    path=Path(path);temporary=path.parent/('.publish-'+uuid.uuid4().hex+'.partial')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:
        with os.fdopen(fd,'wb',closefd=False) as f:f.write(raw);f.flush();os.fsync(fd)
        os.link(temporary,path,follow_symlinks=False);sync_dir(path.parent)
    finally:
        os.close(fd);temporary.unlink();sync_dir(path.parent)

def publish_readonly_metadata(path,raw):
    """Explicit PUBLIC control bytes, exact0444 BEFORE atomic publication.

    Never use for capabilities, provider secrets, private state or HOME. The
    existing publish() and process-wide umask retain their private contract.
    Caller owns the dedicated leaf, mounted read-only to its fixed reader.
    """
    path=Path(path);temporary=path.parent/('.publish-'+uuid.uuid4().hex+'.partial')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False)as f:
            f.write(raw);f.flush();s=os.fstat(fd)
            need(stat.S_ISREG(s.st_mode)and s.st_uid==os.geteuid()and s.st_nlink==1,'PUBLIC_METADATA_OWNED_SINGLE_FILE')
            os.fchmod(fd,0o444);os.fsync(fd)
        os.link(temporary,path,follow_symlinks=False);sync_dir(path.parent)
    finally:
        os.close(fd);temporary.unlink();sync_dir(path.parent)

@contextmanager
def unix_socket_address(path):
    """Same canonical filesystem socket inode, even beyond sockaddr_un.sun_path.

    Long host paths are addressed through a private O_PATH dirfd held for the
    syscall. No chdir, symlink creation, rename, alternate root or permission
    change. Worker-side short bind-mounted names keep their original address.
    """
    p=Path(path)
    need(p.is_absolute()and p.resolve()==p and p.name not in('','.','..'),'UNIX_SOCKET_CANONICAL_PATH')
    raw=os.fsencode(p)
    if len(raw)<=107:
        yield str(p)
        return
    parent=p.parent;before=parent.lstat()
    need(stat.S_ISDIR(before.st_mode),'UNIX_SOCKET_PARENT_DIRECTORY')
    fd=os.open(parent,os.O_PATH|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        opened=os.fstat(fd)
        need((opened.st_dev,opened.st_ino)==(before.st_dev,before.st_ino),'UNIX_SOCKET_PARENT_CHANGED')
        address='/proc/self/fd/'+str(fd)+'/'+p.name
        need(len(os.fsencode(address))<=107,'UNIX_SOCKET_LEAF_TOO_LONG')
        yield address
        after=parent.lstat()
        need((opened.st_dev,opened.st_ino)==(after.st_dev,after.st_ino),'UNIX_SOCKET_PARENT_CHANGED')
    finally:os.close(fd)
