"""Bind fresh native CLI conversation identity using directory-name metadata only.

No CLI flags/session content, prompt, candidate or credential is inspected. A
missing/ambiguous/changed identity is rejected BEFORE the original relay reserves
or marks SENT. Every ordinary request body and usage path remains unchanged.
"""
from pathlib import Path
from types import MethodType
from collections.abc import Mapping
import os,stat,threading,uuid
from common import need,digest
from feasibility_relay import Rejected

class CliSessions(Mapping):
 def __init__(self,trajectory,homes,record):
  need(type(trajectory)is str and bool(trajectory),'FRESH48_SESSION_TRAJECTORY')
  self.t=trajectory;self.homes={role:Path(p)for role,p in homes.items()};self.values={};self.lock=threading.RLock();self.record=record
  need(len(self.homes)in(4,8)and list(self.homes)==[f'worker-{i:02d}'for i in range(len(self.homes))],
       'FRESH48_SESSION_EXACT_FRESH_ROSTER')
 def __len__(self):return len(self.homes)
 def __iter__(self):return iter((self.t,r)for r in self.homes)
 def __contains__(self,key):
  try:self[key];return True
  except KeyError:return False
 def __getitem__(self,key):
  if type(key)is not tuple or len(key)!=2 or key[0]!=self.t or key[1]not in self.homes:raise KeyError(key)
  role=key[1];home=self.homes[role];base=home/'.copilot/session-state'
  with self.lock:
   # Directory metadata only. Never open a session file or read its body.
   try:
    for p in(home,home/'.copilot',base):
     s=p.lstat();need(stat.S_ISDIR(s.st_mode)and not p.is_symlink()and p.resolve()==p,
                     'FRESH48_SESSION_CANONICAL_DIRECTORY_NO_SYMLINK')
   except FileNotFoundError:raise KeyError(key)from None
   rows=[]
   with os.scandir(base)as entries:
    for e in entries:
     try:value=str(uuid.UUID(e.name))
     except(ValueError,AttributeError):continue
     need(e.name==value,'FRESH48_SESSION_CANONICAL_UUID')
     s=e.stat(follow_symlinks=False)
     need(stat.S_ISDIR(s.st_mode)and not e.is_symlink(),'FRESH48_SESSION_UUID_REGULAR_DIRECTORY')
     rows.append((value,s.st_dev,s.st_ino))
   if not rows:raise KeyError(key)
   need(len(rows)==1,'FRESH48_SESSION_AMBIGUOUS_CONVERSATIONS')
   row=rows[0];old=self.values.get(key)
   if old is not None:need(old==row,'FRESH48_SESSION_CHANGED_NO_SILENT_FALLBACK')
   else:
    self.values[key]=row
    self.record('FRESH48_ORIGINAL_CLI_SESSION_METADATA_BOUND',{'trajectory':self.t,'role':role,
       'session_identity_sha256':digest(row),'metadata_only':True,'session_created_or_rewritten':False})
   return row[0]

def before_admission(engine,sessions):
 """The native HTTP server calls engine.run before original ledger.begin/SENT."""
 from scientific_relay import ScientificRelay
 need(type(engine)is ScientificRelay,'FRESH48_SESSION_ORIGINAL_SCIENTIFIC_RELAY')
 need(not hasattr(engine,'_fresh48_session_guard'),'FRESH48_SESSION_GUARD_ONCE')
 original=engine.run
 def run(_,request,identity,emit=None,*,http_custody=None):
  try:sessions[identity]
  except KeyError:raise Rejected('ORIGINAL_CLI_SESSION_METADATA_NOT_YET_AVAILABLE',503)from None
  # Other validation refusals are not translated or hidden. Critically, every
  # one occurs before the original method enters any budget/RNG/send path.
  return original(request,identity,emit=emit,http_custody=http_custody)
 engine.run=MethodType(run,engine);engine._fresh48_session_guard=sessions
 return original
