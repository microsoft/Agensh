"""Fixed PUBLIC archive-control booleans, never read/hash scientific archives.

Only original current-turn control fields and manifest status/byte-count/digest
format. Archive content, PKL, logs, candidates and model output are not opened.
The archive producer is the exact registered original bridge, not an agent JSON.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

from native_bridge_protocol import BASE


def _read(path, owner, limit):
    path=Path(path)
    if path.parent.resolve()!=path.parent:
        raise ValueError('DYNTEAM_ARCHIVE_CONTROL_CANONICAL_PARENT')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not(stat.S_ISREG(before.st_mode)and before.st_uid==owner and 0<before.st_size<=limit):
            raise ValueError('DYNTEAM_ARCHIVE_CONTROL_OWN_REGULAR_FILE')
        raw=os.read(fd,limit+1);after=os.fstat(fd)
        if len(raw)!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(
            after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('DYNTEAM_ARCHIVE_CONTROL_FILE_CHANGED')
        return json.loads(raw)
    finally:os.close(fd)


class NativeArchiveGuard:
    def __init__(self,bindings):
        self.bindings={}
        for key,row in bindings.items():
            root,control=Path(row['archive_root']),Path(row['native_turn_metadata'])
            if not(root.is_absolute()and root.resolve()==root and root.is_dir()and control.is_absolute()and
                   control.parent.resolve()==control.parent and type(row['owner_uid'])is int):
                raise ValueError('DYNTEAM_REGISTERED_ORIGINAL_ARCHIVE_CONTROL_BINDING')
            s=root.stat()
            self.bindings[key]=(root,control,row['owner_uid'],(s.st_dev,s.st_ino))

    def __call__(self,row,_child):
        root,control,uid,identity=self.bindings[(row['trajectory_id'],row['role_slot'])]
        s=root.lstat()
        if root.resolve()!=root or (s.st_dev,s.st_ino)!=identity or s.st_uid!=uid:
            return False
        current=_read(control,uid,4096)
        turn=current.get('turn_id')
        if not(type(turn)is str and turn and turn not in ('.','..')and '/'not in turn and '\\'not in turn):
            return False
        digest=lambda value:hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        if digest([BASE,row['trajectory_id'],row['role_slot'],turn])!=row['native_turn_sha256']:
            return False
        path=root/turn
        if path.resolve()!=path or not path.is_dir()or path.is_symlink():return False
        manifest=_read(path/'manifest.json',uid,65536)
        checksum=manifest.get('sha256');size=manifest.get('bytes')
        if not(manifest.get('status')in ('archived','complete')and type(size)is int and size>0 and
               type(checksum)is str and len(checksum)==64 and all(c in '0123456789abcdef'for c in checksum)):
            return False
        # stat only: do NOT open/hash the .tar.gz or its scientific members.
        archive=(path/'state.tar.gz').lstat()
        return stat.S_ISREG(archive.st_mode)and archive.st_uid==uid and archive.st_size==size
